# Kubernetes Deployment Guide

This directory contains Kubernetes manifests for deploying the Citizen Affiliation Service.

## Architecture

The deployment consists of:

- **Django API** (3 replicas with HPA): Main REST API server
- **RabbitMQ** (1 replica): Message broker for event-driven architecture
- **Register Consumer** (2 replicas): Handles registration events
- **Unregister Consumer** (2 replicas): Handles unregistration events
- **Documents Consumer** (2 replicas): Handles document-ready events

## Prerequisites

1. **Kubernetes cluster** (v1.24+)
2. **kubectl** configured to access your cluster
3. **Docker image** of the application built and available
4. **Ingress controller** (NGINX recommended)
5. **cert-manager** (optional, for TLS/SSL)

## Building the Docker Image

First, build and tag your Docker image:

```bash
# Build the image
docker build -t citizen-affiliation-service:latest .

# Tag for your registry
docker tag citizen-affiliation-service:latest your-registry/citizen-affiliation-service:latest

# Push to registry
docker push your-registry/citizen-affiliation-service:latest
```

## Configuration

### 1. Update Secrets (IMPORTANT!)

Edit `secrets.yaml` and change all default values:

```bash
# Generate a secure Django secret key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Update secrets.yaml with your values
kubectl create secret generic citizen-affiliation-secrets \
  --from-literal=DJANGO_SECRET_KEY='your-generated-secret-key' \
  --from-literal=RABBITMQ_PASSWORD='your-rabbitmq-password' \
  --dry-run=client -o yaml > secrets.yaml
```

### 2. Update ConfigMap

Edit `configmap.yaml` to match your environment:

- `ALLOWED_HOSTS`: Your domain names
- `GOVCARPETA_API_URL`: External API endpoint
- `DOCUMENT_SERVICE_URL`: Document service endpoint

### 3. Update Ingress

Edit `ingress.yaml`:

- Replace `affiliation.yourdomain.com` with your actual domain
- Update annotations for your ingress controller

## Deployment

### Quick Deploy (All Resources)

```bash
# Apply all manifests
kubectl apply -k k8s/

# Or apply individually
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/persistent-volume.yaml
kubectl apply -f k8s/rabbitmq-deployment.yaml
kubectl apply -f k8s/django-deployment.yaml
kubectl apply -f k8s/consumer-deployment.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml
```

### Step-by-Step Deploy

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Create ConfigMap and Secrets
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# 3. Create Persistent Volume
kubectl apply -f k8s/persistent-volume.yaml

# 4. Deploy RabbitMQ (wait for it to be ready)
kubectl apply -f k8s/rabbitmq-deployment.yaml
kubectl wait --for=condition=available --timeout=300s deployment/rabbitmq -n citizen-affiliation

# 5. Deploy Django API
kubectl apply -f k8s/django-deployment.yaml
kubectl wait --for=condition=available --timeout=300s deployment/citizen-affiliation-api -n citizen-affiliation

# 6. Deploy Consumers
kubectl apply -f k8s/consumer-deployment.yaml

# 7. Deploy Ingress
kubectl apply -f k8s/ingress.yaml

# 8. Deploy HPA
kubectl apply -f k8s/hpa.yaml
```

## Verification

```bash
# Check all resources
kubectl get all -n citizen-affiliation

# Check pods status
kubectl get pods -n citizen-affiliation

# Check logs
kubectl logs -f deployment/citizen-affiliation-api -n citizen-affiliation

# Check consumer logs
kubectl logs -f deployment/citizen-affiliation-register-consumer -n citizen-affiliation

# Check RabbitMQ logs
kubectl logs -f deployment/rabbitmq -n citizen-affiliation

# Port forward to test locally
kubectl port-forward svc/citizen-affiliation-api-service 8000:8000 -n citizen-affiliation
```

## Health Checks

The API includes health check endpoints:

```bash
# Test health endpoint
curl http://localhost:8000/api/health/

# Or through ingress
curl https://affiliation.yourdomain.com/api/health/
```

## Scaling

### Manual Scaling

```bash
# Scale API
kubectl scale deployment citizen-affiliation-api --replicas=5 -n citizen-affiliation

# Scale consumers
kubectl scale deployment citizen-affiliation-register-consumer --replicas=3 -n citizen-affiliation
```

### Auto-scaling (HPA)

The HPA is configured to scale based on CPU (70%) and memory (80%) usage:

```bash
# Check HPA status
kubectl get hpa -n citizen-affiliation

# Describe HPA
kubectl describe hpa citizen-affiliation-api-hpa -n citizen-affiliation
```

## Database Migrations

Migrations run automatically via init container. To run manually:

```bash
kubectl exec -it deployment/citizen-affiliation-api -n citizen-affiliation -- python manage.py migrate
```

## RabbitMQ Management

Access RabbitMQ management UI:

```bash
# Port forward
kubectl port-forward svc/rabbitmq-service 15672:15672 -n citizen-affiliation

# Open http://localhost:15672
# Default credentials: guest/guest (change in production!)
```

## Monitoring

```bash
# Watch pod status
kubectl get pods -n citizen-affiliation -w

# View resource usage
kubectl top pods -n citizen-affiliation
kubectl top nodes

# View events
kubectl get events -n citizen-affiliation --sort-by='.lastTimestamp'
```

## Troubleshooting

### Pods not starting

```bash
# Describe pod to see events
kubectl describe pod <pod-name> -n citizen-affiliation

# Check logs
kubectl logs <pod-name> -n citizen-affiliation

# Check previous logs if pod crashed
kubectl logs <pod-name> -n citizen-affiliation --previous
```

### Database connection issues

```bash
# Check if PVC is bound
kubectl get pvc -n citizen-affiliation

# Check PV status
kubectl get pv
```

### RabbitMQ connection issues

```bash
# Test RabbitMQ connectivity
kubectl exec -it deployment/citizen-affiliation-api -n citizen-affiliation -- python manage.py shell

# In Python shell:
from affiliation.rabbitmq.publisher import RabbitMQPublisher
publisher = RabbitMQPublisher()
```

## Updating the Application

```bash
# Build new image
docker build -t citizen-affiliation-service:v1.1.0 .
docker push your-registry/citizen-affiliation-service:v1.1.0

# Update deployments
kubectl set image deployment/citizen-affiliation-api \
  django=your-registry/citizen-affiliation-service:v1.1.0 \
  -n citizen-affiliation

# Rolling restart
kubectl rollout restart deployment/citizen-affiliation-api -n citizen-affiliation
kubectl rollout status deployment/citizen-affiliation-api -n citizen-affiliation
```

## Cleanup

```bash
# Delete all resources
kubectl delete -k k8s/

# Or delete namespace (removes everything)
kubectl delete namespace citizen-affiliation
```

## Production Considerations

1. **Use PostgreSQL/MySQL** instead of SQLite:
   - Update `configmap.yaml` with proper DB credentials
   - Deploy a database StatefulSet or use cloud provider's managed DB

2. **Use external RabbitMQ cluster** for production:
   - CloudAMQP, AWS MQ, or self-hosted RabbitMQ cluster
   - Update connection details in ConfigMap

3. **Enable TLS/SSL**:
   - Install cert-manager
   - Configure Let's Encrypt or use your own certificates

4. **Set up monitoring**:
   - Prometheus + Grafana for metrics
   - ELK/EFK stack for logging
   - Sentry for error tracking

5. **Implement backup strategy**:
   - Database backups via CronJob
   - Persistent volume snapshots

6. **Use secrets management**:
   - Sealed Secrets
   - External Secrets Operator
   - Cloud provider's secret manager (AWS Secrets Manager, Azure Key Vault, etc.)

7. **Network policies**:
   - Restrict pod-to-pod communication
   - Only allow necessary traffic

8. **Resource quotas**:
   - Set namespace resource quotas
   - Implement pod disruption budgets

## Support

For issues and questions, please refer to the main project documentation or create an issue in the repository.
