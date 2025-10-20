#!/bin/bash

# Test runner script for Citizen Affiliation Service
# Provides common test execution commands

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}  Citizen Affiliation Test Suite ${NC}"
echo -e "${BLUE}==================================${NC}\n"

# Parse command line arguments
COMMAND=${1:-"all"}

case $COMMAND in
  all)
    echo -e "${GREEN}Running all tests...${NC}"
    pytest -v
    ;;
  
  unit)
    echo -e "${GREEN}Running unit tests...${NC}"
    pytest tests/test_citizen_service.py tests/test_transfer_service.py -v
    ;;
  
  api)
    echo -e "${GREEN}Running API tests...${NC}"
    pytest tests/test_api_endpoints.py -v
    ;;
  
  consumers)
    echo -e "${GREEN}Running consumer tests...${NC}"
    pytest tests/test_consumers.py -v
    ;;
  
  integration)
    echo -e "${GREEN}Running integration tests...${NC}"
    pytest tests/test_integration_flows.py -v
    ;;
  
  coverage)
    echo -e "${GREEN}Running tests with coverage report...${NC}"
    pytest --cov=affiliation --cov-report=html --cov-report=term-missing
    echo -e "\n${YELLOW}Coverage report generated in htmlcov/index.html${NC}"
    ;;
  
  parallel)
    echo -e "${GREEN}Running tests in parallel...${NC}"
    pytest -n auto -v
    ;;
  
  fast)
    echo -e "${GREEN}Running fast tests (no integration)...${NC}"
    pytest tests/test_citizen_service.py tests/test_transfer_service.py tests/test_api_endpoints.py -v
    ;;
  
  failed)
    echo -e "${GREEN}Re-running failed tests...${NC}"
    pytest --lf -v
    ;;
  
  watch)
    echo -e "${GREEN}Running tests in watch mode...${NC}"
    echo -e "${YELLOW}Note: Requires pytest-watch (pip install pytest-watch)${NC}"
    ptw
    ;;
  
  clean)
    echo -e "${GREEN}Cleaning test artifacts...${NC}"
    rm -rf .pytest_cache htmlcov .coverage
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}Clean complete!${NC}"
    ;;
  
  help)
    echo -e "${YELLOW}Usage: ./run_tests.sh [command]${NC}\n"
    echo -e "Available commands:"
    echo -e "  ${GREEN}all${NC}         - Run all tests (default)"
    echo -e "  ${GREEN}unit${NC}        - Run unit tests only"
    echo -e "  ${GREEN}api${NC}         - Run API endpoint tests"
    echo -e "  ${GREEN}consumers${NC}   - Run consumer tests"
    echo -e "  ${GREEN}integration${NC} - Run integration tests"
    echo -e "  ${GREEN}coverage${NC}    - Run tests with coverage report"
    echo -e "  ${GREEN}parallel${NC}    - Run tests in parallel"
    echo -e "  ${GREEN}fast${NC}        - Run fast tests (skip integration)"
    echo -e "  ${GREEN}failed${NC}      - Re-run only failed tests"
    echo -e "  ${GREEN}watch${NC}       - Run tests in watch mode"
    echo -e "  ${GREEN}clean${NC}       - Clean test artifacts"
    echo -e "  ${GREEN}help${NC}        - Show this help message"
    echo ""
    ;;
  
  *)
    echo -e "${RED}Unknown command: $COMMAND${NC}"
    echo -e "Run ${GREEN}./run_tests.sh help${NC} for available commands"
    exit 1
    ;;
esac

echo ""
