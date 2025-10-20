#!/usr/bin/env python
"""
RabbitMQ consumer for unregister.citizen.completed events.

This consumer listens for events from the Operator Connectivity microservice 
indicating that an unregisterCitizen API call has been completed (successfully or with errors).

When received, it updates the local state based on the response:
- If successful: Confirms external unregistration completed
- If failed: Logs error and may need manual intervention

Usage:
    python manage.py run_unregister_consumer
    
Or manually:
    python -m affiliation.rabbitmq.unregister_citizen_consumer
"""
import os
import sys
import django
import logging

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings
from affiliation.rabbitmq.consumer import RabbitMQConsumer, create_message_handler

logger = logging.getLogger(__name__)


def handle_unregister_citizen_completed(message: dict):
    """
    Handle unregister.citizen.completed events from Operator Connectivity.

    Expected message format:
    {
        "id": "1128456232",
        "operatorId": "68f003d9a49e090002e5d0b5",
        "success": true,
        "message": "Citizen unregistered successfully",
        "response": {
            // Original API response if successful
        },
        "error": {
            // Error details if failed
        }
    }

    Args:
        message: The event message containing unregistration result
    """
    try:
        from affiliation.models import Citizen, Affiliation
        from affiliation.rabbitmq.publisher import publish_user_transferred

        citizen_id = str(message.get("id"))
        success = message.get("success", False)
        msg = message.get("message", "No message provided")

        if not citizen_id:
            logger.error("unregister.citizen.completed event missing id field")
            print("❌ [UnregisterCompleted] Missing citizen ID in event")
            return

        logger.info(f"📥 [UnregisterCompleted] Received event for citizen {citizen_id}")
        print(
            f"📥 [UnregisterCompleted] Processing unregister.citizen.completed for citizen {citizen_id}"
        )

        # Find the citizen
        citizen = Citizen.objects.filter(citizen_id=citizen_id).first()
        if not citizen:
            logger.warning(
                f"Citizen {citizen_id} not found in database (may have been deleted already)"
            )
            print(f"⚠️  [UnregisterCompleted] Citizen {citizen_id} not found")
            return

        if success:
            logger.info(
                f"✅ [UnregisterCompleted] Citizen {citizen_id} unregistered successfully: {msg}"
            )
            print(f"✅ [UnregisterCompleted] Success: {msg}")

            # Check if citizen is being TRANSFERRED (outgoing transfer)
            affiliation = Affiliation.objects.filter(citizen=citizen).first()

            if affiliation and affiliation.status == "TRANSFERRING":
                # This is an OUTGOING TRANSFER - continue the transfer process
                logger.info(
                    f"🚀 [UnregisterCompleted] Citizen {citizen_id} is TRANSFERRING, continuing transfer flow"
                )
                print(
                    f"🚀 [UnregisterCompleted] Continuing outgoing transfer for citizen {citizen_id}"
                )

                # Call transfer service to continue the transfer
                from affiliation.services.transfer_service import TransferService

                transfer_service = TransferService()
                result = transfer_service.continue_transfer_after_unregister(citizen_id)

                if result["success"]:
                    logger.info(
                        f"✅ [UnregisterCompleted] Transfer continuation successful for citizen {citizen_id}"
                    )
                    print(f"✅ [UnregisterCompleted] Transfer sent to target operator")
                else:
                    logger.error(
                        f"❌ [UnregisterCompleted] Transfer continuation failed: {result['message']}"
                    )
                    print(f"❌ [UnregisterCompleted] Transfer continuation failed")

                # Don't delete yet - wait for target operator confirmation
                return

            # This is a DIRECT DELETION (not a transfer)
            logger.info(f"🗑️  [UnregisterCompleted] Direct deletion for citizen {citizen_id}")

            # Publish user.transferred event for cleanup (documents, etc.)
            try:
                logger.info(f"Publishing user.transferred event for citizen {citizen_id}")
                publish_user_transferred(int(citizen_id))
                logger.info(f"Published user.transferred event for citizen {citizen_id}")
            except Exception as e:
                logger.error(
                    f"Error publishing user.transferred event for citizen {citizen_id}: {str(e)}"
                )

            # Delete affiliation first (foreign key relationship)
            if affiliation:
                affiliation.delete()
                logger.info(f"Deleted affiliation for citizen {citizen_id}")

            # Delete citizen
            citizen_name = citizen.name
            citizen.delete()
            logger.info(f"Deleted citizen {citizen_id} ({citizen_name}) after MINTIC confirmation")
            print(f"✅ [UnregisterCompleted] Citizen {citizen_id} fully deleted")

        else:
            error_msg = (
                message.get("error", {}).get("message", msg)
                if isinstance(message.get("error"), dict)
                else msg
            )
            logger.error(
                f"❌ [UnregisterCompleted] Failed to unregister citizen {citizen_id}: {error_msg}"
            )
            print(f"❌ [UnregisterCompleted] Error: {error_msg}")

            # Rollback pending deletion status - keep the citizen
            citizen.pending_deletion = False
            citizen.verification_message = f"Unregister failed: {error_msg}"
            citizen.save()

            # Rollback affiliation status
            affiliation = Affiliation.objects.filter(citizen=citizen).first()
            if affiliation:
                affiliation.status = "AFFILIATED"
                affiliation.save()

            print(f"⚠️  [UnregisterCompleted] Kept citizen {citizen_id}, unregister failed")

    except Exception as e:
        logger.error(f"Error handling unregister.citizen.completed event: {str(e)}")
        print(f"❌ [UnregisterCompleted] Error: {str(e)}")
        raise  # Re-raise to trigger message requeue
        raise  # Re-raise to trigger message requeue


def main():
    """Run the unregister.citizen.completed consumer."""
    queue_name = settings.RABBITMQ_UNREGISTER_CITIZEN_COMPLETED_QUEUE

    print(f"\n{'=' *60}")
    print(f"Starting unregister.citizen.completed consumer")
    print(f"Queue: {queue_name}")
    print(f"RabbitMQ Host: {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}")
    print(f"{'=' *60}\n")

    consumer = RabbitMQConsumer(queue_name)
    callback = create_message_handler(handle_unregister_citizen_completed)

    try:
        print(f"🎧 [UnregisterCompleted] Listening for events on '{queue_name}'...\n")
        consumer.consume(callback)
    except KeyboardInterrupt:
        print("\n\n⏹️  [UnregisterCompleted] Consumer stopped by user")
        consumer.stop()
    except Exception as e:
        print(f"\n\n❌ [UnregisterCompleted] Consumer error: {str(e)}")
        consumer.stop()


if __name__ == "__main__":
    main()
