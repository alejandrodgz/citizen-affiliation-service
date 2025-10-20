#!/bin/bash

set -e

echo "🚀 Citizen Affiliation Service - Kubernetes Deployment"
echo "======================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Step 1: Stopping Docker Compose...${NC}"
if [ -f "docker-compose.yml" ]; then
    docker-compose down
    echo -e "${GREEN}✅ Docker Compose stopped${NC}"
else
    echo -e "${YELLOW}⚠️  docker-compose.yml not found, skipping...${NC}"
fi
echo ""

echo -e "${YELLOW}🏗️  Step 2: Building Docker image...${NC}"
docker build -t citizen-affiliation-service:latest .
echo -e "${GREEN}✅ Docker image built successfully${NC}"
echo ""

echo -e "${YELLOW}📋 Step 3: Creating namespace...${NC}"
kubectl apply -f k8s/namespace.yaml
echo -e "${GREEN}✅ Namespace created${NC}"
echo ""

echo -e "${YELLOW}⚙️  Step 4: Creating ConfigMap and Secrets...${NC}"
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
echo -e "${GREEN}✅ ConfigMap and Secrets created${NC}"
echo ""

echo -e "${YELLOW}💾 Step 5: Deploying MySQL...${NC}"
kubectl apply -f k8s/mysql-deployment.yaml
echo "Waiting for MySQL to be ready..."
kubectl wait --for=condition=available --timeout=180s deployment/mysql -n citizen-affiliation 2>/dev/null || true
sleep 10
echo -e "${GREEN}✅ MySQL deployed${NC}"
echo ""

echo -e "${YELLOW}🐰 Step 6: Deploying RabbitMQ...${NC}"
kubectl apply -f k8s/rabbitmq-deployment.yaml
echo "Waiting for RabbitMQ to be ready..."
kubectl wait --for=condition=available --timeout=180s deployment/rabbitmq -n citizen-affiliation 2>/dev/null || true
sleep 10
echo -e "${GREEN}✅ RabbitMQ deployed${NC}"
echo ""

echo -e "${YELLOW}🌐 Step 7: Deploying Django API...${NC}"
kubectl apply -f k8s/django-deployment.yaml
echo "Waiting for Django API to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/citizen-affiliation-api -n citizen-affiliation 2>/dev/null || true
echo -e "${GREEN}✅ Django API deployed${NC}"
echo ""

echo -e "${YELLOW}👷 Step 8: Deploying Consumers...${NC}"
kubectl apply -f k8s/consumer-deployment.yaml
echo -e "${GREEN}✅ Consumers deployed${NC}"
echo ""

echo -e "${YELLOW}🌍 Step 9: Deploying Ingress...${NC}"
kubectl apply -f k8s/ingress.yaml
echo -e "${GREEN}✅ Ingress deployed${NC}"
echo ""

echo -e "${YELLOW}📊 Step 10: Deploying HPA...${NC}"
kubectl apply -f k8s/hpa.yaml
echo -e "${GREEN}✅ HPA deployed${NC}"
echo ""

echo "======================================================="
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "======================================================="
echo ""
echo "📊 Current Status:"
kubectl get all -n citizen-affiliation
echo ""
echo "🔍 Useful Commands:"
echo ""
echo "  # Check pod status:"
echo "  kubectl get pods -n citizen-affiliation"
echo ""
echo "  # View logs:"
echo "  kubectl logs -f deployment/citizen-affiliation-api -n citizen-affiliation"
echo ""
echo "  # Port forward to access API locally:"
echo "  kubectl port-forward svc/citizen-affiliation-api-service 8000:8000 -n citizen-affiliation"
echo ""
echo "  # Access RabbitMQ Management UI:"
echo "  kubectl port-forward svc/rabbitmq-service 15672:15672 -n citizen-affiliation"
echo "  Then open: http://localhost:15672 (user: guest, pass: admin)"
echo ""
echo "  # Check MySQL:"
echo "  kubectl exec -it deployment/mysql -n citizen-affiliation -- mysql -u djangouser -p citizen_affiliation"
echo ""
echo "  # Delete everything:"
echo "  kubectl delete namespace citizen-affiliation"
echo ""
