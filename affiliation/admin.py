from django.contrib import admin
from affiliation.models import Citizen, Affiliation


@admin.register(Citizen)
class CitizenAdmin(admin.ModelAdmin):
    list_display = ("citizen_id", "name", "email", "operator_name", "is_registered", "created_at")
    list_filter = ("is_registered", "created_at", "operator_name")
    search_fields = ("citizen_id", "name", "email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Affiliation)
class AffiliationAdmin(admin.ModelAdmin):
    list_display = ("citizen", "operator_name", "status", "affiliated_at", "status_changed_at")
    list_filter = ("status", "affiliated_at", "operator_name")
    search_fields = ("citizen__citizen_id", "citizen__name", "operator_name")
    readonly_fields = ("affiliated_at", "status_changed_at")
    fieldsets = (
        ("Citizen Information", {"fields": ("citizen", "operator_id", "operator_name")}),
        ("Status", {"fields": ("status", "affiliated_at", "status_changed_at")}),
        (
            "Transfer Information",
            {
                "fields": (
                    "transfer_destination_operator_id",
                    "transfer_destination_operator_name",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Additional Information", {"fields": ("notes",), "classes": ("collapse",)}),
    )
