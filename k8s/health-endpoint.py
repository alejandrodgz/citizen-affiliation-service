# Health check endpoint to add to your Django views
# Add this to affiliation/api/views.py or create a new health.py file

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from affiliation.rabbitmq.publisher import RabbitMQPublisher
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for Kubernetes liveness and readiness probes.
    
    Returns:
        200 OK: Service is healthy
        503 Service Unavailable: Service has issues
    """
    health_status = {
        'status': 'healthy',
        'checks': {}
    }
    
    # Check database connection
    try:
        connection.ensure_connection()
        health_status['checks']['database'] = 'ok'
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health_status['checks']['database'] = 'error'
        health_status['status'] = 'unhealthy'
    
    # Check RabbitMQ connection
    try:
        publisher = RabbitMQPublisher()
        health_status['checks']['rabbitmq'] = 'ok'
    except Exception as e:
        logger.error(f"RabbitMQ health check failed: {str(e)}")
        health_status['checks']['rabbitmq'] = 'error'
        health_status['status'] = 'unhealthy'
    
    if health_status['status'] == 'healthy':
        return Response(health_status, status=status.HTTP_200_OK)
    else:
        return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_check(request):
    """
    Readiness check - simpler check for Kubernetes readiness probe.
    Just verifies the application is running.
    """
    return Response({'status': 'ready'}, status=status.HTTP_200_OK)


# Add to your urls.py:
# from affiliation.api.views import health_check, readiness_check
# 
# urlpatterns = [
#     path('api/health/', health_check, name='health_check'),
#     path('api/ready/', readiness_check, name='readiness_check'),
#     ...
# ]
