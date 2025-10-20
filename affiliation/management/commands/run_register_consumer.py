"""
Django management command to run the register.citizen.completed consumer.

This command starts a RabbitMQ consumer that listens for register.citizen.completed
events from the Operator Connectivity microservice.

Usage:
    python manage.py run_register_consumer
"""

from django.core.management.base import BaseCommand
from affiliation.rabbitmq.register_citizen_consumer import main


class Command(BaseCommand):
    help = "Run RabbitMQ consumer for register.citizen.completed events"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting register.citizen.completed consumer..."))
        main()
