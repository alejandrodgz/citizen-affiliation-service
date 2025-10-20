"""
URL configuration for citizen affiliation service.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from affiliation.api.health import health_check, readiness_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("affiliation.api.urls")),
    path("api/health/", health_check, name="health_check"),
    path("api/ready/", readiness_check, name="readiness_check"),
]

# In development, Django's runserver automatically serves static files
# from each app's static/ directory (including django.contrib.admin)
# No additional configuration needed for DEBUG=True
