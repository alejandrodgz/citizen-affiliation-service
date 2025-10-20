from rest_framework import serializers
from affiliation.models import Citizen, Affiliation


class CitizenSerializer(serializers.ModelSerializer):
    """Serializer for Citizen model."""

    id = serializers.CharField(source="citizen_id", required=True)
    isVerified = serializers.BooleanField(source="is_verified", read_only=True)
    verificationStatus = serializers.CharField(source="verification_status", read_only=True)
    verificationMessage = serializers.CharField(source="verification_message", read_only=True)
    pendingDeletion = serializers.BooleanField(source="pending_deletion", read_only=True)

    class Meta:
        model = Citizen
        fields = [
            "id",
            "name",
            "address",
            "email",
            "isVerified",
            "verificationStatus",
            "verificationMessage",
            "pendingDeletion",
        ]

    def create(self, validated_data):
        """Create a new citizen instance."""
        return Citizen.objects.create(**validated_data)


class AffiliationSerializer(serializers.ModelSerializer):
    """Serializer for Affiliation model."""

    citizenId = serializers.CharField(source="citizen.citizen_id", read_only=True)
    citizenName = serializers.CharField(source="citizen.name", read_only=True)
    operatorId = serializers.CharField(source="operator_id")
    operatorName = serializers.CharField(source="operator_name")
    affiliatedAt = serializers.DateTimeField(source="affiliated_at", read_only=True)
    statusChangedAt = serializers.DateTimeField(source="status_changed_at", read_only=True)

    class Meta:
        model = Affiliation
        fields = [
            "id",
            "citizenId",
            "citizenName",
            "operatorId",
            "operatorName",
            "status",
            "affiliatedAt",
            "statusChangedAt",
            "transfer_destination_operator_id",
            "transfer_destination_operator_name",
            "notes",
        ]
        read_only_fields = ["id", "affiliatedAt", "statusChangedAt"]
