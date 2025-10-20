#!/usr/bin/env python
"""
RabbitMQ consumer for register.citizen.completed events.

This consumer listens for events from the Operator Connectivity microservice 
indicating that a registerCitizen API call has been completed (successfully or with errors).

When received, it updates the local state based on the response:
- If successful: Updates citizen/affiliation records as registered
- If failed: Logs error and may need to rollback or mark for retry

Usage:
    python manage.py run_register_consumer
    
Or manually:
    python -m affiliation.rabbitmq.register_citizen_consumer
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


def handle_register_citizen_completed(message: dict):
    """
    Handle register.citizen.completed events from Operator Connectivity.

    Expected message format from Operator Connectivity:

    SUCCESS (HTTP 201):
    {
        "id": "7778686591",
        "statusCode": 201
    }

    FAILURE (HTTP 501 or other error):
    {
        "id": "7778686591",
        "statusCode": 501
    }

    Args:
        message: The event message containing registration result from MINTIC API
    """
    try:
        from affiliation.models import Citizen, Affiliation

        citizen_id = str(message.get("id"))
        status_code = message.get("statusCode", 0)

        if not citizen_id:
            logger.error("register.citizen.completed event missing id field")
            print("❌ [RegisterCompleted] Missing citizen ID in event")
            return

        logger.info(
            f"📥 [RegisterCompleted] Received event for citizen {citizen_id} (statusCode: {status_code})"
        )
        print(
            f"📥 [RegisterCompleted] Processing register.citizen.completed for citizen {citizen_id}"
        )
        print(f"    Status Code: {status_code}")

        # Find the citizen
        citizen = Citizen.objects.filter(citizen_id=citizen_id).first()
        if not citizen:
            logger.error(f"Citizen {citizen_id} not found in database")
            print(f"❌ [RegisterCompleted] Citizen {citizen_id} not found")
            return

        if status_code == 201:
            logger.info(
                f"✅ [RegisterCompleted] Citizen {citizen_id} registered successfully with MINTIC"
            )
            print(f"✅ [RegisterCompleted] Success - Citizen registered in MINTIC")

            # Update citizen verification status
            citizen.is_verified = True
            citizen.verification_status = Citizen.VERIFICATION_VERIFIED
            citizen.verification_message = "Citizen successfully registered in MINTIC"
            citizen.save()

            # Check affiliation status
            affiliation = Affiliation.objects.filter(citizen=citizen).first()
            if affiliation:
                # If citizen is being TRANSFERRED (incoming transfer), check if we can complete
                if affiliation.status == "TRANSFERRING":
                    logger.info(
                        f"Citizen {citizen_id} is in TRANSFERRING status, checking if transfer can be completed"
                    )
                    from affiliation.services.transfer_service import TransferService

                    transfer_service = TransferService()
                    transfer_service.check_and_complete_transfer(citizen_id)
                else:
                    # Normal registration (not a transfer) - just update status
                    affiliation.status = "AFFILIATED"
                    affiliation.save()
                    logger.info(
                        f"Updated affiliation status to AFFILIATED for citizen {citizen_id}"
                    )

            print(f"✅ [RegisterCompleted] Citizen {citizen_id} now VERIFIED")

        else:
            # Any status code other than 201 is a failure
            logger.error(
                f"❌ [RegisterCompleted] Failed to register citizen {citizen_id} - Status code: {status_code}"
            )
            print(f"❌ [RegisterCompleted] Error - Status code: {status_code}")

            # Update citizen verification status to FAILED
            citizen.is_verified = False
            citizen.verification_status = Citizen.VERIFICATION_FAILED
            citizen.verification_message = f"Registration failed with status code: {status_code}"
            citizen.save()

            # Update affiliation status to FAILED
            affiliation = Affiliation.objects.filter(citizen=citizen).first()
            if affiliation:
                affiliation.status = "FAILED"
                affiliation.save()

            print(f"❌ [RegisterCompleted] Citizen {citizen_id} verification FAILED")

    except Exception as e:
        logger.error(f"Error handling register.citizen.completed event: {str(e)}")
        print(f"❌ [RegisterCompleted] Error: {str(e)}")
        raise  # Re-raise to trigger message requeue


def main():
    """Run the register.citizen.completed consumer."""
    queue_name = settings.RABBITMQ_REGISTER_CITIZEN_COMPLETED_QUEUE

    print(f"\n{'=' *60}")
    print(f"Starting register.citizen.completed consumer")
    print(f"Queue: {queue_name}")
    print(f"RabbitMQ Host: {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}")
    print(f"{'=' *60}\n")

    consumer = RabbitMQConsumer(queue_name)
    callback = create_message_handler(handle_register_citizen_completed)

    try:
        print(f"🎧 [RegisterCompleted] Listening for events on '{queue_name}'...\n")
        consumer.consume(callback)
    except KeyboardInterrupt:
        print("\n\n⏹️  [RegisterCompleted] Consumer stopped by user")
        consumer.stop()
    except Exception as e:
        print(f"\n\n❌ [RegisterCompleted] Consumer error: {str(e)}")
        consumer.stop()


if __name__ == "__main__":
    main()
