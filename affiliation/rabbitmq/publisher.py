import json
import logging
import pika
from django.conf import settings

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """RabbitMQ publisher for citizen events."""

    def __init__(self):
        """Initialize RabbitMQ publisher with configuration from settings."""
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

            # Declare queues to ensure they exist
            self.channel.queue_declare(
                queue=settings.RABBITMQ_AFFILIATION_CREATED_QUEUE, durable=True
            )
            self.channel.queue_declare(queue=settings.RABBITMQ_USER_TRANSFERRED_QUEUE, durable=True)
            self.channel.queue_declare(
                queue=settings.RABBITMQ_DOCUMENTS_DOWNLOAD_REQUESTED_QUEUE, durable=True
            )
            self.channel.queue_declare(queue=settings.RABBITMQ_DOCUMENTS_READY_QUEUE, durable=True)
            # Declare new queues for register/unregister operations
            self.channel.queue_declare(
                queue=settings.RABBITMQ_REGISTER_CITIZEN_REQUESTED_QUEUE, durable=True
            )
            self.channel.queue_declare(
                queue=settings.RABBITMQ_UNREGISTER_CITIZEN_REQUESTED_QUEUE, durable=True
            )
            self.channel.queue_declare(
                queue=settings.RABBITMQ_REGISTER_CITIZEN_COMPLETED_QUEUE, durable=True
            )
            self.channel.queue_declare(
                queue=settings.RABBITMQ_UNREGISTER_CITIZEN_COMPLETED_QUEUE, durable=True
            )

            logger.info("RabbitMQ publisher initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RabbitMQ publisher: {str(e)}")
            self.connection = None
            self.channel = None

    def publish_affiliation_created(self, id_citizen: int) -> bool:
        """
        Publish an affiliation.created event to RabbitMQ.
        This event is fired when a new citizen is affiliated/registered with the operator.

        Args:
            id_citizen: The citizen ID that was affiliated

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.channel:
            logger.warning("RabbitMQ channel not initialized, attempting to reconnect")
            self._initialize_connection()
            if not self.channel:
                logger.error("Failed to reconnect to RabbitMQ")
                return False

        try:
            message = {"idCitizen": id_citizen}

            self.channel.basic_publish(
                exchange="",
                routing_key=settings.RABBITMQ_AFFILIATION_CREATED_QUEUE,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2, content_type="application/json"  # Make message persistent
                ),
            )

            logger.info(f"Published affiliation.created event for citizen {id_citizen}")
            print(f"✅ [RabbitMQ] Published affiliation.created event for citizen {id_citizen}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish affiliation.created event: {str(e)}")
            # Try to reconnect for next time
            self._close()
            return False

    def publish_user_transferred(self, id_citizen: int) -> bool:
        """
        Publish a user.transferred event to RabbitMQ.
        This event is fired when a citizen is transferred between operators.

        Args:
            id_citizen: The citizen ID that was transferred

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.channel:
            logger.warning("RabbitMQ channel not initialized, attempting to reconnect")
            self._initialize_connection()
            if not self.channel:
                logger.error("Failed to reconnect to RabbitMQ")
                return False

        try:
            message = {"idCitizen": id_citizen}

            self.channel.basic_publish(
                exchange="",
                routing_key=settings.RABBITMQ_USER_TRANSFERRED_QUEUE,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2, content_type="application/json"  # Make message persistent
                ),
            )

            logger.info(f"Published user.transferred event for citizen {id_citizen}")
            print(f"✅ [RabbitMQ] Published user.transferred event for citizen {id_citizen}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish user.transferred event: {str(e)}")
            # Try to reconnect for next time
            self._close()
            return False

    def publish_documents_download_requested(self, id_citizen: int, url_documents: dict) -> bool:
        """
        Publish a documents.download.requested event to RabbitMQ for Document Service.
        This event requests the document service to download files from URLs.

        Args:
            id_citizen: The citizen ID
            url_documents: Dictionary of document URLs to download

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.channel:
            logger.warning("RabbitMQ channel not initialized, attempting to reconnect")
            self._initialize_connection()
            if not self.channel:
                logger.error("Failed to reconnect to RabbitMQ")
                return False

        try:
            message = {"idCitizen": id_citizen, "urlDocuments": url_documents}

            self.channel.basic_publish(
                exchange="",
                routing_key=settings.RABBITMQ_DOCUMENTS_DOWNLOAD_REQUESTED_QUEUE,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2, content_type="application/json"  # Make message persistent
                ),
            )

            logger.info(f"Published documents.download.requested event for citizen {id_citizen}")
            print(f"📥 [RabbitMQ] Published documents.download.requested for citizen {id_citizen}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish documents.download.requested event: {str(e)}")
            # Try to reconnect for next time
            self._close()
            return False

    def publish_register_citizen_requested(self, citizen_data: dict) -> bool:
        """
        Publish a register.citizen.requested event to RabbitMQ for Operator Connectivity.
        This event requests Operator Connectivity to call POST /apis/registerCitizen.

        Args:
            citizen_data: Dictionary containing citizen registration data

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.channel:
            logger.warning("RabbitMQ channel not initialized, attempting to reconnect")
            self._initialize_connection()
            if not self.channel:
                logger.error("Failed to reconnect to RabbitMQ")
                return False

        try:
            message = {
                "id": citizen_data.get("id"),
                "name": citizen_data.get("name"),
                "address": citizen_data.get("address"),
                "email": citizen_data.get("email"),
                "operatorId": citizen_data.get("operatorId"),
                "operatorName": citizen_data.get("operatorName"),
            }

            self.channel.basic_publish(
                exchange="",
                routing_key=settings.RABBITMQ_REGISTER_CITIZEN_REQUESTED_QUEUE,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2, content_type="application/json"  # Make message persistent
                ),
            )

            logger.info(
                f"Published register.citizen.requested event for citizen {citizen_data.get('id')}"
            )
            print(
                f"📤 [RabbitMQ] Published register.citizen.requested for citizen {citizen_data.get('id')}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish register.citizen.requested event: {str(e)}")
            # Try to reconnect for next time
            self._close()
            return False

    def publish_unregister_citizen_requested(self, citizen_data: dict) -> bool:
        """
        Publish an unregister.citizen.requested event to RabbitMQ for Operator Connectivity.
        This event requests Operator Connectivity to call DELETE /apis/unregisterCitizen.

        Args:
            citizen_data: Dictionary containing citizen unregistration data

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.channel:
            logger.warning("RabbitMQ channel not initialized, attempting to reconnect")
            self._initialize_connection()
            if not self.channel:
                logger.error("Failed to reconnect to RabbitMQ")
                return False

        try:
            message = {
                "id": citizen_data.get("id"),
                "operatorId": citizen_data.get("operatorId"),
                "operatorName": citizen_data.get("operatorName"),
            }

            self.channel.basic_publish(
                exchange="",
                routing_key=settings.RABBITMQ_UNREGISTER_CITIZEN_REQUESTED_QUEUE,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2, content_type="application/json"  # Make message persistent
                ),
            )

            logger.info(
                f"Published unregister.citizen.requested event for citizen {citizen_data.get('id')}"
            )
            print(
                f"📤 [RabbitMQ] Published unregister.citizen.requested for citizen {citizen_data.get('id')}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish unregister.citizen.requested event: {str(e)}")
            # Try to reconnect for next time
            self._close()
            return False

        except Exception as e:
            logger.error(f"Failed to publish documents.download.requested event: {str(e)}")
            # Try to reconnect for next time
            self._close()
            return False

    def _close(self):
        """Close the RabbitMQ connection."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {str(e)}")
        finally:
            self.connection = None
            self.channel = None

    def __del__(self):
        """Cleanup on object destruction."""
        self._close()


# Global publisher instance
_publisher = None


def get_publisher() -> RabbitMQPublisher:
    """Get or create the global publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = RabbitMQPublisher()
    return _publisher


def publish_affiliation_created(id_citizen: int) -> bool:
    """
    Publish an affiliation.created event to RabbitMQ.

    Args:
        id_citizen: The citizen ID that was affiliated

    Returns:
        bool: True if successful, False otherwise
    """
    publisher = get_publisher()
    return publisher.publish_affiliation_created(id_citizen)


def publish_user_transferred(id_citizen: int) -> bool:
    """
    Publish a user.transferred event to RabbitMQ.

    Args:
        id_citizen: The citizen ID that was transferred

    Returns:
        bool: True if successful, False otherwise
    """
    publisher = get_publisher()
    return publisher.publish_user_transferred(id_citizen)


def publish_documents_download_requested(id_citizen: int, url_documents: dict) -> bool:
    """
    Publish a documents.download.requested event to RabbitMQ for Document Service.

    Args:
        id_citizen: The citizen ID
        url_documents: Dictionary of document URLs to download

    Returns:
        bool: True if successful, False otherwise
    """
    publisher = get_publisher()
    return publisher.publish_documents_download_requested(id_citizen, url_documents)


def publish_register_citizen_requested(citizen_data: dict) -> bool:
    """
    Publish a register.citizen.requested event to RabbitMQ for Operator Connectivity.
    This will be consumed by Operator Connectivity to call POST /apis/registerCitizen.

    Args:
        citizen_data: Dictionary containing:
            - id: Citizen ID (document number)
            - name: Citizen full name
            - address: Citizen address
            - email: Citizen email
            - operatorId: Current operator ID
            - operatorName: Current operator name

    Returns:
        bool: True if successful, False otherwise
    """
    publisher = get_publisher()
    return publisher.publish_register_citizen_requested(citizen_data)


def publish_unregister_citizen_requested(citizen_data: dict) -> bool:
    """
    Publish an unregister.citizen.requested event to RabbitMQ for Operator Connectivity.
    This will be consumed by Operator Connectivity to call DELETE /apis/unregisterCitizen.

    Args:
        citizen_data: Dictionary containing:
            - id: Citizen ID (document number)
            - operatorId: Current operator ID
            - operatorName: Current operator name

    Returns:
        bool: True if successful, False otherwise
    """
    publisher = get_publisher()
    return publisher.publish_unregister_citizen_requested(citizen_data)
