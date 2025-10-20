"""
Django management command to run the documents.ready consumer.

This command starts a RabbitMQ consumer that listens for documents.ready events
from the Document microservice and completes the transfer process.

Usage:
    python manage.py run_documents_consumer
"""

from django.core.management.base import BaseCommand
from affiliation.rabbitmq.documents_ready_consumer import main


class Command(BaseCommand):
    help = "Run RabbitMQ consumer for documents.ready events"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting documents.ready consumer..."))
        main()
