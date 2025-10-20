import requests
from django.conf import settings
from affiliation.models import Citizen, Affiliation
from affiliation.rabbitmq.publisher import (
    publish_register_citizen_requested,
    publish_unregister_citizen_requested,
)
import logging

logger = logging.getLogger(__name__)


class CitizenService:
    """Service class for citizen validation and registration operations."""

    def __init__(self):
        self.api_base_url = settings.GOVCARPETA_API_URL

    def validate_citizen(self, citizen_id: str) -> dict:
        """
        Validate if a citizen exists in the external system.

        Args:
            citizen_id: The citizen's ID to validate

        Returns:
            dict: Contains 'exists' boolean and 'message' string
        """
        try:
            url = f"{self.api_base_url}/apis/validateCitizen/{citizen_id}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200 and response.text:
                # Citizen exists
                return {"exists": True, "message": response.text}
            else:
                # Citizen does not exist
                return {"exists": False, "message": f"Citizen with id {citizen_id} not found"}
        except requests.RequestException as e:
            logger.error(f"Error validating citizen {citizen_id}: {str(e)}")
            return {"exists": False, "message": f"Error validating citizen: {str(e)}"}

    def register_citizen(self, citizen_data: dict) -> dict:
        """
        Register a new citizen using event-driven pattern.
        Creates citizen locally with pending verification, then publishes event
        for Operator Connectivity to confirm with MINTIC.

        Args:
            citizen_data: Dictionary containing citizen information

        Returns:
            dict: Contains 'success' boolean and 'message' string
        """
        citizen_id = citizen_data["citizen_id"]

        # First, check if citizen already exists in our database
        existing_citizen = Citizen.objects.filter(citizen_id=citizen_id).first()
        if existing_citizen:
            if existing_citizen.is_verified:
                return {
                    "success": False,
                    "message": f"Citizen with id {citizen_id} already registered and verified",
                }
            elif existing_citizen.verification_status == Citizen.VERIFICATION_PENDING:
                return {
                    "success": False,
                    "message": f"Citizen with id {citizen_id} already registered, waiting for MINTIC verification",
                }

        # Check if citizen exists in external system (still need this validation)
        validation = self.validate_citizen(citizen_id)
        if validation["exists"]:
            return {"success": False, "message": validation["message"]}

        try:
            # Create citizen locally with pending verification status
            citizen = Citizen.objects.create(
                citizen_id=citizen_id,
                name=citizen_data["name"],
                address=citizen_data["address"],
                email=citizen_data["email"],
                operator_id=citizen_data["operator_id"],
                operator_name=citizen_data["operator_name"],
                is_registered=True,  # Registered locally
                is_verified=False,  # Not yet verified by MINTIC
                verification_status=Citizen.VERIFICATION_PENDING,
                verification_message="Waiting for MINTIC verification",
            )

            # Create affiliation record with PENDING status
            Affiliation.objects.create(
                citizen=citizen,
                operator_id=citizen_data["operator_id"],
                operator_name=citizen_data["operator_name"],
                status="PENDING",  # Will change to AFFILIATED after verification
            )

            # Publish event for Operator Connectivity to register with MINTIC
            event_payload = {
                "id": int(citizen_id),
                "name": citizen_data["name"],
                "address": citizen_data["address"],
                "email": citizen_data["email"],
                "operatorId": citizen_data["operator_id"],
                "operatorName": citizen_data["operator_name"],
            }

            success = publish_register_citizen_requested(event_payload)

            if not success:
                logger.warning(
                    f"Failed to publish register event for citizen {citizen_id}, but citizen created locally"
                )

            return {
                "success": True,
                "message": "Citizen registered locally. Waiting for MINTIC verification.",
                "citizen_id": citizen_id,
                "verification_status": "pending",
            }

        except Exception as e:
            logger.error(f"Error registering citizen {citizen_id}: {str(e)}")
            return {"success": False, "message": f"Error registering citizen: {str(e)}"}

    def get_affiliation_status(self, citizen_id: str) -> dict:
        """
        Get the current affiliation status for a citizen.

        Args:
            citizen_id: The citizen's ID

        Returns:
            dict: Contains 'success' boolean, 'data' with affiliation info or 'message' string
        """
        try:
            citizen = Citizen.objects.filter(citizen_id=citizen_id).first()

            if not citizen:
                return {"success": False, "message": f"Citizen {citizen_id} not found"}

            affiliation = Affiliation.objects.filter(citizen=citizen).first()

            if not affiliation:
                return {
                    "success": False,
                    "message": f"No affiliation found for citizen {citizen_id}",
                }

            return {
                "success": True,
                "data": {
                    "citizen_id": citizen.citizen_id,
                    "citizen_name": citizen.name,
                    "citizen_email": citizen.email,
                    "operator_id": affiliation.operator_id,
                    "operator_name": affiliation.operator_name,
                    "status": affiliation.status,
                    "affiliated_at": affiliation.affiliated_at.isoformat(),
                    "transfer_destination_operator_id": affiliation.transfer_destination_operator_id,
                    "transfer_destination_operator_name": affiliation.transfer_destination_operator_name,
                },
            }
        except Exception as e:
            logger.error(f"Error getting affiliation status for citizen {citizen_id}: {str(e)}")
            return {"success": False, "message": f"Error getting affiliation status: {str(e)}"}

    def delete_affiliation(self, citizen_id: str) -> dict:
        """
        Delete a citizen's affiliation using event-driven pattern.
        Marks citizen for deletion, publishes unregister event, actual deletion
        happens when Operator Connectivity confirms.

        Steps:
        1. Mark citizen as pending_deletion=True
        2. Publish unregister.citizen.requested event
        3. Wait for unregister.citizen.completed event (consumer handles actual deletion)

        Args:
            citizen_id: The citizen's ID

        Returns:
            dict: Contains 'success' boolean and 'message' string
        """
        try:
            citizen = Citizen.objects.filter(citizen_id=citizen_id).first()

            if not citizen:
                return {"success": False, "message": f"Citizen {citizen_id} not found"}

            if citizen.pending_deletion:
                return {
                    "success": False,
                    "message": f"Citizen {citizen_id} is already pending deletion, waiting for MINTIC confirmation",
                }

            operator_id = citizen.operator_id
            operator_name = citizen.operator_name

            # Mark citizen as pending deletion
            citizen.pending_deletion = True
            citizen.verification_message = "Waiting for MINTIC unregister confirmation"
            citizen.save()

            # Update affiliation status to PENDING_DELETION
            affiliation = Affiliation.objects.filter(citizen=citizen).first()
            if affiliation:
                affiliation.status = "PENDING_DELETION"
                affiliation.save()

            # Publish unregister event for Operator Connectivity
            event_payload = {
                "id": int(citizen_id),
                "operatorId": operator_id,
                "operatorName": operator_name,
            }

            success = publish_unregister_citizen_requested(event_payload)

            if not success:
                logger.warning(f"Failed to publish unregister event for citizen {citizen_id}")
                # Rollback pending deletion status
                citizen.pending_deletion = False
                citizen.verification_message = None
                citizen.save()
                if affiliation:
                    affiliation.status = "AFFILIATED"
                    affiliation.save()
                return {"success": False, "message": "Failed to publish unregister event"}

            logger.info(
                f"Marked citizen {citizen_id} for deletion, waiting for MINTIC confirmation"
            )

            return {
                "success": True,
                "message": "Citizen marked for deletion. Waiting for MINTIC confirmation.",
                "citizen_id": citizen_id,
                "status": "pending_deletion",
            }

        except Exception as e:
            logger.error(f"Error deleting affiliation for citizen {citizen_id}: {str(e)}")
            return {"success": False, "message": f"Error processing deletion: {str(e)}"}

    def get_operators(self) -> dict:
        """
        Get list of all operators from GovCarpeta API.

        NOTE: This endpoint will continue using REST API calls via Operator Connectivity.
        Unlike register/unregister operations, this is a read-only query operation
        that doesn't require event-driven architecture.

        Returns:
            dict: Contains 'success' boolean, 'operators' list, and 'message' string
        """
        try:
            url = f"{self.api_base_url}/apis/getOperators"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                operators = response.json()
                logger.info(f"Successfully retrieved {len(operators)} operators")
                return {
                    "success": True,
                    "operators": operators,
                    "message": f"Retrieved {len(operators)} operators",
                }
            else:
                logger.error(f"Failed to get operators. Status: {response.status_code}")
                return {
                    "success": False,
                    "operators": [],
                    "message": f"Failed to retrieve operators: {response.status_code}",
                }
        except requests.RequestException as e:
            logger.error(f"Error getting operators: {str(e)}")
            return {
                "success": False,
                "operators": [],
                "message": f"Error getting operators: {str(e)}",
            }
