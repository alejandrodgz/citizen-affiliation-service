#!/bin/bash
# Kubernetes Deployment Script for Citizen Affiliation Service

set -e  # Exit on error

echo "=========================================="
echo "Citizen Affiliation Service - K8s Deploy"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="citizen-affiliation-service"
IMAGE_TAG="${1:-latest}"
NAMESPACE="citizen-affiliation"

echo -e "${YELLOW}Step 1: Stopping Docker Compose...${NC}"
if [ -f docker-compose.yml ]; then
    docker-compose down || true
    echo -e "${GREEN}✓ Docker Compose stopped${NC}"
else
    echo -e "${YELLOW}⚠ No docker-compose.yml found, skipping...${NC}"
fi
echo ""

echo -e "${YELLOW}Step 2: Building Docker image...${NC}"
echo "Building ${IMAGE_NAME}:${IMAGE_TAG}"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
echo -e "${GREEN}✓ Docker image built successfully${NC}"
echo ""

echo -e "${YELLOW}Step 3: Checking Kubernetes cluster...${NC}"
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}✗ Cannot connect to Kubernetes cluster${NC}"
    echo "Please ensure:"
    echo "  - Kubernetes is running (minikube, kind, k3s, etc.)"
    echo "  - kubectl is properly configured"
    exit 1
fi
echo -e "${GREEN}✓ Kubernetes cluster is accessible${NC}"
kubectl cluster-info | head -n 1
echo ""

echo -e "${YELLOW}Step 4: Loading image to Kubernetes...${NC}"
# Detect which K8s platform is being used
if command -v minikube &> /dev/null && minikube status &> /dev/null; then
    echo "Detected Minikube - loading image..."
    minikube image load ${IMAGE_NAME}:${IMAGE_TAG}
    echo -e "${GREEN}✓ Image loaded to Minikube${NC}"
elif command -v kind &> /dev/null; then
    echo "Detected kind - loading image..."
    kind load docker-image ${IMAGE_NAME}:${IMAGE_TAG}
    echo -e "${GREEN}✓ Image loaded to kind${NC}"
elif command -v k3s &> /dev/null; then
    echo "Detected k3s - importing image..."
    docker save ${IMAGE_NAME}:${IMAGE_TAG} | sudo k3s ctr images import -
    echo -e "${GREEN}✓ Image imported to k3s${NC}"
else
    echo -e "${YELLOW}⚠ Using local Docker images (assuming Docker Desktop K8s)${NC}"
fi
echo ""

echo -e "${YELLOW}Step 5: Creating namespace...${NC}"
kubectl apply -f k8s/namespace.yaml
echo -e "${GREEN}✓ Namespace created/updated${NC}"
echo ""

echo -e "${YELLOW}Step 6: Deploying ConfigMap and Secrets...${NC}"
echo -e "${RED}⚠ WARNING: Using default secrets - CHANGE IN PRODUCTION!${NC}"
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
echo -e "${GREEN}✓ ConfigMap and Secrets deployed${NC}"
echo ""

echo -e "${YELLOW}Step 7: Deploying Persistent Volume...${NC}"
kubectl apply -f k8s/persistent-volume.yaml
echo -e "${GREEN}✓ Persistent Volume created${NC}"
echo ""

echo -e "${YELLOW}Step 8: Deploying RabbitMQ...${NC}"
kubectl apply -f k8s/rabbitmq-deployment.yaml
echo "Waiting for RabbitMQ to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/rabbitmq -n ${NAMESPACE} || true
echo -e "${GREEN}✓ RabbitMQ deployed${NC}"
echo ""

echo -e "${YELLOW}Step 9: Deploying Django API...${NC}"
kubectl apply -f k8s/django-deployment.yaml
echo "Waiting for Django API to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/citizen-affiliation-api -n ${NAMESPACE} || true
echo -e "${GREEN}✓ Django API deployed${NC}"
echo ""

echo -e "${YELLOW}Step 10: Deploying Consumers...${NC}"
kubectl apply -f k8s/consumer-deployment.yaml
echo -e "${GREEN}✓ Consumers deployed${NC}"
echo ""

echo -e "${YELLOW}Step 11: Deploying Ingress...${NC}"
kubectl apply -f k8s/ingress.yaml || echo -e "${YELLOW}⚠ Ingress deployment failed (may need ingress controller)${NC}"
echo ""

echo -e "${YELLOW}Step 12: Deploying HPA...${NC}"
kubectl apply -f k8s/hpa.yaml || echo -e "${YELLOW}⚠ HPA deployment failed (may need metrics server)${NC}"
echo ""

echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "Check deployment status:"
echo "  kubectl get all -n ${NAMESPACE}"
echo ""
echo "View logs:"
echo "  kubectl logs -f deployment/citizen-affiliation-api -n ${NAMESPACE}"
echo ""
echo "Port forward to test locally:"
echo "  kubectl port-forward svc/citizen-affiliation-api-service 8000:8000 -n ${NAMESPACE}"
echo ""
echo "Access RabbitMQ management:"
echo "  kubectl port-forward svc/rabbitmq-service 15672:15672 -n ${NAMESPACE}"
echo "  Then open: http://localhost:15672 (guest/guest)"
echo ""
