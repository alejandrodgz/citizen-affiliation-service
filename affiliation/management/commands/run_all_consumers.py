"""
Django management command to run all RabbitMQ consumers in parallel threads.

This command starts all consumers (documents_ready, register_citizen_completed,
unregister_citizen_completed) in separate threads so they can all listen
simultaneously from a single service.

Usage:
    python manage.py run_all_consumers
"""

import threading
import logging
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run all RabbitMQ consumers in parallel threads"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("Starting ALL RabbitMQ Consumers"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        # Import consumers
        from affiliation.rabbitmq.documents_ready_consumer import main as documents_ready_main
        from affiliation.rabbitmq.register_citizen_consumer import main as register_citizen_main
        from affiliation.rabbitmq.unregister_citizen_consumer import main as unregister_citizen_main

        # Create threads for each consumer
        consumers = [
            {
                "name": "DocumentsReady",
                "function": documents_ready_main,
                "queue": settings.RABBITMQ_DOCUMENTS_READY_QUEUE,
            },
            {
                "name": "RegisterCitizenCompleted",
                "function": register_citizen_main,
                "queue": settings.RABBITMQ_REGISTER_CITIZEN_COMPLETED_QUEUE,
            },
            {
                "name": "UnregisterCitizenCompleted",
                "function": unregister_citizen_main,
                "queue": settings.RABBITMQ_UNREGISTER_CITIZEN_COMPLETED_QUEUE,
            },
        ]

        threads = []
        for consumer in consumers:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Starting {consumer['name']} consumer (queue: {consumer['queue']})"
                )
            )
            thread = threading.Thread(
                target=consumer["function"], name=consumer["name"], daemon=True
            )
            thread.start()
            threads.append(thread)

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS(f"All {len(threads)} consumers started successfully!"))
        self.stdout.write(self.style.SUCCESS("Press Ctrl+C to stop all consumers"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        # Keep the main thread alive
        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n\n⏹️  Stopping all consumers..."))
            self.stdout.write(self.style.SUCCESS("All consumers stopped."))
