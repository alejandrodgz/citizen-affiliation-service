.PHONY: help install migrate test run docker-up docker-down rabbitmq-up rabbitmq-down rabbitmq-logs rabbitmq-ui clean check-queue test-rabbitmq test-unit test-api test-consumers test-integration test-coverage test-fast test-parallel

help:
	@echo "Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  install         Install Python dependencies"
	@echo "  migrate         Run database migrations"
	@echo "  run             Run Django development server"
	@echo ""
	@echo "Testing:"
	@echo "  test            Run all tests"
	@echo "  test-unit       Run unit tests only"
	@echo "  test-api        Run API endpoint tests"
	@echo "  test-consumers  Run consumer tests"
	@echo "  test-integration Run integration tests"
	@echo "  test-coverage   Run tests with coverage report"
	@echo "  test-fast       Run fast tests (skip integration)"
	@echo "  test-parallel   Run tests in parallel"
	@echo ""
	@echo "Docker Services:"
	@echo "  docker-up       Start all services (RabbitMQ + MariaDB)"
	@echo "  docker-down     Stop all services"
	@echo "  rabbitmq-up     Start only RabbitMQ and DB"
	@echo "  rabbitmq-down   Stop RabbitMQ and DB"
	@echo "  rabbitmq-logs   View RabbitMQ logs"
	@echo "  rabbitmq-ui     Open RabbitMQ Management UI"
	@echo ""
	@echo "RabbitMQ Tools:"
	@echo "  check-queue     Check messages in user.transferred queue"
	@echo "  test-rabbitmq   Test RabbitMQ connection and publish test event"
	@echo ""
	@echo "Utilities:"
	@echo "  clean           Clean Python cache files"

install:
	pip install -r requirements.txt

migrate:
	python manage.py makemigrations
	python manage.py migrate

test:
	pytest -v

test-unit:
	pytest tests/test_citizen_service.py tests/test_transfer_service.py -v

test-api:
	pytest tests/test_api_endpoints.py -v

test-consumers:
	pytest tests/test_consumers.py -v

test-integration:
	pytest tests/test_integration_flows.py -v

test-coverage:
	pytest --cov=affiliation --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "✅ Coverage report generated in htmlcov/index.html"

test-fast:
	pytest tests/test_citizen_service.py tests/test_transfer_service.py tests/test_api_endpoints.py -v

test-parallel:
	pytest -n auto -v

run:
	python manage.py runserver

docker-up:
	docker-compose up -d rabbitmq db

docker-down:
	docker-compose down

rabbitmq-up:
	docker-compose up -d rabbitmq db
	@echo "✅ RabbitMQ and MariaDB started"
	@echo "🌐 RabbitMQ Management UI: http://localhost:15672 (admin/admin)"

rabbitmq-down:
	docker-compose stop rabbitmq db

rabbitmq-logs:
	docker-compose logs -f rabbitmq

rabbitmq-ui:
	@echo "Opening RabbitMQ Management UI..."
	@xdg-open http://localhost:15672 2>/dev/null || open http://localhost:15672 2>/dev/null || echo "Open http://localhost:15672 in your browser (admin/admin)"

check-queue:
	@python -c "import pika, json; \
		credentials = pika.PlainCredentials('admin', 'admin'); \
		connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', credentials=credentials)); \
		channel = connection.channel(); \
		queue = channel.queue_declare(queue='user.transferred', durable=True, passive=True); \
		print(f'📊 Queue: user.transferred'); \
		print(f'📬 Messages ready: {queue.method.message_count}'); \
		connection.close()"

test-rabbitmq:
	python test_rabbitmq.py

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +
	find . -type d -name "htmlcov" -exec rm -r {} +
