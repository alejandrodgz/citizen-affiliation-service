#!/usr/bin/env python
"""
RabbitMQ consumer for documents.ready events.

This consumer listens for events from the Document microservice indicating
that documents have been successfully downloaded and uploaded for a citizen transfer.

When received, it completes the transfer process by:
1. Updating citizen to registered
2. Updating affiliation status to AFFILIATED
3. Calling confirmation API to notify sending operator
4. Publishing affiliation.created event

Usage:
    python manage.py run_documents_consumer
    
Or manually:
    python -m affiliation.rabbitmq.documents_ready_consumer
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
from affiliation.services.transfer_service import TransferService

logger = logging.getLogger(__name__)


def handle_documents_ready(message: dict):
    """
    Handle documents.ready events from the Document microservice.

    Expected message format:
    {
        "idCitizen": 1128456232
    }

    Args:
        message: The event message containing citizen ID
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

        # Complete the transfer using TransferService
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


def main():
    """Run the documents.ready consumer."""
    queue_name = settings.RABBITMQ_DOCUMENTS_READY_QUEUE

    print(f"\n{'=' *60}")
    print(f"Starting documents.ready consumer")
    print(f"Queue: {queue_name}")
    print(f"RabbitMQ Host: {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}")
    print(f"{'=' *60}\n")

    consumer = RabbitMQConsumer(queue_name)
    callback = create_message_handler(handle_documents_ready)

    try:
        print(f"🎧 [DocumentsReady] Listening for events on '{queue_name}'...\n")
        consumer.consume(callback)
    except KeyboardInterrupt:
        print("\n\n⏹️  [DocumentsReady] Consumer stopped by user")
        consumer.stop()
    except Exception as e:
        print(f"\n\n❌ [DocumentsReady] Consumer error: {str(e)}")
        consumer.stop()
        raise


if __name__ == "__main__":
    main()
