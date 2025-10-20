"""
Unit tests for CitizenService - handles citizen registration and affiliation.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from affiliation.services.citizen_service import CitizenService
from affiliation.models.citizen import Citizen
from affiliation.models.affiliation import Affiliation


@pytest.mark.django_db
class TestCitizenServiceValidation:
    """Test cases for citizen validation with MINTIC."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = CitizenService()

    @patch("affiliation.services.citizen_service.requests.get")
    def test_validate_citizen_exists(self, mock_get):
        """Test validation when citizen exists in MINTIC."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "El ciudadano con id: 1234567890 se encuentra registrado"
        mock_get.return_value = mock_response

        result = self.service.validate_citizen("1234567890")

        assert result["exists"] is True
        assert "registrado" in result["message"]
        mock_get.assert_called_once()

    @patch("affiliation.services.citizen_service.requests.get")
    def test_validate_citizen_not_exists(self, mock_get):
        """Test validation when citizen does not exist in MINTIC."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Ciudadano no encontrado"
        mock_get.return_value = mock_response

        result = self.service.validate_citizen("9999999999")

        assert result["exists"] is False

    @patch("affiliation.services.citizen_service.requests.get")
    def test_validate_citizen_api_error(self, mock_get):
        """Test handling MINTIC API errors."""
        import requests

        mock_get.side_effect = requests.RequestException("Connection timeout")

        result = self.service.validate_citizen("1234567890")

        assert result["exists"] is False


@pytest.mark.django_db
class TestCitizenServiceRegistration:
    """Test cases for citizen registration."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = CitizenService()

    @patch("affiliation.rabbitmq.publisher.publish_register_citizen_requested")
    @patch("affiliation.services.citizen_service.requests.get")
    def test_register_citizen_success(
        self, mock_get, mock_publish, sample_citizen_data, sample_operator_data
    ):
        """Test successful citizen registration."""
        # Mock validation - citizen doesn't exist externally
        mock_get.return_value.status_code = 404
        mock_publish.return_value = True

        citizen_data = {**sample_citizen_data, **sample_operator_data}
        # Add citizen_id field
        citizen_data["citizen_id"] = citizen_data["id"]
        result = self.service.register_citizen(citizen_data)

        assert result["success"] is True

        # Verify citizen was created with correct field name
        citizen = Citizen.objects.get(citizen_id=sample_citizen_data["id"])
        assert citizen.name == sample_citizen_data["name"]
        assert citizen.email == sample_citizen_data["email"]
        assert citizen.is_registered is True
        assert citizen.is_verified is False

    @patch("affiliation.services.citizen_service.requests.get")
    def test_register_citizen_already_exists(
        self, mock_get, create_citizen, sample_citizen_data, sample_operator_data
    ):
        """Test registering citizen that already exists."""
        # Create existing verified citizen
        create_citizen(
            citizen_id=sample_citizen_data["id"], is_verified=True, verification_status="verified"
        )

        # Mock validation
        mock_get.return_value.status_code = 404

        citizen_data = {**sample_citizen_data, **sample_operator_data}
        citizen_data["citizen_id"] = citizen_data["id"]
        result = self.service.register_citizen(citizen_data)

        assert result["success"] is False

    @patch("affiliation.rabbitmq.publisher.publish_register_citizen_requested")
    @patch("affiliation.services.citizen_service.requests.get")
    def test_register_citizen_event_publish_failure(
        self, mock_get, mock_publish, sample_citizen_data, sample_operator_data
    ):
        """Test handling event publishing failure."""
        mock_get.return_value.status_code = 404
        mock_publish.return_value = False  # Publisher returns False on failure

        citizen_data = {**sample_citizen_data, **sample_operator_data}
        citizen_data["citizen_id"] = citizen_data["id"]

        # Should handle gracefully - event publish failure doesn't stop registration
        result = self.service.register_citizen(citizen_data)
        # Citizen should still be created even if event publishing fails
        assert Citizen.objects.filter(citizen_id=sample_citizen_data["id"]).exists()


@pytest.mark.django_db
class TestCitizenServiceAffiliationStatus:
    """Test cases for checking affiliation status."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = CitizenService()

    def test_get_affiliation_status_success(self, affiliated_citizen):
        """Test getting affiliation status for affiliated citizen."""
        citizen, affiliation = affiliated_citizen

        result = self.service.get_affiliation_status(citizen.citizen_id)

        assert result["success"] is True
        assert result["data"]["citizen_id"] == citizen.citizen_id
        assert result["data"]["citizen_name"] == citizen.name
        assert result["data"]["status"] == "AFFILIATED"
        assert result["data"]["operator_id"] == affiliation.operator_id

    def test_get_affiliation_status_not_found(self):
        """Test getting status for non-existent citizen."""
        result = self.service.get_affiliation_status("9999999999")

        assert result["success"] is False

    def test_get_affiliation_status_transferring(self, transferring_citizen):
        """Test getting status for citizen in TRANSFERRING state."""
        citizen, affiliation = transferring_citizen

        result = self.service.get_affiliation_status(citizen.citizen_id)

        assert result["success"] is True
        assert result["data"]["status"] == "TRANSFERRING"
        assert (
            result["data"]["transfer_destination_operator_id"]
            == affiliation.transfer_destination_operator_id
        )


@pytest.mark.django_db
class TestCitizenServiceDeleteAffiliation:
    """Test cases for deleting affiliations."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = CitizenService()

    @patch("affiliation.rabbitmq.publisher.publish_user_transferred")
    @patch("affiliation.rabbitmq.publisher.publish_unregister_citizen_requested")
    def test_delete_affiliation_success(
        self, mock_unregister, mock_transferred, affiliated_citizen
    ):
        """Test successful affiliation deletion."""
        citizen, affiliation = affiliated_citizen
        citizen_id = citizen.citizen_id

        mock_unregister.return_value = True
        mock_transferred.return_value = True

        result = self.service.delete_affiliation(citizen_id)

        assert result["success"] is True

        # Citizen is marked for deletion, actual deletion happens after unregister event

    def test_delete_affiliation_not_found(self):
        """Test deleting non-existent affiliation."""
        result = self.service.delete_affiliation("9999999999")

        assert result["success"] is False


@pytest.mark.django_db
class TestCitizenServiceGetOperators:
    """Test cases for getting operator list."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = CitizenService()

    @patch("affiliation.services.citizen_service.requests.get")
    def test_get_operators_success(self, mock_get):
        """Test successfully fetching operators list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "op1", "name": "Operator 1"},
            {"id": "op2", "name": "Operator 2"},
        ]
        mock_get.return_value = mock_response

        result = self.service.get_operators()

        assert result["success"] is True
        assert len(result["operators"]) == 2

    @patch("affiliation.services.citizen_service.requests.get")
    def test_get_operators_api_error(self, mock_get):
        """Test handling operator service errors."""
        import requests

        mock_get.side_effect = requests.RequestException("Service unavailable")

        result = self.service.get_operators()

        assert result["success"] is False
