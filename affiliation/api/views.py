from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from affiliation.api.serializers import CitizenSerializer
from affiliation.services.citizen_service import CitizenService
from affiliation.services.transfer_service import TransferService


class ValidateCitizenView(APIView):
    """
    API endpoint to validate if a citizen exists in the external system.

    GET /api/v1/citizens/{citizen_id}/validate/
    """

    def get(self, request, citizen_id):
        """Validate if citizen exists."""
        service = CitizenService()
        result = service.validate_citizen(citizen_id)

        if result["exists"]:
            return Response({"message": result["message"]}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "Citizen not found"}, status=status.HTTP_404_NOT_FOUND)


class RegisterCitizenView(APIView):
    """
    API endpoint to register a new citizen.

    POST /api/v1/citizens/register/

    Request body:
    {
        "id": "1128456232",
        "name": "Daniel Garcia",
        "address": "Cra44 # 33",
        "email": "dagarciaz@unal.edu.co"
    }

    Note: Operator information is configured in settings (OPERATOR_ID, OPERATOR_NAME)
    """

    def post(self, request):
        """Register a new citizen."""
        serializer = CitizenSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Add operator information from settings
        citizen_data = serializer.validated_data
        citizen_data["operator_id"] = settings.OPERATOR_ID
        citizen_data["operator_name"] = settings.OPERATOR_NAME

        service = CitizenService()
        result = service.register_citizen(citizen_data)

        if result["success"]:
            return Response({"message": result["message"]}, status=status.HTTP_201_CREATED)
        else:
            return Response({"message": result["message"]}, status=status.HTTP_400_BAD_REQUEST)


class TransferReceiveView(APIView):
    """
    API endpoint to receive incoming transfer requests from other operators.

    POST /api/v1/citizens/transfer/receive/

    Request body:
    {
        "id": 1128456232,
        "citizenName": "Daniel Garcia",
        "citizenEmail": "dagarciaz@unal.edu.co",
        "urlDocuments": {
            "document1": "https://example.com/doc1.pdf",
            "document2": "https://example.com/doc2.pdf"
        },
        "confirmAPI": "https://sending-operator.com/api/v1/transfer/confirm"
    }
    """

    def post(self, request):
        """Receive transfer request from another operator."""
        # Validate required fields
        required_fields = ["id", "citizenName", "citizenEmail", "confirmAPI"]
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {"message": f"Missing required field: {field}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        service = TransferService()
        result = service.receive_transfer(request.data)

        if result["success"]:
            return Response({"message": result["message"]}, status=status.HTTP_201_CREATED)
        else:
            return Response({"message": result["message"]}, status=status.HTTP_400_BAD_REQUEST)


class TransferSendView(APIView):
    """
    API endpoint to send a citizen to another operator (Phase 2: Outgoing Transfer).

    POST /api/v1/citizens/{citizen_id}/transfer/

    Request body:
    {
        "targetOperatorId": "68f003d9a49e090002e5d0b6",
        "targetOperatorName": "Operator Name",
        "targetApiUrl": "https://target-operator.com/api/v1/citizens/transfer/receive/"
    }

    Process:
    1. Marks affiliation as TRANSFERRING
    2. Deletes citizen from gov folder system
    3. Prepares transfer payload with document URLs
    4. Calls receiving operator's API
    5. Waits for confirmation callback
    6. On confirmation: deletes local citizen and affiliation data
    """

    def post(self, request, citizen_id):
        """Send citizen to another operator."""
        # Validate required fields
        required_fields = ["targetOperatorId", "targetOperatorName", "targetApiUrl"]
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {"message": f"Missing required field: {field}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Prepare target operator info
        target_operator = {
            "operator_id": request.data["targetOperatorId"],
            "operator_name": request.data["targetOperatorName"],
            "api_url": request.data["targetApiUrl"],
        }

        service = TransferService()
        result = service.send_transfer(citizen_id, target_operator)

        if result["success"]:
            return Response(
                {
                    "message": result["message"],
                    "citizenId": result.get("citizen_id"),
                    "targetOperator": result.get("target_operator"),
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response({"message": result["message"]}, status=status.HTTP_400_BAD_REQUEST)


class TransferConfirmView(APIView):
    """
    API endpoint to receive confirmation from other operators.

    This is called by the operator we sent a transfer to, confirming they
    received the citizen successfully. Upon successful confirmation,
    we delete the local citizen and affiliation data.

    POST /api/v1/citizens/transfer/confirm/

    Request body:
    {
        "id": 1128456232,
        "req_status": 1  // 1 = success, 0 = failure
    }
    """

    def post(self, request):
        """Receive confirmation of transfer."""
        # Validate required fields
        if "id" not in request.data or "req_status" not in request.data:
            return Response(
                {"message": "Missing required fields: id, req_status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        citizen_id = str(request.data["id"])
        req_status = request.data["req_status"]

        # Handle confirmation (Phase 2)
        service = TransferService()
        result = service.handle_transfer_confirmation(citizen_id, req_status)

        if result["success"]:
            return Response({"message": result["message"]}, status=status.HTTP_200_OK)
        else:
            return Response({"message": result["message"]}, status=status.HTTP_400_BAD_REQUEST)


class AffiliationStatusView(APIView):
    """
    API endpoint to get the current affiliation status for a citizen.

    GET /api/v1/affiliations/{citizen_id}/status/

    Response:
    {
        "citizen_id": "1128456232",
        "citizen_name": "Daniel Garcia",
        "citizen_email": "dagarciaz@unal.edu.co",
        "operator_id": "68f003d9a49e090002e5d0b5",
        "operator_name": "TEST DAGZ",
        "status": "AFFILIATED",
        "affiliated_at": "2024-01-01T12:00:00Z",
        "destination_operator_id": null,
        "destination_operator_name": null
    }
    """

    def get(self, request, citizen_id):
        """Get affiliation status for a citizen."""
        service = CitizenService()
        result = service.get_affiliation_status(citizen_id)

        if result["success"]:
            return Response(result["data"], status=status.HTTP_200_OK)
        else:
            return Response({"message": result["message"]}, status=status.HTTP_404_NOT_FOUND)


class AffiliationDeleteView(APIView):
    """
    API endpoint to delete an affiliation and associated citizen.

    DELETE /api/v1/affiliations/{citizen_id}/

    This operation performs a complete cleanup:
    1. Unregisters the citizen from the external government folder system
    2. Publishes user.transferred event to notify other microservices (e.g., document service)
    3. Deletes the local citizen and affiliation records

    NOTE: This is different from the transfer flow. Use this for administrative
    cleanup when you need to completely remove a citizen without transferring them
    to another operator.

    Response:
    {
        "message": "Citizen 1128456232 and associated affiliation deleted successfully"
    }
    """

    def delete(self, request, citizen_id):
        """Delete affiliation and citizen."""
        service = CitizenService()
        result = service.delete_affiliation(citizen_id)

        if result["success"]:
            return Response({"message": result["message"]}, status=status.HTTP_200_OK)
        else:
            return Response({"message": result["message"]}, status=status.HTTP_404_NOT_FOUND)


class OperatorsListView(APIView):
    """
    API endpoint to get list of all operators.

    GET /api/v1/operators/

    NOTE: This endpoint uses REST API calls (not RabbitMQ events).
    It's a simple read-only query that will be routed through Operator Connectivity.

    Response:
    {
        "operators": [
            {
                "_id": "66ca18cd66ca9f0015a8afb3",
                "operatorName": "Nsync",
                "participants": ["Juan Camilo Castro", "Juan David Echeverri", ...],
                "transferAPIURL": "https://example.com/api/transferCitizen"  // optional
            },
            ...
        ]
    }
    """

    def get(self, request):
        """Get list of all operators."""
        service = CitizenService()
        result = service.get_operators()

        if result["success"]:
            return Response(
                {"operators": result["operators"], "count": len(result["operators"])},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"message": result["message"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
