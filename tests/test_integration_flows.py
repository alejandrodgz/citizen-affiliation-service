"""
Integration tests for complete citizen affiliation and transfer flows.
"""

import pytest
from unittest.mock import patch, Mock
from rest_framework.test import APIClient
from affiliation.models.citizen import Citizen
from affiliation.models.affiliation import Affiliation
from affiliation.services.citizen_service import CitizenService
from affiliation.services.transfer_service import TransferService


@pytest.mark.django_db
class TestFullRegistrationFlow:
    """Integration tests for complete citizen registration flow."""

    def setup_method(self):
        """Set up test dependencies."""
        self.client = APIClient()
        self.citizen_service = CitizenService()

    @patch("affiliation.services.citizen_service.publish_event")
    @patch("affiliation.rabbitmq.register_citizen_consumer.publish_event")
    def test_complete_registration_flow(self, mock_consumer_publish, mock_service_publish):
        """Test complete flow: Register → MINTIC Verify → Affiliate."""
        from affiliation.rabbitmq.register_citizen_consumer import handle_register_citizen_completed

        # Step 1: Register citizen
        citizen_data = {
            "id": "1234567890",
            "name": "Integration Test User",
            "address": "Test Street 123",
            "email": "integration@test.com",
            "operator_id": "test_operator_123",
            "operator_name": "Test Operator",
        }

        result = self.citizen_service.register_citizen(citizen_data)
        assert result["success"] is True

        # Verify citizen created with pending status
        citizen = Citizen.objects.get(id=citizen_data["id"])
        assert citizen.is_verified is False
        assert citizen.verification_status == "pending"

        affiliation = Affiliation.objects.get(citizen=citizen)
        assert affiliation.status == "PENDING"

        # Step 2: Simulate MINTIC verification success
        event_data = {"id": citizen_data["id"], "statusCode": 201}

        handle_register_citizen_completed(event_data)

        # Step 3: Verify final state
        citizen.refresh_from_db()
        assert citizen.is_verified is True
        assert citizen.verification_status == "verified"

        affiliation.refresh_from_db()
        assert affiliation.status == "AFFILIATED"


@pytest.mark.django_db
class TestFullOutgoingTransferFlow:
    """Integration tests for complete outgoing transfer flow."""

    def setup_method(self):
        """Set up test dependencies."""
        self.transfer_service = TransferService()

    @patch("affiliation.services.transfer_service.requests.post")
    @patch("affiliation.services.transfer_service.requests.get")
    @patch("affiliation.services.transfer_service.publish_event")
    @patch("affiliation.rabbitmq.unregister_citizen_consumer.publish_event")
    def test_complete_outgoing_transfer(
        self, mock_consumer_publish, mock_service_publish, mock_get, mock_post, affiliated_citizen
    ):
        """Test complete flow: Initiate Transfer → Unregister → Send to Operator → Confirm → Delete."""
        from affiliation.rabbitmq.unregister_citizen_consumer import (
            handle_unregister_citizen_completed,
        )

        citizen, affiliation = affiliated_citizen
        citizen_id = citizen.id

        # Step 1: Initiate transfer
        target_operator = {
            "targetOperatorId": "target_999",
            "targetOperatorName": "Target Operator",
            "targetApiUrl": "https://target-operator.com/api/transfer/receive/",
        }

        result = self.transfer_service.send_transfer(citizen_id, target_operator)
        assert result["success"] is True

        # Verify status changed to TRANSFERRING
        affiliation.refresh_from_db()
        assert affiliation.status == "TRANSFERRING"
        assert affiliation.transfer_destination_api_url == target_operator["targetApiUrl"]

        # Step 2: Simulate MINTIC unregister confirmation
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "document_id": "https://storage.com/id.pdf",
            "document_rut": "https://storage.com/rut.pdf",
        }

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"message": "Transfer received"}

        unregister_event = {"id": citizen_id, "success": True}

        handle_unregister_citizen_completed(unregister_event)

        # Verify external operator was called
        assert mock_post.called
        call_args = mock_post.call_args
        assert target_operator["targetApiUrl"] in call_args[0]

        # Step 3: Simulate target operator confirmation
        result = self.transfer_service.handle_transfer_confirmation(citizen_id, req_status=1)
        assert result["success"] is True

        # Step 4: Verify cleanup
        assert not Citizen.objects.filter(id=citizen_id).exists()
        assert not Affiliation.objects.filter(citizen_id=citizen_id).exists()


@pytest.mark.django_db
class TestFullIncomingTransferFlow:
    """Integration tests for complete incoming transfer flow."""

    def setup_method(self):
        """Set up test dependencies."""
        self.transfer_service = TransferService()

    @patch("affiliation.services.transfer_service.requests.post")
    @patch("affiliation.services.transfer_service.publish_event")
    @patch("affiliation.rabbitmq.register_citizen_consumer.publish_event")
    @patch("affiliation.rabbitmq.documents_ready_consumer.requests.post")
    def test_complete_incoming_transfer(
        self, mock_doc_post, mock_reg_publish, mock_transfer_publish, mock_confirmation_post
    ):
        """Test complete flow: Receive Transfer → Register → Documents Ready → Confirm."""
        from affiliation.rabbitmq.register_citizen_consumer import handle_register_citizen_completed
        from affiliation.rabbitmq.documents_ready_consumer import handle_documents_ready

        # Step 1: Receive transfer from source operator
        transfer_data = {
            "id": 9876543210,
            "citizenName": "Transferred User",
            "citizenEmail": "transferred@example.com",
            "urlDocuments": {
                "document_id": "https://source.com/doc1.pdf",
                "document_rut": "https://source.com/doc2.pdf",
            },
            "confirmAPI": "https://source-operator.com/api/confirm/",
            "sourceOperatorId": "source_op_123",
            "sourceOperatorName": "Source Operator",
        }

        result = self.transfer_service.receive_transfer(transfer_data)
        assert result["success"] is True

        citizen_id = str(transfer_data["id"])

        # Verify citizen created
        citizen = Citizen.objects.get(id=citizen_id)
        assert citizen.is_verified is False

        affiliation = Affiliation.objects.get(citizen=citizen)
        assert affiliation.status == "PENDING"
        assert affiliation.confirmation_callback_url == transfer_data["confirmAPI"]

        # Step 2: Simulate MINTIC registration success
        register_event = {"id": citizen_id, "statusCode": 201}

        handle_register_citizen_completed(register_event)

        citizen.refresh_from_db()
        assert citizen.is_verified is True

        # Step 3: Simulate documents ready event
        mock_confirmation_post.return_value.status_code = 200

        documents_event = {"citizenId": citizen_id}

        handle_documents_ready(documents_event)

        # Step 4: Verify final state
        affiliation.refresh_from_db()
        assert affiliation.status == "AFFILIATED"

        # Verify confirmation was sent to source operator
        assert mock_confirmation_post.called
        call_args = mock_confirmation_post.call_args
        assert transfer_data["confirmAPI"] in call_args[0]


@pytest.mark.django_db
class TestTransferFailureRollback:
    """Integration tests for transfer failure scenarios."""

    def setup_method(self):
        """Set up test dependencies."""
        self.transfer_service = TransferService()

    @patch("affiliation.services.transfer_service.requests.post")
    @patch("affiliation.services.transfer_service.requests.get")
    def test_outgoing_transfer_external_api_failure_rollback(
        self, mock_get, mock_post, transferring_citizen
    ):
        """Test rollback when external operator API fails."""
        citizen, affiliation = transferring_citizen

        # Mock document service success
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {}

        # Mock external operator failure
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Internal Server Error"

        # Attempt to continue transfer
        result = self.transfer_service.continue_transfer_after_unregister(citizen.id)

        assert result["success"] is False

        # Verify affiliation rolled back to AFFILIATED
        affiliation.refresh_from_db()
        assert affiliation.status == "AFFILIATED"

        # Verify citizen still exists
        assert Citizen.objects.filter(id=citizen.id).exists()

    def test_outgoing_transfer_confirmation_failure_rollback(self, transferring_citizen):
        """Test rollback when target operator rejects transfer."""
        citizen, affiliation = transferring_citizen

        # Target operator sends failure confirmation
        result = self.transfer_service.handle_transfer_confirmation(citizen.id, req_status=0)

        assert result["success"] is True
        assert "rolled back" in result["message"].lower()

        # Verify affiliation rolled back
        affiliation.refresh_from_db()
        assert affiliation.status == "AFFILIATED"
        assert affiliation.transfer_destination_operator_id is None

        # Verify citizen still exists
        assert Citizen.objects.filter(id=citizen.id).exists()


@pytest.mark.django_db
class TestConcurrentTransferAttempts:
    """Integration tests for concurrent transfer scenarios."""

    def setup_method(self):
        """Set up test dependencies."""
        self.transfer_service = TransferService()

    @patch("affiliation.services.transfer_service.publish_event")
    def test_prevent_multiple_simultaneous_transfers(self, mock_publish, affiliated_citizen):
        """Test that multiple transfer attempts are prevented."""
        citizen, affiliation = affiliated_citizen

        target_operator_1 = {
            "targetOperatorId": "target_1",
            "targetOperatorName": "Target 1",
            "targetApiUrl": "https://target1.com/api/transfer/",
        }

        target_operator_2 = {
            "targetOperatorId": "target_2",
            "targetOperatorName": "Target 2",
            "targetApiUrl": "https://target2.com/api/transfer/",
        }

        # First transfer should succeed
        result1 = self.transfer_service.send_transfer(citizen.id, target_operator_1)
        assert result1["success"] is True

        # Second transfer should fail
        result2 = self.transfer_service.send_transfer(citizen.id, target_operator_2)
        assert result2["success"] is False
        assert "already transferring" in result2["message"].lower()

        # Verify first transfer info is preserved
        affiliation.refresh_from_db()
        assert affiliation.transfer_destination_operator_id == target_operator_1["targetOperatorId"]


@pytest.mark.django_db
class TestAPIIntegrationFlow:
    """Integration tests using API endpoints."""

    def setup_method(self):
        """Set up test client."""
        self.client = APIClient()

    @patch("affiliation.services.citizen_service.publish_event")
    @patch("affiliation.services.transfer_service.publish_event")
    @patch("affiliation.services.transfer_service.requests.post")
    @patch("affiliation.services.transfer_service.requests.get")
    def test_full_flow_via_api_endpoints(
        self, mock_get, mock_post, mock_transfer_publish, mock_citizen_publish
    ):
        """Test complete flow using only API endpoints."""
        from django.urls import reverse

        # Step 1: Register citizen via API
        register_url = reverse("register-citizen")
        register_data = {
            "id": "5555555555",
            "name": "API Test User",
            "address": "API Street 456",
            "email": "apitest@example.com",
            "operator_id": "api_operator_123",
            "operator_name": "API Operator",
        }

        response = self.client.post(register_url, register_data, format="json")
        assert response.status_code == 200

        # Step 2: Check affiliation status via API
        status_url = reverse("affiliation-status", kwargs={"citizen_id": "5555555555"})

        # After MINTIC verification (simulated by updating DB directly)
        citizen = Citizen.objects.get(id="5555555555")
        citizen.is_verified = True
        citizen.verification_status = "verified"
        citizen.save()

        affiliation = Affiliation.objects.get(citizen=citizen)
        affiliation.status = "AFFILIATED"
        affiliation.save()

        response = self.client.get(status_url)
        assert response.status_code == 200
        assert response.data["status"] == "AFFILIATED"

        # Step 3: Initiate transfer via API
        transfer_url = reverse("transfer-send", kwargs={"citizen_id": "5555555555"})
        transfer_data = {
            "targetOperatorId": "api_target_999",
            "targetOperatorName": "API Target Operator",
            "targetApiUrl": "https://api-target.com/api/transfer/",
        }

        response = self.client.post(transfer_url, transfer_data, format="json")
        assert response.status_code == 200

        # Verify status changed
        response = self.client.get(status_url)
        assert response.data["status"] == "TRANSFERRING"

        # Step 4: Simulate external operator confirmation via API
        mock_post.return_value.status_code = 200
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {}

        confirm_url = reverse("transfer-confirm")
        confirm_data = {"id": "5555555555", "req_status": 1}

        response = self.client.post(confirm_url, confirm_data, format="json")
        assert response.status_code == 200

        # Step 5: Verify citizen deleted
        response = self.client.get(status_url)
        assert response.status_code == 404
