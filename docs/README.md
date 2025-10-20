# Citizen Affiliation Service

A Django microservice for managing citizen affiliation with Kafka event bus integration.

## Features

- Validate citizen registration
- Register new citizens
- Kafka event-driven architecture
- RESTful API endpoints

## Project Structure

```
citizen-affiliation-service/
├── affiliation/               # Main Django app
│   ├── api/                  # API endpoints
│   ├── models/               # Database models
│   ├── services/             # Business logic
│   ├── kafka/                # Kafka producers/consumers
│   └── tasks/                # Celery tasks
├── config/                   # Django settings
├── docker/                   # Docker configurations
└── tests/                    # Test suite
```

## Setup

### Using Poetry

```bash
poetry install
poetry shell
python manage.py migrate
python manage.py runserver
```

### Using pip

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Environment Variables

Create a `.env` file in the root directory:

```
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=mysql://user:password@localhost:3306/citizen_affiliation
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
GOVCARPETA_API_URL=https://govcarpeta-apis-4905ff3c005b.herokuapp.com
```

## API Endpoints

### Validate Citizen
```
GET /api/v1/citizens/{id}/validate
```

### Register Citizen
```
POST /api/v1/citizens/register
```

## Docker

```bash
docker-compose up -d
```

## Testing

```bash
pytest
```
