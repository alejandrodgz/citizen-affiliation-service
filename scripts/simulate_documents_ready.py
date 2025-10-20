#!/usr/bin/env python
"""
Script to simulate the Document Service publishing a documents.ready event.

This is used for testing the transfer flow without needing the actual Document Service.

Usage:
    python scripts/simulate_documents_ready.py <citizen_id>
    
Example:
    python scripts/simulate_documents_ready.py 5555666777
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import json
import pika
from django.conf import settings


def publish_documents_ready(citizen_id: int):
    """
    Publish a documents.ready event to RabbitMQ.
    
    Args:
        citizen_id: The citizen ID to publish the event for
    """
    try:
        # Connect to RabbitMQ
        credentials = pika.PlainCredentials(
            settings.RABBITMQ_USER,
            settings.RABBITMQ_PASSWORD
        )
        parameters = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            credentials=credentials
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Declare the queue
        queue_name = settings.RABBITMQ_DOCUMENTS_READY_QUEUE
        channel.queue_declare(queue=queue_name, durable=True)
        
        # Prepare message
        message = {"idCitizen": citizen_id}
        
        # Publish message
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json'
            )
        )
        
        print(f"✅ Published documents.ready event for citizen {citizen_id}")
        print(f"   Queue: {queue_name}")
        print(f"   Message: {message}")
        
        connection.close()
        
    except Exception as e:
        print(f"❌ Error publishing message: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/simulate_documents_ready.py <citizen_id>")
        print("Example: python scripts/simulate_documents_ready.py 5555666777")
        sys.exit(1)
    
    try:
        citizen_id = int(sys.argv[1])
        publish_documents_ready(citizen_id)
    except ValueError:
        print("❌ Error: citizen_id must be a number")
        sys.exit(1)
