"""
Test endpoints for simulating external services.
These are for development/testing only.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class MockDocumentServiceView(APIView):
    """
    Mock endpoint to simulate document service.

    This simulates what the document service would return when
    asked for a citizen's document URLs.

    GET /api/test/documents/{citizen_id}

    Returns document URLs in the format expected by transfer payload:
    {
        "URL1": ["http://example.com/document1"],
        "URL2": ["http://example.com/document2"]
    }
    """

    def get(self, request, citizen_id):
        """Return mock document URLs for a citizen."""

        # Mock document URLs for testing
        mock_documents = {
            "identification": [
                f"https://storage.example.com/citizens/{citizen_id}/id_front.pdf",
                f"https://storage.example.com/citizens/{citizen_id}/id_back.pdf",
            ],
            "proofOfAddress": [
                f"https://storage.example.com/citizens/{citizen_id}/address_proof.pdf"
            ],
            "birthCertificate": [
                f"https://storage.example.com/citizens/{citizen_id}/birth_cert.pdf"
            ],
        }

        return Response(mock_documents, status=status.HTTP_200_OK)


class MockDocumentServiceWrappedView(APIView):
    """
    Alternative mock endpoint that returns documents wrapped in a 'documents' key.

    GET /api/test/documents-wrapped/{citizen_id}

    Returns:
    {
        "documents": {
            "URL1": ["http://example.com/document1"],
            "URL2": ["http://example.com/document2"]
        }
    }
    """

    def get(self, request, citizen_id):
        """Return mock document URLs wrapped in 'documents' key."""

        mock_data = {
            "documents": {
                "identification": [
                    f"https://storage.example.com/citizens/{citizen_id}/id_front.pdf",
                    f"https://storage.example.com/citizens/{citizen_id}/id_back.pdf",
                ],
                "proofOfAddress": [
                    f"https://storage.example.com/citizens/{citizen_id}/address_proof.pdf"
                ],
            }
        }

        return Response(mock_data, status=status.HTTP_200_OK)
