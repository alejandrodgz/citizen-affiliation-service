"""
API endpoint tests for citizen affiliation service.
"""

import pytest
import json
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
from affiliation.models.citizen import Citizen
from affiliation.models.affiliation import Affiliation


@pytest.mark.django_db
class TestCitizenRegistrationAPI:
    """Test cases for citizen registration endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()
        self.url = reverse("register-citizen")

    @patch("affiliation.rabbitmq.publisher.publish_register_citizen_requested")
    @patch("affiliation.services.citizen_service.requests.get")
    def test_register_citizen_success(
        self, mock_get, mock_publish, sample_citizen_data, sample_operator_data
    ):
        """Test successful citizen registration via API."""
        # Mock validation to return citizen doesn't exist
        mock_get.return_value.status_code = 404
        mock_publish.return_value = True

        data = {**sample_citizen_data, **sample_operator_data}

        response = self.client.post(self.url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "message" in response.data

        # Verify citizen was created with correct field name
        assert Citizen.objects.filter(citizen_id=sample_citizen_data["id"]).exists()

    def test_register_citizen_missing_fields(self):
        """Test registration with missing required fields."""
        data = {
            "id": "1234567890",
            "name": "Test User",
            # Missing email, address, operator_id
        }

        response = self.client.post(self.url, data, format="json")

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    @patch("affiliation.rabbitmq.publisher.publish_register_citizen_requested")
    @patch("affiliation.services.citizen_service.requests.get")
    def test_register_citizen_duplicate(
        self, mock_get, mock_publish, create_citizen, sample_citizen_data, sample_operator_data
    ):
        """Test registering duplicate citizen."""
        # Create existing citizen with verified status
        create_citizen(
            citizen_id=sample_citizen_data["id"], is_verified=True, verification_status="verified"
        )

        # Mock validation
        mock_get.return_value.status_code = 404
        mock_publish.return_value = True

        data = {**sample_citizen_data, **sample_operator_data}
        response = self.client.post(self.url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestCitizenValidationAPI:
    """Test cases for citizen validation endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()

    @patch("affiliation.services.citizen_service.requests.get")
    def test_validate_citizen_exists(self, mock_get):
        """Test validating existing citizen."""
        citizen_id = "1234567890"
        url = reverse("validate-citizen", kwargs={"citizen_id": citizen_id})

        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "El ciudadano se encuentra registrado"

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

    @patch("affiliation.services.citizen_service.requests.get")
    def test_validate_citizen_not_found(self, mock_get):
        """Test validating non-existent citizen."""
        citizen_id = "9999999999"
        url = reverse("validate-citizen", kwargs={"citizen_id": citizen_id})

        mock_get.return_value.status_code = 404

        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAffiliationStatusAPI:
    """Test cases for affiliation status endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()

    def test_get_affiliation_status_success(self, affiliated_citizen):
        """Test getting affiliation status."""
        citizen, affiliation = affiliated_citizen
        url = reverse("affiliation-status", kwargs={"citizen_id": citizen.citizen_id})

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["citizen_id"] == citizen.citizen_id
        assert response.data["status"] == "AFFILIATED"
        assert response.data["operator_id"] == affiliation.operator_id

    def test_get_affiliation_status_not_found(self):
        """Test getting status for non-existent citizen."""
        url = reverse("affiliation-status", kwargs={"citizen_id": "9999999999"})

        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestTransferSendAPI:
    """Test cases for sending transfer endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()

    @patch("affiliation.rabbitmq.publisher.publish_unregister_citizen_requested")
    def test_send_transfer_success(self, mock_publish, affiliated_citizen, sample_target_operator):
        """Test initiating outgoing transfer."""
        citizen, affiliation = affiliated_citizen
        url = reverse("transfer-send", kwargs={"citizen_id": citizen.citizen_id})

        mock_publish.return_value = True
        response = self.client.post(url, sample_target_operator, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

        # Verify affiliation status changed
        affiliation.refresh_from_db()
        assert affiliation.status == "TRANSFERRING"

    @patch("affiliation.rabbitmq.publisher.publish_unregister_citizen_requested")
    def test_send_transfer_citizen_not_found(self, mock_publish, sample_target_operator):
        """Test transfer for non-existent citizen."""
        mock_publish.return_value = True
        url = reverse("transfer-send", kwargs={"citizen_id": "9999999999"})

        response = self.client.post(url, sample_target_operator, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_transfer_missing_fields(self, affiliated_citizen):
        """Test transfer with missing required fields."""
        citizen, _ = affiliated_citizen
        url = reverse("transfer-send", kwargs={"citizen_id": citizen.citizen_id})

        data = {
            "targetOperatorId": "target_123"
            # Missing targetOperatorName and targetApiUrl
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTransferReceiveAPI:
    """Test cases for receiving transfer endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()
        self.url = reverse("transfer-receive")

    @patch("affiliation.rabbitmq.publisher.publish_register_citizen_requested")
    def test_receive_transfer_success(self, mock_publish, sample_transfer_data):
        """Test receiving incoming transfer."""
        mock_publish.return_value = True
        response = self.client.post(self.url, sample_transfer_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        # Verify citizen was created with correct field name
        citizen_id = str(sample_transfer_data["id"])
        assert Citizen.objects.filter(citizen_id=citizen_id).exists()

        # Verify affiliation was created with callback URL
        citizen = Citizen.objects.get(citizen_id=citizen_id)
        affiliation = Affiliation.objects.get(citizen=citizen)
        assert affiliation.transfer_confirmation_url == sample_transfer_data["confirmAPI"]

    @patch("affiliation.rabbitmq.publisher.publish_register_citizen_requested")
    def test_receive_transfer_duplicate(self, mock_publish, create_citizen, sample_transfer_data):
        """Test receiving transfer for existing citizen."""
        # Create existing citizen with verified status
        create_citizen(citizen_id=str(sample_transfer_data["id"]), is_verified=True)
        mock_publish.return_value = True

        response = self.client.post(self.url, sample_transfer_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTransferConfirmAPI:
    """Test cases for transfer confirmation endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()
        self.url = reverse("transfer-confirm")

    @patch("affiliation.rabbitmq.publisher.publish_user_transferred")
    def test_confirm_transfer_success(self, mock_publish, transferring_citizen):
        """Test successful transfer confirmation."""
        citizen, affiliation = transferring_citizen
        mock_publish.return_value = True

        data = {"id": citizen.citizen_id, "req_status": 1}  # Success

        response = self.client.post(self.url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

        # Verify citizen was deleted
        assert not Citizen.objects.filter(citizen_id=citizen.citizen_id).exists()

    @patch("affiliation.rabbitmq.publisher.publish_user_transferred")
    def test_confirm_transfer_failure(self, mock_publish, transferring_citizen):
        """Test failed transfer confirmation."""
        citizen, affiliation = transferring_citizen
        mock_publish.return_value = True

        data = {"id": citizen.citizen_id, "req_status": 0}  # Failure

        response = self.client.post(self.url, data, format="json")

        # Service returns 400 for failed confirmation
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify citizen still exists
        assert Citizen.objects.filter(citizen_id=citizen.citizen_id).exists()

        # Verify affiliation rolled back
        affiliation.refresh_from_db()
        assert affiliation.status == "AFFILIATED"

    def test_confirm_transfer_citizen_not_found(self):
        """Test confirmation for non-existent citizen."""
        data = {"id": "9999999999", "req_status": 1}

        response = self.client.post(self.url, data, format="json")

        # Service returns 400 for unknown citizen
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeleteAffiliationAPI:
    """Test cases for delete affiliation endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()

    @patch("affiliation.rabbitmq.publisher.publish_unregister_citizen_requested")
    @patch("affiliation.rabbitmq.publisher.publish_user_transferred")
    def test_delete_affiliation_success(
        self, mock_transferred, mock_unregister, affiliated_citizen
    ):
        """Test successful affiliation deletion."""
        citizen, affiliation = affiliated_citizen
        url = reverse("affiliation-delete", kwargs={"citizen_id": citizen.citizen_id})
        citizen_id = citizen.citizen_id

        mock_transferred.return_value = True
        mock_unregister.return_value = True

        response = self.client.delete(url)

        assert response.status_code == status.HTTP_200_OK

        # Citizen should be marked for deletion, not immediately deleted
        # (actual deletion happens after unregister event confirmation)

    def test_delete_affiliation_not_found(self):
        """Test deleting non-existent affiliation."""
        url = reverse("affiliation-delete", kwargs={"citizen_id": "9999999999"})

        response = self.client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestOperatorsListAPI:
    """Test cases for operators list endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()
        self.url = reverse("operators-list")

    @patch("affiliation.services.citizen_service.requests.get")
    def test_get_operators_success(self, mock_get):
        """Test getting operators list."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"id": "op1", "name": "Operator 1"},
            {"id": "op2", "name": "Operator 2"},
        ]

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["operators"]) == 2
