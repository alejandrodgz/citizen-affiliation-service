import json
import logging
import pika
from django.conf import settings

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    """RabbitMQ consumer for citizen events."""

    def __init__(self, queue_name: str):
        """
        Initialize RabbitMQ consumer.

        Args:
            queue_name: The queue to consume from
        """
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
        self._initialize_connection()

    def _initialize_connection(self):
        """Initialize the RabbitMQ connection and channel."""
        try:
            credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
            parameters = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                virtual_host=settings.RABBITMQ_VHOST,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare the queue to ensure it exists
            self.channel.queue_declare(queue=self.queue_name, durable=True)

            # Set QoS to process one message at a time
            self.channel.basic_qos(prefetch_count=1)

            logger.info(f"RabbitMQ consumer initialized for queue: {self.queue_name}")
        except Exception as e:
            logger.error(f"Failed to initialize RabbitMQ consumer: {str(e)}")
            self.connection = None
            self.channel = None

    def consume(self, callback):
        """
        Start consuming messages from the queue.

        Args:
            callback: Function to call for each message.
                     Should accept (ch, method, properties, body) parameters
        """
        if not self.channel:
            logger.error("RabbitMQ channel not initialized")
            return

        try:
            logger.info(f"Starting to consume from queue: {self.queue_name}")
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=callback,
                auto_ack=False,  # Manual acknowledgment
            )
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
            self.stop()
        except Exception as e:
            logger.error(f"Error consuming messages: {str(e)}")
            self.stop()

    def stop(self):
        """Stop consuming and close the connection."""
        try:
            if self.channel:
                self.channel.stop_consuming()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ consumer stopped and connection closed")
        except Exception as e:
            logger.error(f"Error stopping consumer: {str(e)}")


def create_message_handler(handler_func):
    """
    Create a RabbitMQ message callback that wraps a custom handler function.

    Args:
        handler_func: Function that takes the parsed message dict and processes it

    Returns:
        Callback function for RabbitMQ consumer
    """

    def callback(ch, method, properties, body):
        try:
            message = json.loads(body.decode("utf-8"))
            logger.info(f"Received message: {message}")

            # Call the custom handler
            handler_func(message)

            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info("Message processed and acknowledged")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {str(e)}")
            # Reject and don't requeue invalid messages
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            # Requeue the message for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    return callback


# Example usage
if __name__ == "__main__":
    """Run the consumer as a standalone script."""

    def handle_user_transferred(message: dict):
        """Handle user.transferred events."""
        id_citizen = message.get("idCitizen")
        logger.info(f"Processing user.transferred for citizen: {id_citizen}")
        # Add your business logic here

    consumer = RabbitMQConsumer(settings.RABBITMQ_USER_TRANSFERRED_QUEUE)
    callback = create_message_handler(handle_user_transferred)
    consumer.consume(callback)
