import requests
import logging
from django.conf import settings
from django.utils import timezone
from affiliation.models import Citizen, Affiliation
from affiliation.rabbitmq.publisher import (
    publish_documents_download_requested,
    publish_affiliation_created,
    publish_user_transferred,
    publish_unregister_citizen_requested,
)

logger = logging.getLogger(__name__)


class TransferService:
    """Service class for handling citizen transfer operations."""

    def receive_transfer(self, transfer_data: dict) -> dict:
        """
        Handle incoming transfer request from another operator.

        This initiates the transfer process:
        1. Create citizen record (not verified, not registered yet)
        2. Create affiliation with TRANSFERRING status
        3. Publish event for document service to download files
        4. Wait for TWO events:
           - documents.ready (documents downloaded)
           - register.citizen.completed (MINTIC registration confirmed)
        5. When BOTH events complete, send confirmation to sending operator

        Args:
            transfer_data: Dictionary containing:
                - id: citizen ID
                - citizenName: citizen's name
                - citizenEmail: citizen's email
                - urlDocuments: dict of document URLs
                - confirmAPI: URL to call for confirmation

        Returns:
            dict: Contains 'success' boolean and 'message' string
        """
        citizen_id = str(transfer_data["id"])

        # Check if citizen already exists
        existing_citizen = Citizen.objects.filter(citizen_id=citizen_id).first()
        if existing_citizen:
            return {"success": False, "message": f"Citizen with id {citizen_id} already exists"}

        try:
            # Create citizen record (not registered, not verified - waiting for documents AND MINTIC)
            citizen = Citizen.objects.create(
                citizen_id=citizen_id,
                name=transfer_data["citizenName"],
                address="",  # Will be updated when documents are processed
                email=transfer_data["citizenEmail"],
                operator_id=settings.OPERATOR_ID,
                operator_name=settings.OPERATOR_NAME,
                is_registered=False,  # Not complete until MINTIC confirms
                is_verified=False,  # Waiting for MINTIC verification
                verification_status="pending",
                verification_message="Waiting for documents and MINTIC verification",
            )

            # Create affiliation with TRANSFERRING status
            affiliation = Affiliation.objects.create(
                citizen=citizen,
                operator_id=settings.OPERATOR_ID,
                operator_name=settings.OPERATOR_NAME,
                status="TRANSFERRING",
                transfer_confirmation_url=transfer_data["confirmAPI"],
                transfer_started_at=timezone.now(),
                documents_ready=False,
            )

            # Publish event for document service to download files
            url_documents = transfer_data.get("urlDocuments", {})
            publish_documents_download_requested(
                id_citizen=int(citizen_id), url_documents=url_documents
            )

            logger.info(f"Transfer initiated for citizen {citizen_id}, waiting for documents")

            return {
                "success": True,
                "message": f"Transfer request received for citizen {citizen_id}, processing documents",
                "citizen_id": citizen_id,
            }

        except Exception as e:
            logger.error(f"Error receiving transfer for citizen {citizen_id}: {str(e)}")
            # Rollback if citizen was created
            if "citizen" in locals():
                citizen.delete()
            return {"success": False, "message": f"Error processing transfer: {str(e)}"}

    def complete_transfer_after_documents(self, citizen_id: str) -> dict:
        """
        Mark documents as ready after documents.ready event is received.

        This does NOT complete the transfer yet. We need to wait for BOTH:
        1. documents_ready = True (this function sets it)
        2. is_verified = True (register.citizen.completed event sets it)

        The check_and_complete_transfer() function will send confirmation
        only when BOTH conditions are met.

        Args:
            citizen_id: The citizen ID

        Returns:
            dict: Contains 'success' boolean and 'message' string
        """
        try:
            citizen = Citizen.objects.get(citizen_id=citizen_id)
            affiliation = citizen.affiliation

            # Mark documents as ready
            affiliation.documents_ready = True
            affiliation.save()

            logger.info(f"Documents ready for citizen {citizen_id}")

            # Now publish register.citizen.requested to register in MINTIC
            from affiliation.rabbitmq.publisher import publish_register_citizen_requested

            publish_register_citizen_requested(
                {
                    "id": int(citizen_id),
                    "name": citizen.name,
                    "address": citizen.address if hasattr(citizen, "address") else "",
                    "email": citizen.email,
                    "operatorId": settings.OPERATOR_ID,
                    "operatorName": settings.OPERATOR_NAME,
                }
            )

            logger.info(f"Published register.citizen.requested for citizen {citizen_id}")

            # Check if we can complete the transfer now
            # (in case MINTIC already responded before documents were ready)
            self.check_and_complete_transfer(citizen_id)

            return {
                "success": True,
                "message": f"Documents ready for citizen {citizen_id}, waiting for MINTIC verification",
            }

        except Citizen.DoesNotExist:
            logger.error(f"Citizen {citizen_id} not found for transfer completion")
            return {"success": False, "message": f"Citizen {citizen_id} not found"}
        except Exception as e:
            logger.error(f"Error completing transfer for citizen {citizen_id}: {str(e)}")
            return {"success": False, "message": f"Error completing transfer: {str(e)}"}

    def check_and_complete_transfer(self, citizen_id: str) -> dict:
        """
        Check if both documents AND MINTIC verification are complete.
        If both are ready, finalize the transfer and send confirmation.

        This is called by:
        1. complete_transfer_after_documents() - when documents are ready
        2. register_citizen_consumer - when MINTIC verification completes

        Args:
            citizen_id: The citizen ID

        Returns:
            dict: Contains 'success' boolean and 'message' string
        """
        try:
            citizen = Citizen.objects.get(citizen_id=citizen_id)
            affiliation = citizen.affiliation

            # Check if affiliation is in TRANSFERRING status
            if affiliation.status != "TRANSFERRING":
                logger.info(
                    f"Citizen {citizen_id} is not in TRANSFERRING status, skipping completion check"
                )
                return {
                    "success": False,
                    "message": f"Citizen {citizen_id} is not being transferred",
                }

            # Check if BOTH conditions are met
            documents_ready = affiliation.documents_ready
            mintic_verified = citizen.is_verified

            logger.info(
                f"Transfer completion check for {citizen_id}: documents_ready={documents_ready}, mintic_verified={mintic_verified}"
            )

            if documents_ready and mintic_verified:
                # BOTH conditions met - complete the transfer!
                logger.info(
                    f"🎉 Both conditions met for citizen {citizen_id}! Completing transfer..."
                )

                # Update citizen to registered
                citizen.is_registered = True
                citizen.save()

                # Update affiliation status to AFFILIATED
                affiliation.status = "AFFILIATED"
                affiliation.transfer_completed_at = timezone.now()
                affiliation.save()

                # Call confirmation API to notify sending operator
                if affiliation.transfer_confirmation_url:
                    self._send_confirmation(
                        confirmation_url=affiliation.transfer_confirmation_url,
                        citizen_id=citizen_id,
                        status=1,  # Success
                    )

                # Publish affiliation.created event
                publish_affiliation_created(int(citizen_id))

                logger.info(f"✅ Transfer completed for citizen {citizen_id}")

                return {"success": True, "message": f"Transfer completed for citizen {citizen_id}"}
            else:
                # Still waiting for one or both conditions
                waiting_for = []
                if not documents_ready:
                    waiting_for.append("documents")
                if not mintic_verified:
                    waiting_for.append("MINTIC verification")

                message = f"Waiting for: {', '.join(waiting_for)}"
                logger.info(f"Transfer not yet complete for {citizen_id}: {message}")

                return {"success": False, "message": message}

        except Citizen.DoesNotExist:
            logger.error(f"Citizen {citizen_id} not found for transfer completion check")
            return {"success": False, "message": f"Citizen {citizen_id} not found"}
        except Exception as e:
            logger.error(f"Error checking transfer completion for citizen {citizen_id}: {str(e)}")
            return {"success": False, "message": f"Error checking transfer completion: {str(e)}"}

    def continue_transfer_after_unregister(self, citizen_id: str) -> dict:
        """
        Continue outgoing transfer after MINTIC unregister confirmation.

        This is called by the unregister.citizen.completed consumer when
        MINTIC confirms the citizen has been unregistered.

        Steps:
        1. Get document URLs from document service
        2. Call target operator's transfer API
        3. Wait for confirmation callback

        Args:
            citizen_id: The citizen ID

        Returns:
            dict: Contains 'success' boolean and 'message' string
        """
        try:
            citizen = Citizen.objects.get(citizen_id=citizen_id)
            affiliation = citizen.affiliation

            # Check if affiliation is in TRANSFERRING status
            if affiliation.status != "TRANSFERRING":
                logger.info(
                    f"Citizen {citizen_id} is not in TRANSFERRING status, skipping transfer continuation"
                )
                return {
                    "success": False,
                    "message": f"Citizen {citizen_id} is not being transferred",
                }

            logger.info(
                f"Continuing transfer for citizen {citizen_id} after MINTIC unregister confirmation"
            )

            # Step 1: Get document URLs from document service
            url_documents = self._get_citizen_documents(citizen_id)

            # Build confirmation callback URL from settings
            # In production, set TRANSFER_CONFIRMATION_URL env variable to your domain
            confirmation_url = settings.TRANSFER_CONFIRMATION_URL

            transfer_payload = {
                "id": int(citizen_id),
                "citizenName": citizen.name,
                "citizenEmail": citizen.email,
                "urlDocuments": url_documents,
                "confirmAPI": confirmation_url,
            }

            # Step 2: Call receiving operator's transfer API
            # Get the target API URL that was saved when transfer was initiated
            target_api_url = affiliation.transfer_destination_api_url

            if not target_api_url:
                logger.error(f"No target API URL found for citizen {citizen_id}")
                return {"success": False, "message": "Target operator API URL not found"}

            logger.info(f"Sending transfer request to {target_api_url}")
            logger.info(f"body of response {transfer_payload}")
            response = requests.post(target_api_url, json=transfer_payload, timeout=30)

            if response.status_code not in [200, 201]:
                logger.error(f"Failed to send transfer to target operator: {response.text}")
                # Keep TRANSFERRING status so it can be retried
                return {
                    "success": False,
                    "message": f"Failed to send transfer to target operator: {response.text}",
                }

            logger.info(f"Transfer request sent successfully for citizen {citizen_id}")

            # Step 3: Transfer sent, now waiting for confirmation callback
            # The receiving operator will call our /confirm endpoint when done
            # The confirmation handler will delete the local data

            return {
                "success": True,
                "message": f"Transfer sent to target operator for citizen {citizen_id}. Waiting for confirmation.",
                "citizen_id": citizen_id,
            }

        except Citizen.DoesNotExist:
            logger.error(f"Citizen {citizen_id} not found for transfer continuation")
            return {"success": False, "message": f"Citizen {citizen_id} not found"}
        except Exception as e:
            logger.error(f"Error continuing transfer for citizen {citizen_id}: {str(e)}")
            return {"success": False, "message": f"Error continuing transfer: {str(e)}"}

    def send_transfer(self, citizen_id: str, target_operator: dict) -> dict:
        """
        Send a citizen to another operator (Phase 2: Outgoing Transfer).

        EVENT-DRIVEN FLOW:
        1. Mark Affiliation as 'TRANSFERRING'
        2. Publish unregister.citizen.requested event (non-blocking)
        3. Wait for unregister.citizen.completed event
        4. Consumer will call continue_transfer_after_unregister() to:
           - Get document URLs
           - Call target operator's API
        5. Wait for target operator confirmation callback
        6. On confirmation: delete local data

        Args:
            citizen_id: The citizen ID to transfer
            target_operator: Dict containing:
                - operator_id: Target operator ID
                - operator_name: Target operator name
                - api_url: Target operator's transfer API endpoint

        Returns:
            dict: Contains 'success' boolean and 'message' string
        """
        try:
            # Get citizen and affiliation
            citizen = Citizen.objects.get(citizen_id=citizen_id)
            affiliation = citizen.affiliation

            # Check if citizen is currently affiliated (not already transferring)
            if affiliation.status != "AFFILIATED":
                return {
                    "success": False,
                    "message": f"Citizen {citizen_id} cannot be transferred (status: {affiliation.status})",
                }

            # Step 1: Mark affiliation as TRANSFERRING and save target operator info
            affiliation.status = "TRANSFERRING"
            affiliation.transfer_destination_operator_id = target_operator["operator_id"]
            affiliation.transfer_destination_operator_name = target_operator["operator_name"]
            affiliation.transfer_destination_api_url = target_operator["api_url"]
            affiliation.transfer_started_at = timezone.now()
            affiliation.save()

            logger.info(
                f"Marked citizen {citizen_id} as TRANSFERRING to {target_operator['operator_name']}"
            )

            # Step 2: Publish unregister event (EVENT-DRIVEN, non-blocking)
            # The unregister consumer will call continue_transfer_after_unregister()
            # when MINTIC confirms the unregistration
            event_payload = {
                "id": int(citizen_id),
                "operatorId": settings.OPERATOR_ID,
                "operatorName": settings.OPERATOR_NAME,
            }

            success = publish_unregister_citizen_requested(event_payload)

            if not success:
                logger.error(f"Failed to publish unregister event for citizen {citizen_id}")
                # Rollback TRANSFERRING status
                affiliation.status = "AFFILIATED"
                affiliation.transfer_destination_operator_id = None
                affiliation.transfer_destination_operator_name = None
                affiliation.save()
                return {
                    "success": False,
                    "message": "Failed to initiate transfer: could not publish unregister event",
                }

            logger.info(
                f"Published unregister event for citizen {citizen_id}, waiting for MINTIC confirmation"
            )

            # Step 3: Return immediately (optimistic UI)
            # The unregister.citizen.completed consumer will call
            # continue_transfer_after_unregister() to complete the flow
            return {
                "success": True,
                "message": f"Transfer initiated for citizen {citizen_id}. Waiting for MINTIC unregister confirmation.",
                "citizen_id": citizen_id,
                "target_operator": target_operator["operator_name"],
                "status": "unregistering_from_mintic",
            }

        except Citizen.DoesNotExist:
            return {"success": False, "message": f"Citizen {citizen_id} not found"}
        except Exception as e:
            logger.error(f"Error sending transfer for citizen {citizen_id}: {str(e)}")
            return {"success": False, "message": f"Error sending transfer: {str(e)}"}

    def handle_transfer_confirmation(self, citizen_id: str, req_status: int) -> dict:
        """
        Handle confirmation callback from receiving operator (Phase 2).

        When we send a citizen to another operator and they successfully
        receive it, they call this endpoint. We then delete the local data.

        Args:
            citizen_id: The citizen ID
            req_status: 1 for success, 0 for failure

        Returns:
            dict: Contains 'success' boolean and 'message' string
        """
        try:
            citizen = Citizen.objects.get(citizen_id=citizen_id)
            affiliation = citizen.affiliation

            if req_status == 1:
                # Transfer successful - delete local data
                logger.info(f"Transfer confirmed for citizen {citizen_id}. Deleting local data.")

                # Update status before deletion (for audit trail)
                affiliation.status = "TRANSFERRED"
                affiliation.transfer_completed_at = timezone.now()
                affiliation.save()

                # Emit user.transferred event BEFORE deletion
                # This notifies other services (document service, etc.) that citizen has been transferred
                publish_user_transferred(int(citizen_id))
                logger.info(f"Published user.transferred event for citizen {citizen_id}")

                # Delete citizen and affiliation
                citizen_name = citizen.name
                operator_name = affiliation.transfer_destination_operator_name

                affiliation.delete()
                citizen.delete()

                logger.info(
                    f"Deleted citizen {citizen_id} ({citizen_name}) after successful transfer to {operator_name}"
                )

                return {
                    "success": True,
                    "message": f"Citizen {citizen_id} transferred successfully and deleted locally",
                }
            else:
                # Transfer failed - rollback status
                logger.warning(f"Transfer failed for citizen {citizen_id}. Rolling back.")

                affiliation.status = "AFFILIATED"
                affiliation.transfer_destination_operator_id = None
                affiliation.transfer_destination_operator_name = None
                affiliation.save()

                return {
                    "success": False,
                    "message": f"Transfer failed for citizen {citizen_id}. Status rolled back to AFFILIATED.",
                }

        except Citizen.DoesNotExist:
            logger.warning(f"Received confirmation for unknown citizen {citizen_id}")
            return {"success": False, "message": f"Citizen {citizen_id} not found"}
        except Exception as e:
            logger.error(f"Error handling confirmation for citizen {citizen_id}: {str(e)}")
            return {"success": False, "message": f"Error handling confirmation: {str(e)}"}

    def _get_citizen_documents(self, citizen_id: str) -> dict:
        """
        Get document URLs for a citizen from the document service via REST API.

        The document service should return URLs in the format:
        {
            "URL1": ["http://example.com/document1"],
            "URL2": ["http://example.com/document2"]
        }

        Args:
            citizen_id: The citizen ID

        Returns:
            dict: Dictionary of document URLs with arrays
        """
        try:
            # Call document service REST API to get document URLs
            # In production, DOCUMENT_SERVICE_URL should be set to the actual document service
            # In development/testing with localhost, use the appropriate endpoint
            document_service_url = settings.DOCUMENT_SERVICE_URL

            if "localhost" in document_service_url or "127.0.0.1" in document_service_url:
                # Development/testing mode - check if we're in Kubernetes
                import os

                if os.getenv("KUBERNETES_SERVICE_HOST"):
                    # We're in Kubernetes, use internal service name for test endpoint
                    document_api_url = f"http://citizen-affiliation-api-service:8000/api/v1/test/documents/{citizen_id}/"
                else:
                    # Local development, use localhost
                    document_api_url = f"http://localhost:8000/api/v1/test/documents/{citizen_id}/"
            else:
                # Production mode - use the configured document service URL
                document_api_url = f"{document_service_url}/api/documents/{citizen_id}"

            logger.info(
                f"Fetching documents for citizen {citizen_id} from document service: {document_api_url}"
            )

            response = requests.get(
                document_api_url, headers={"Content-Type": "application/json"}, timeout=10
            )

            if response.status_code == 200:
                documents_data = response.json()

                # Expected format: {"URL1": ["http://..."], "URL2": ["http://..."]}
                # If wrapped in a 'documents' key, unwrap it
                if "documents" in documents_data:
                    url_documents = documents_data["documents"]
                else:
                    url_documents = documents_data

                logger.info(
                    f"Retrieved {len(url_documents)} document URL group(s) for citizen {citizen_id}"
                )
                return url_documents
            else:
                logger.warning(
                    f"Failed to get documents for citizen {citizen_id}: Status {response.status_code}, {response.text}"
                )
                # Return empty dict if documents not found or service unavailable
                return {}

        except requests.exceptions.Timeout:
            logger.error(
                f"Timeout fetching documents for citizen {citizen_id} from document service"
            )
            return {}
        except requests.exceptions.ConnectionError:
            logger.error(
                f"Connection error to document service for citizen {citizen_id}. Is the service running?"
            )
            return {}
        except Exception as e:
            logger.error(f"Error getting documents for citizen {citizen_id}: {str(e)}")
            return {}

    def _send_confirmation(self, confirmation_url: str, citizen_id: str, status: int):
        """
        Send confirmation to the sending operator.

        Args:
            confirmation_url: URL to call for confirmation
            citizen_id: The citizen ID
            status: 1 for success, 0 for failure
        """
        try:
            payload = {"id": int(citizen_id), "req_status": status}

            response = requests.post(confirmation_url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info(f"Confirmation sent successfully for citizen {citizen_id}")
            else:
                logger.error(f"Failed to send confirmation: {response.text}")

        except Exception as e:
            logger.error(f"Failed to send confirmation: {str(e)}")
