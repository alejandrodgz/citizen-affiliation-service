from django.urls import path
from affiliation.api.views import (
    ValidateCitizenView,
    RegisterCitizenView,
    TransferReceiveView,
    TransferSendView,
    TransferConfirmView,
    AffiliationStatusView,
    AffiliationDeleteView,
    OperatorsListView,
)
from affiliation.api.test_views import MockDocumentServiceView, MockDocumentServiceWrappedView

urlpatterns = [
    path(
        "citizens/<str:citizen_id>/validate/",
        ValidateCitizenView.as_view(),
        name="validate-citizen",
    ),
    path("citizens/register/", RegisterCitizenView.as_view(), name="register-citizen"),
    path("citizens/transfer/receive/", TransferReceiveView.as_view(), name="transfer-receive"),
    path("citizens/<str:citizen_id>/transfer/", TransferSendView.as_view(), name="transfer-send"),
    path("citizens/transfer/confirm/", TransferConfirmView.as_view(), name="transfer-confirm"),
    # Affiliation management endpoints
    path(
        "affiliations/<str:citizen_id>/status/",
        AffiliationStatusView.as_view(),
        name="affiliation-status",
    ),
    path(
        "affiliations/<str:citizen_id>/", AffiliationDeleteView.as_view(), name="affiliation-delete"
    ),
    # Operators endpoints
    path("operators/", OperatorsListView.as_view(), name="operators-list"),
    # Test endpoints (for development only)
    path(
        "test/documents/<str:citizen_id>/", MockDocumentServiceView.as_view(), name="mock-documents"
    ),
    path(
        "test/documents-wrapped/<str:citizen_id>/",
        MockDocumentServiceWrappedView.as_view(),
        name="mock-documents-wrapped",
    ),
]
