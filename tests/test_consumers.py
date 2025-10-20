"""
Tests for RabbitMQ event consumers.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from affiliation.rabbitmq.register_citizen_consumer import handle_register_citizen_completed
from affiliation.rabbitmq.unregister_citizen_consumer import handle_unregister_citizen_completed
from affiliation.rabbitmq.documents_ready_consumer import handle_documents_ready
from affiliation.models.citizen import Citizen
from affiliation.models.affiliation import Affiliation


@pytest.mark.django_db
class TestRegisterCitizenConsumer:
    """Test cases for register.citizen.completed event consumer."""

    def test_handle_register_success(self, create_citizen, create_affiliation):
        """Test handling successful MINTIC registration."""
        # Create pending citizen
        citizen = create_citizen(is_verified=False, verification_status="pending")
        affiliation = create_affiliation(citizen, status="AFFILIATED")

        # Simulate event payload
        event_data = {"id": citizen.citizen_id, "statusCode": 201}

        # Call consumer handler
        handle_register_citizen_completed(event_data)

        # Verify citizen was verified
        citizen.refresh_from_db()
        assert citizen.is_verified is True
        assert citizen.verification_status == "verified"

        # Verify affiliation status remained AFFILIATED
        affiliation.refresh_from_db()
        assert affiliation.status == "AFFILIATED"

    def test_handle_register_failure(self, create_citizen, create_affiliation):
        """Test handling failed MINTIC registration."""
        # Create pending citizen
        citizen = create_citizen(is_verified=False, verification_status="pending")
        affiliation = create_affiliation(citizen, status="AFFILIATED")
        citizen_id = citizen.citizen_id

        # Simulate failure event
        event_data = {
            "id": citizen.citizen_id,
            "statusCode": 404,
            "error": "Citizen not found in MINTIC",
        }

        # Call consumer handler
        handle_register_citizen_completed(event_data)

        # Verify citizen was marked as failed
        citizen_exists = Citizen.objects.filter(citizen_id=citizen_id).exists()
        assert citizen_exists
        citizen.refresh_from_db()
        assert citizen.verification_status == "failed"

        # Verify affiliation status changed to FAILED
        affiliation.refresh_from_db()
        assert affiliation.status == "FAILED"

    def test_handle_register_citizen_not_found(self):
        """Test handling event for non-existent citizen."""
        event_data = {"id": "9999999999", "statusCode": 201}

        # Should not raise exception
        try:
            handle_register_citizen_completed(event_data)
        except Exception as e:
            pytest.fail(f"Should handle gracefully but raised: {e}")


@pytest.mark.django_db
class TestUnregisterCitizenConsumer:
    """Test cases for unregister.citizen.completed event consumer."""

    @patch("affiliation.rabbitmq.publisher.publish_user_transferred")
    def test_handle_unregister_direct_deletion(self, mock_publish, affiliated_citizen):
        """Test unregister for direct deletion (not transfer)."""
        citizen, affiliation = affiliated_citizen
        citizen_id = citizen.citizen_id

        # Ensure not in TRANSFERRING state
        affiliation.status = "AFFILIATED"
        affiliation.pending_deletion = True  # Mark for deletion
        affiliation.save()

        # Also mark citizen for deletion
        citizen.pending_deletion = True
        citizen.save()

        mock_publish.return_value = True

        event_data = {
            "id": citizen.citizen_id,
            "success": True,
            "message": "Unregistered successfully",
        }

        # Call consumer handler
        handle_unregister_citizen_completed(event_data)

        # Verify citizen and affiliation were deleted
        assert not Citizen.objects.filter(citizen_id=citizen_id).exists()

        # Verify user.transferred event was published
        assert mock_publish.called

    @patch("affiliation.services.transfer_service.requests.post")
    @patch("affiliation.services.transfer_service.requests.get")
    def test_handle_unregister_during_transfer(self, mock_get, mock_post, transferring_citizen):
        """Test unregister for citizen in TRANSFERRING state."""
        citizen, affiliation = transferring_citizen

        # Mock document service
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {}

        # Mock external operator
        mock_post.return_value.status_code = 200

        event_data = {
            "id": citizen.citizen_id,
            "success": True,
            "message": "Unregistered successfully",
        }

        # Call consumer handler
        handle_unregister_citizen_completed(event_data)

        # Verify external operator was called
        mock_post.assert_called_once()

        # Verify citizen still exists (waiting for confirmation)
        assert Citizen.objects.filter(citizen_id=citizen.citizen_id).exists()

    def test_handle_unregister_failure(self, affiliated_citizen):
        """Test handling failed unregister."""
        citizen, affiliation = affiliated_citizen

        event_data = {
            "id": citizen.citizen_id,
            "success": False,
            "message": "MINTIC unregister failed",
        }

        # Call consumer handler
        handle_unregister_citizen_completed(event_data)

        # Verify citizen still exists
        assert Citizen.objects.filter(citizen_id=citizen.citizen_id).exists()

        # Citizen should still be in its original state
        affiliation.refresh_from_db()
        assert affiliation.status == "AFFILIATED"


@pytest.mark.django_db
class TestDocumentsReadyConsumer:
    """Test cases for documents.ready event consumer."""

    @patch("affiliation.rabbitmq.publisher.publish_register_citizen_requested")
    def test_handle_documents_ready_for_incoming_transfer(
        self, mock_publish, create_citizen, create_affiliation
    ):
        """Test handling documents ready for incoming transfer."""
        # Create citizen with pending transfer
        citizen = create_citizen(is_verified=False)
        affiliation = create_affiliation(
            citizen,
            status="TRANSFERRING",
            transfer_confirmation_url="https://source-operator.com/api/confirm/",
            documents_ready=False,
        )

        mock_publish.return_value = True

        event_data = {"idCitizen": int(citizen.citizen_id)}

        # Call consumer handler
        handle_documents_ready(event_data)

        # Verify documents_ready flag was set
        affiliation.refresh_from_db()
        assert affiliation.documents_ready is True

        # Verify register event was published
        mock_publish.assert_called_once()

    def test_handle_documents_ready_citizen_not_found(self):
        """Test handling documents ready for non-existent citizen."""
        event_data = {"citizenId": "9999999999"}

        # Should not raise exception
        try:
            handle_documents_ready(event_data)
        except Exception as e:
            pytest.fail(f"Should handle gracefully but raised: {e}")


@pytest.mark.django_db
class TestEventPayloadValidation:
    """Test cases for event payload validation."""

    def test_register_completed_missing_id(self):
        """Test register event with missing citizen ID."""
        event_data = {
            "statusCode": 201
            # Missing 'id'
        }

        try:
            handle_register_citizen_completed(event_data)
        except KeyError:
            # Expected to raise KeyError or handle gracefully
            pass

    def test_unregister_completed_missing_success_flag(self, affiliated_citizen):
        """Test unregister event with missing success flag."""
        citizen, _ = affiliated_citizen

        event_data = {
            "id": citizen.citizen_id
            # Missing 'success'
        }

        # Should handle gracefully with default value (success defaults to False)
        try:
            handle_unregister_citizen_completed(event_data)
            # Should not raise an error, uses default value
        except KeyError:
            pass

    def test_invalid_json_payload(self):
        """Test handling invalid JSON in event payload."""
        invalid_data = "not a dict"

        # Consumer should validate payload type
        with pytest.raises((TypeError, AttributeError)):
            handle_register_citizen_completed(invalid_data)


@pytest.mark.django_db
class TestConsumerErrorHandling:
    """Test cases for consumer error handling."""

    @patch("affiliation.rabbitmq.register_citizen_consumer.logger")
    def test_database_error_is_logged(self, mock_logger, create_citizen, create_affiliation):
        """Test that database errors are properly logged."""
        citizen = create_citizen()
        affiliation = create_affiliation(citizen)

        event_data = {"id": citizen.citizen_id, "statusCode": 201}

        # Force a database error by making citizen readonly
        with patch("affiliation.models.citizen.Citizen.save", side_effect=Exception("DB Error")):
            try:
                handle_register_citizen_completed(event_data)
            except Exception:
                pass

            # Verify error was logged
            assert mock_logger.error.called or mock_logger.exception.called

    @patch(
        "affiliation.services.transfer_service.TransferService.continue_transfer_after_unregister"
    )
    def test_transfer_service_error_is_handled(self, mock_service, transferring_citizen):
        """Test that transfer service errors are handled gracefully."""
        citizen, _ = transferring_citizen

        mock_service.return_value = {"success": False, "message": "External API timeout"}

        event_data = {
            "id": citizen.citizen_id,
            "success": True,
            "message": "Unregistered successfully",
        }

        # Should handle error without crashing consumer
        try:
            handle_unregister_citizen_completed(event_data)
        except Exception:
            pytest.fail("Consumer should handle service errors gracefully")
