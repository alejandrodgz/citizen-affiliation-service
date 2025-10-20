"""
Django management command to run the unregister.citizen.completed consumer.

This command starts a RabbitMQ consumer that listens for unregister.citizen.completed
events from the Operator Connectivity microservice.

Usage:
    python manage.py run_unregister_consumer
"""

from django.core.management.base import BaseCommand
from affiliation.rabbitmq.unregister_citizen_consumer import main


class Command(BaseCommand):
    help = "Run RabbitMQ consumer for unregister.citizen.completed events"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting unregister.citizen.completed consumer..."))
        main()
