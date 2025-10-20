#!/usr/bin/env python
"""
Multi-event RabbitMQ consumer that listens to multiple queues.

This consumer handles ALL event types in parallel using threads.
To add a new event handler, just add it to QUEUE_HANDLERS below.

Usage:
    python -m affiliation.rabbitmq.multi_event_consumer
"""
import os
import sys
import django
import logging
import threading

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings
from affiliation.rabbitmq.consumer import RabbitMQConsumer, create_message_handler
from affiliation.services.transfer_service import TransferService

logger = logging.getLogger(__name__)


# ============================================================================
# EVENT HANDLERS - Add new handlers here for each event type
# ============================================================================


def handle_documents_ready(message: dict):
    """
    Handle documents.ready events from Document Service.
    Called when documents have been downloaded and uploaded.
    """
    try:
        id_citizen = message.get("idCitizen")

        if not id_citizen:
            logger.error("documents.ready event missing idCitizen field")
            print("❌ [DocumentsReady] Missing idCitizen in event")
            return

        citizen_id = str(id_citizen)

        logger.info(f"📄 [DocumentsReady] Received event for citizen {citizen_id}")
        print(f"📄 [DocumentsReady] Processing documents.ready for citizen {citizen_id}")

        # Complete the transfer
        service = TransferService()
        result = service.complete_transfer_after_documents(citizen_id)

        if result["success"]:
            logger.info(f"✅ [DocumentsReady] Transfer completed for citizen {citizen_id}")
            print(f"✅ [DocumentsReady] Transfer completed successfully for citizen {citizen_id}")
        else:
            logger.error(f"❌ [DocumentsReady] Failed to complete transfer: {result['message']}")
            print(f"❌ [DocumentsReady] Error: {result['message']}")

    except Exception as e:
        logger.error(f"Error handling documents.ready event: {str(e)}")
        print(f"❌ [DocumentsReady] Error: {str(e)}")
        raise  # Re-raise to trigger message requeue


def handle_user_transferred(message: dict):
    """
    Handle user.transferred events.
    Called when a citizen has been transferred to another operator.

    TODO: Implement Phase 2 (sending transfers) logic here
    """
    try:
        id_citizen = message.get("idCitizen")
        logger.info(f"📤 [UserTransferred] Received event for citizen {id_citizen}")
        print(f"📤 [UserTransferred] Processing user.transferred for citizen {id_citizen}")

        # TODO: Add handler logic when Phase 2 is implemented
        # Example: Update local records, notify admins, trigger cleanup
        print(f"⚠️  [UserTransferred] Handler not yet implemented (Phase 2)")

    except Exception as e:
        logger.error(f"Error handling user.transferred event: {str(e)}")
        print(f"❌ [UserTransferred] Error: {str(e)}")
        raise


def handle_affiliation_created(message: dict):
    """
    Handle affiliation.created events.
    This is an example - usually this event is consumed by OTHER services.

    You could use this to:
    - Send welcome emails
    - Trigger notifications
    - Update analytics
    - Sync with other systems
    """
    try:
        id_citizen = message.get("idCitizen")
        logger.info(f"🆕 [AffiliationCreated] Received event for citizen {id_citizen}")
        print(f"🆕 [AffiliationCreated] New affiliation for citizen {id_citizen}")

        # Example: Send welcome email, trigger analytics, etc.
        # TODO: Add your business logic here
        print(f"✅ [AffiliationCreated] Event processed")

    except Exception as e:
        logger.error(f"Error handling affiliation.created event: {str(e)}")
        print(f"❌ [AffiliationCreated] Error: {str(e)}")
        raise


# ============================================================================
# QUEUE CONFIGURATION - Map queues to their handlers
# ============================================================================

# Add new event handlers here - NO need to create new Docker services!
QUEUE_HANDLERS = {
    settings.RABBITMQ_DOCUMENTS_READY_QUEUE: handle_documents_ready,
    settings.RABBITMQ_USER_TRANSFERRED_QUEUE: handle_user_transferred,
    # Add more as needed:
    # settings.RABBITMQ_AFFILIATION_CREATED_QUEUE: handle_affiliation_created,
    # 'payment.completed': handle_payment_completed,
    # 'notification.sent': handle_notification_sent,
}


# ============================================================================
# CONSUMER STARTUP
# ============================================================================


def start_consumer_thread(queue_name: str, handler_func):
    """Start a consumer for a specific queue in a separate thread."""
    try:
        print(f"🎧 [{queue_name}] Starting consumer...")
        consumer = RabbitMQConsumer(queue_name)
        callback = create_message_handler(handler_func)
        consumer.consume(callback)
    except KeyboardInterrupt:
        print(f"\n⏹️  [{queue_name}] Consumer stopped")
        consumer.stop()
    except Exception as e:
        print(f"\n❌ [{queue_name}] Consumer error: {str(e)}")
        logger.error(f"Consumer error for {queue_name}: {str(e)}")
        raise


def main():
    """Start consumers for all configured queues."""
    print(f"\n{'=' *70}")
    print(f"🚀 Starting Multi-Event RabbitMQ Consumer")
    print(f"{'=' *70}")
    print(f"RabbitMQ: {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}")
    print(f"Listening to {len(QUEUE_HANDLERS)} queue(s):")
    for queue in QUEUE_HANDLERS.keys():
        print(f"  • {queue}")
    print(f"{'=' *70}\n")

    threads = []

    # Start a consumer thread for each queue
    for queue_name, handler_func in QUEUE_HANDLERS.items():
        thread = threading.Thread(
            target=start_consumer_thread,
            args=(queue_name, handler_func),
            name=f"Consumer-{queue_name}",
            daemon=True,
        )
        thread.start()
        threads.append(thread)
        logger.info(f"Started consumer thread for queue: {queue_name}")

    print(f"✅ All consumers started successfully!\n")

    # Keep main thread alive
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n\n⏹️  Shutting down all consumers...")
        sys.exit(0)


if __name__ == "__main__":
    main()
