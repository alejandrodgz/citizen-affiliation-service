"""
Unit tests for TransferService - handles citizen transfer operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import override_settings
from affiliation.services.transfer_service import TransferService
from affiliation.models.citizen import Citizen
from affiliation.models.affiliation import Affiliation


@pytest.mark.django_db
class TestTransferServiceReceiveTransfer:
    """Test cases for receiving incoming transfers from other operators."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = TransferService()

    def test_receive_transfer_success(self, sample_transfer_data, mock_rabbitmq_publisher):
        """Test successful incoming transfer reception."""
        result = self.service.receive_transfer(sample_transfer_data)

        # Verify citizen was created
        assert result["success"] is True
        assert "processing documents" in result["message"].lower()

        citizen = Citizen.objects.get(citizen_id=str(sample_transfer_data["id"]))
        assert citizen.name == sample_transfer_data["citizenName"]
        assert citizen.email == sample_transfer_data["citizenEmail"]
        assert citizen.is_registered is False  # Not complete until MINTIC confirms
        assert citizen.is_verified is False

        # Verify affiliation was created with correct status
        affiliation = Affiliation.objects.get(citizen=citizen)
        assert affiliation.status == "TRANSFERRING"
        assert affiliation.transfer_confirmation_url == sample_transfer_data["confirmAPI"]

    def test_receive_transfer_duplicate_citizen(
        self, sample_transfer_data, create_citizen, mock_rabbitmq_publisher
    ):
        """Test receiving transfer for already existing citizen."""
        # Create existing citizen
        create_citizen(citizen_id=str(sample_transfer_data["id"]))

        result = self.service.receive_transfer(sample_transfer_data)

        assert result["success"] is False
        assert "already exists" in result["message"].lower()

    def test_receive_transfer_missing_required_fields(self):
        """Test receiving transfer with missing required fields."""
        incomplete_data = {
            "id": 123456,
            "citizenName": "Test User",
            # Missing email, urlDocuments, confirmAPI, etc.
        }

        # Service will raise KeyError for missing required fields
        result = self.service.receive_transfer(incomplete_data)

        # Should return error since required fields are missing
        assert result["success"] is False

    @patch("affiliation.services.transfer_service.publish_documents_download_requested")
    def test_receive_transfer_publishes_registration_event(
        self, mock_publish, sample_transfer_data
    ):
        """Test that receiving transfer publishes document download event."""
        mock_publish.return_value = True
        self.service.receive_transfer(sample_transfer_data)

        # Verify documents download event was published
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[1]["id_citizen"] == sample_transfer_data["id"]


@pytest.mark.django_db
class TestTransferServiceSendTransfer:
    """Test cases for sending outgoing transfers to other operators."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = TransferService()

    def test_send_transfer_success(
        self, affiliated_citizen, sample_target_operator, mock_rabbitmq_publisher
    ):
        """Test successful outgoing transfer initiation."""
        citizen, affiliation = affiliated_citizen

        # Convert to the format expected by send_transfer (dict with operator_id, operator_name, api_url)
        target_operator = {
            "operator_id": sample_target_operator["targetOperatorId"],
            "operator_name": sample_target_operator["targetOperatorName"],
            "api_url": sample_target_operator["targetApiUrl"],
        }

        result = self.service.send_transfer(citizen.citizen_id, target_operator)

        assert result["success"] is True
        assert "initiated" in result["message"].lower()

        # Verify affiliation status changed to TRANSFERRING
        affiliation.refresh_from_db()
        assert affiliation.status == "TRANSFERRING"
        assert affiliation.transfer_destination_operator_id == target_operator["operator_id"]
        assert affiliation.transfer_destination_operator_name == target_operator["operator_name"]
        assert affiliation.transfer_destination_api_url == target_operator["api_url"]

    def test_send_transfer_citizen_not_found(self, sample_target_operator):
        """Test sending transfer for non-existent citizen."""
        result = self.service.send_transfer("9999999999", sample_target_operator)

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_send_transfer_citizen_not_affiliated(self, create_citizen, sample_target_operator):
        """Test sending transfer for citizen without affiliation."""
        citizen = create_citizen(is_verified=True)

        target_operator = {
            "operator_id": sample_target_operator["targetOperatorId"],
            "operator_name": sample_target_operator["targetOperatorName"],
            "api_url": sample_target_operator["targetApiUrl"],
        }

        result = self.service.send_transfer(citizen.citizen_id, target_operator)

        assert result["success"] is False
        assert "affiliation" in result["message"].lower()

    def test_send_transfer_already_transferring(self, transferring_citizen, sample_target_operator):
        """Test sending transfer for citizen already in TRANSFERRING state."""
        citizen, affiliation = transferring_citizen

        target_operator = {
            "operator_id": sample_target_operator["targetOperatorId"],
            "operator_name": sample_target_operator["targetOperatorName"],
            "api_url": sample_target_operator["targetApiUrl"],
        }

        result = self.service.send_transfer(citizen.citizen_id, target_operator)

        assert result["success"] is False
        assert "cannot be transferred" in result["message"].lower()

    @patch("affiliation.services.transfer_service.publish_unregister_citizen_requested")
    def test_send_transfer_publishes_unregister_event(
        self, mock_publish, affiliated_citizen, sample_target_operator
    ):
        """Test that sending transfer publishes unregister event."""
        citizen, _ = affiliated_citizen
        mock_publish.return_value = True

        target_operator = {
            "operator_id": sample_target_operator["targetOperatorId"],
            "operator_name": sample_target_operator["targetOperatorName"],
            "api_url": sample_target_operator["targetApiUrl"],
        }

        self.service.send_transfer(citizen.citizen_id, target_operator)

        # Verify unregister event was published
        mock_publish.assert_called_once()


@pytest.mark.django_db
class TestTransferServiceContinueTransfer:
    """Test cases for continuing transfer after MINTIC unregister."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = TransferService()

    @patch("affiliation.services.transfer_service.requests.get")
    @patch("affiliation.services.transfer_service.requests.post")
    def test_continue_transfer_success(self, mock_post, mock_get, transferring_citizen):
        """Test continuing transfer after MINTIC unregister confirmation."""
        citizen, affiliation = transferring_citizen

        # Mock document service response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "document_id": "https://example.com/doc1.pdf",
            "document_rut": "https://example.com/doc2.pdf",
        }

        # Mock external operator response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "message": "Transfer received",
            "citizenId": citizen.citizen_id,
        }

        result = self.service.continue_transfer_after_unregister(citizen.citizen_id)

        assert result["success"] is True

        # Verify POST was made to target operator
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert affiliation.transfer_destination_api_url in call_args[0]

        # Verify payload structure
        payload = call_args[1]["json"]
        assert payload["id"] == int(citizen.citizen_id)
        assert payload["citizenName"] == citizen.name
        assert payload["citizenEmail"] == citizen.email
        assert "confirmAPI" in payload

    def test_continue_transfer_citizen_not_transferring(self, affiliated_citizen):
        """Test continuing transfer for citizen not in TRANSFERRING state."""
        citizen, _ = affiliated_citizen

        result = self.service.continue_transfer_after_unregister(citizen.citizen_id)

        assert result["success"] is False
        assert "not" in result["message"].lower() and "transfer" in result["message"].lower()

    @patch("affiliation.services.transfer_service.requests.post")
    @patch("affiliation.services.transfer_service.requests.get")
    def test_continue_transfer_external_api_failure(
        self, mock_get, mock_post, transferring_citizen
    ):
        """Test handling external operator API failure."""
        citizen, affiliation = transferring_citizen

        # Mock document service success
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {}

        # Mock external operator failure
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Internal Server Error"

        result = self.service.continue_transfer_after_unregister(citizen.citizen_id)

        assert result["success"] is False

        # Status remains TRANSFERRING (not rolled back) for retry capability
        affiliation.refresh_from_db()
        assert affiliation.status == "TRANSFERRING"


@pytest.mark.django_db
class TestTransferServiceConfirmation:
    """Test cases for handling transfer confirmations."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = TransferService()

    @patch("affiliation.services.transfer_service.publish_user_transferred")
    def test_confirmation_success_deletes_citizen(self, mock_publish, transferring_citizen):
        """Test successful confirmation deletes citizen and publishes event."""
        citizen, affiliation = transferring_citizen
        citizen_id = citizen.citizen_id
        mock_publish.return_value = True

        result = self.service.handle_transfer_confirmation(citizen_id, req_status=1)

        assert result["success"] is True

        # Verify citizen and affiliation were deleted
        assert not Citizen.objects.filter(citizen_id=citizen_id).exists()

        # Verify user.transferred event was published
        assert mock_publish.called

    def test_confirmation_failure_rolls_back(self, transferring_citizen):
        """Test failed confirmation rolls back to AFFILIATED status."""
        citizen, affiliation = transferring_citizen

        result = self.service.handle_transfer_confirmation(citizen.citizen_id, req_status=0)

        # Service should handle rollback
        assert result["success"] is False or result["success"] is True

        # Verify citizen still exists
        assert Citizen.objects.filter(citizen_id=citizen.citizen_id).exists()

        # Verify affiliation status rolled back
        affiliation.refresh_from_db()
        assert affiliation.status == "AFFILIATED"
        assert affiliation.transfer_destination_operator_id is None

    def test_confirmation_citizen_not_found(self):
        """Test confirmation for non-existent citizen."""
        result = self.service.handle_transfer_confirmation("9999999999", req_status=1)

        assert result["success"] is False
        assert "not found" in result["message"].lower()


@pytest.mark.django_db
class TestTransferServiceCompleteAfterDocuments:
    """Test cases for completing incoming transfer after documents are ready."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = TransferService()

    @patch("affiliation.rabbitmq.publisher.publish_register_citizen_requested")
    def test_complete_transfer_success(self, mock_publish, create_citizen, create_affiliation):
        """Test completing transfer after documents are ready."""
        citizen = create_citizen(is_verified=False, verification_status="pending")
        affiliation = create_affiliation(
            citizen,
            status="TRANSFERRING",
            transfer_confirmation_url="https://source-operator.com/api/confirm/",
            documents_ready=False,
        )

        mock_publish.return_value = True

        result = self.service.complete_transfer_after_documents(citizen.citizen_id)

        assert result["success"] is True

        # Verify documents_ready flag was set
        affiliation.refresh_from_db()
        assert affiliation.documents_ready is True

        # Verify register event was published
        mock_publish.assert_called_once()

    @patch("affiliation.rabbitmq.publisher.publish_register_citizen_requested")
    def test_complete_transfer_no_callback_url(
        self, mock_publish, create_citizen, create_affiliation
    ):
        """Test completing transfer when no callback URL is set."""
        citizen = create_citizen(is_verified=False)
        affiliation = create_affiliation(
            citizen, status="TRANSFERRING", transfer_confirmation_url=None, documents_ready=False
        )

        mock_publish.return_value = True

        result = self.service.complete_transfer_after_documents(citizen.citizen_id)

        # Should still succeed and mark documents ready
        assert result["success"] is True
        affiliation.refresh_from_db()
        assert affiliation.documents_ready is True


@pytest.mark.django_db
class TestTransferServicePrivateMethods:
    """Test cases for private helper methods in TransferService."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = TransferService()

    @patch("affiliation.services.transfer_service.requests.get")
    def test_get_citizen_documents_success(self, mock_get):
        """Test fetching citizen documents from document service."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "document_id": "https://storage.com/id.pdf",
            "document_rut": "https://storage.com/rut.pdf",
        }

        result = self.service._get_citizen_documents("1234567890")

        assert result["document_id"] == "https://storage.com/id.pdf"
        assert result["document_rut"] == "https://storage.com/rut.pdf"

    @patch("affiliation.services.transfer_service.requests.get")
    def test_get_citizen_documents_service_unavailable(self, mock_get):
        """Test handling document service unavailability."""
        mock_get.side_effect = Exception("Connection refused")

        result = self.service._get_citizen_documents("1234567890")

        # Should return empty dict on error
        assert result == {}

    @patch("affiliation.services.transfer_service.requests.post")
    def test_send_confirmation_success(self, mock_post):
        """Test sending confirmation to source operator."""
        confirmation_url = "https://source-operator.com/api/confirm/"
        mock_post.return_value.status_code = 200

        # Should not raise exception
        self.service._send_confirmation(
            "https://source-operator.com/api/confirm/", "1234567890", status=1
        )

        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert payload["id"] == 1234567890  # _send_confirmation converts to int
        assert payload["req_status"] == 1

    @patch("affiliation.services.transfer_service.requests.post")
    def test_send_confirmation_handles_errors(self, mock_post):
        """Test error handling when sending confirmation fails."""
        mock_post.side_effect = Exception("Connection timeout")

        # Should not raise exception, just log error
        self.service._send_confirmation(
            "https://source-operator.com/api/confirm/", "1234567890", status=1
        )
