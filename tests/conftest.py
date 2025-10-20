"""
Pytest configuration and shared fixtures for the test suite.
"""

import pytest
from unittest.mock import Mock, MagicMock
from django.contrib.auth.models import User
from affiliation.models.citizen import Citizen
from affiliation.models.affiliation import Affiliation


@pytest.fixture
def mock_rabbitmq_publisher(mocker):
    """Mock RabbitMQ publisher to avoid actual message publishing in tests."""
    # Mock all the specific publisher functions
    mock_affiliation_created = mocker.patch(
        "affiliation.rabbitmq.publisher.publish_affiliation_created", return_value=True
    )
    mock_user_transferred = mocker.patch(
        "affiliation.rabbitmq.publisher.publish_user_transferred", return_value=True
    )
    mock_documents_download = mocker.patch(
        "affiliation.rabbitmq.publisher.publish_documents_download_requested", return_value=True
    )
    mock_register_requested = mocker.patch(
        "affiliation.rabbitmq.publisher.publish_register_citizen_requested", return_value=True
    )
    mock_unregister_requested = mocker.patch(
        "affiliation.rabbitmq.publisher.publish_unregister_citizen_requested", return_value=True
    )

    return {
        "affiliation_created": mock_affiliation_created,
        "user_transferred": mock_user_transferred,
        "documents_download": mock_documents_download,
        "register_requested": mock_register_requested,
        "unregister_requested": mock_unregister_requested,
    }


@pytest.fixture
def mock_requests_get(mocker):
    """Mock requests.get for external API calls."""
    return mocker.patch("requests.get")


@pytest.fixture
def mock_requests_post(mocker):
    """Mock requests.post for external API calls."""
    return mocker.patch("requests.post")


@pytest.fixture
def sample_citizen_data():
    """Sample citizen data for testing."""
    return {
        "id": "1234567890",
        "name": "John Doe",
        "address": "Calle 123 #45-67",
        "email": "john.doe@example.com",
    }


@pytest.fixture
def sample_operator_data():
    """Sample operator data for testing."""
    return {"operator_id": "507f1f77bcf86cd799439011", "operator_name": "Test Operator"}


@pytest.fixture
def sample_transfer_data(sample_citizen_data, sample_operator_data):
    """Sample transfer data for incoming transfers."""
    return {
        "id": int(sample_citizen_data["id"]),
        "citizenName": sample_citizen_data["name"],
        "citizenEmail": sample_citizen_data["email"],
        "urlDocuments": {
            "document_id": "https://example.com/doc/123",
            "document_rut": "https://example.com/doc/456",
        },
        "confirmAPI": "https://source-operator.com/api/confirm/",
        "sourceOperatorId": sample_operator_data["operator_id"],
        "sourceOperatorName": sample_operator_data["operator_name"],
    }


@pytest.fixture
def sample_target_operator():
    """Sample target operator for outgoing transfers."""
    return {
        "targetOperatorId": "target_operator_999",
        "targetOperatorName": "Target Operator ABC",
        "targetApiUrl": "https://target-operator.com/api/transfer/receive/",
    }


@pytest.fixture
@pytest.mark.django_db
def create_citizen(db, sample_citizen_data, sample_operator_data):
    """Factory fixture to create a test citizen."""

    def _create_citizen(**kwargs):
        citizen_data = {**sample_citizen_data, **sample_operator_data, **kwargs}
        # Map 'id' to 'citizen_id'
        if "id" in citizen_data and "citizen_id" not in citizen_data:
            citizen_data["citizen_id"] = citizen_data.pop("id")

        citizen = Citizen.objects.create(
            citizen_id=citizen_data["citizen_id"],
            name=citizen_data["name"],
            address=citizen_data.get("address", "Default Address"),
            email=citizen_data["email"],
            operator_id=citizen_data["operator_id"],
            operator_name=citizen_data["operator_name"],
            is_registered=citizen_data.get("is_registered", True),
            is_verified=citizen_data.get("is_verified", False),
            verification_status=citizen_data.get("verification_status", "pending"),
        )
        return citizen

    return _create_citizen


@pytest.fixture
@pytest.mark.django_db
def create_affiliation(db, sample_operator_data):
    """Factory fixture to create a test affiliation."""

    def _create_affiliation(citizen, **kwargs):
        affiliation_data = {**sample_operator_data, **kwargs}
        affiliation = Affiliation.objects.create(
            citizen=citizen,
            operator_id=affiliation_data.get("operator_id"),
            operator_name=affiliation_data.get("operator_name"),
            status=affiliation_data.get("status", "AFFILIATED"),
            transfer_destination_operator_id=affiliation_data.get(
                "transfer_destination_operator_id"
            ),
            transfer_destination_operator_name=affiliation_data.get(
                "transfer_destination_operator_name"
            ),
            transfer_destination_api_url=affiliation_data.get("transfer_destination_api_url"),
            transfer_started_at=affiliation_data.get("transfer_started_at"),
        )
        return affiliation

    return _create_affiliation


@pytest.fixture
@pytest.mark.django_db
def affiliated_citizen(create_citizen, create_affiliation):
    """Create a fully affiliated citizen for testing."""
    citizen = create_citizen(is_verified=True, verification_status="verified")
    affiliation = create_affiliation(citizen)
    return citizen, affiliation


@pytest.fixture
@pytest.mark.django_db
def transferring_citizen(create_citizen, create_affiliation):
    """Create a citizen in TRANSFERRING state for testing."""
    citizen = create_citizen(is_verified=True, verification_status="verified")
    affiliation = create_affiliation(
        citizen,
        status="TRANSFERRING",
        transfer_destination_operator_id="target_999",
        transfer_destination_operator_name="Target Operator",
        transfer_destination_api_url="https://target.com/api/transfer/",
    )
    return citizen, affiliation


@pytest.fixture
def mock_mintic_validation_success(mock_requests_get):
    """Mock successful MINTIC citizen validation."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "El ciudadano con id: 1234567890 se encuentra registrado"
    mock_requests_get.return_value = mock_response
    return mock_requests_get


@pytest.fixture
def mock_mintic_validation_not_found(mock_requests_get):
    """Mock MINTIC citizen not found."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.text = "Ciudadano no encontrado"
    mock_requests_get.return_value = mock_response
    return mock_requests_get


@pytest.fixture
def mock_document_service_success(mock_requests_get):
    """Mock successful document service response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "document_id": "https://storage.example.com/docs/id_123.pdf",
        "document_rut": "https://storage.example.com/docs/rut_123.pdf",
    }
    mock_requests_get.return_value = mock_response
    return mock_requests_get


@pytest.fixture
def mock_external_operator_success(mock_requests_post):
    """Mock successful external operator API response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": "Transfer received successfully",
        "citizenId": "1234567890",
    }
    mock_requests_post.return_value = mock_response
    return mock_requests_post


@pytest.fixture
def mock_pika_connection(mocker):
    """Mock pika RabbitMQ connection."""
    mock_connection = MagicMock()
    mock_channel = MagicMock()
    mock_connection.channel.return_value = mock_channel

    mocker.patch("pika.BlockingConnection", return_value=mock_connection)
    return mock_connection, mock_channel
