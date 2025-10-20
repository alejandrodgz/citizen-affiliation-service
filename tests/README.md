# Testing Guide for Citizen Affiliation Service

## Overview

This test suite provides comprehensive coverage for the citizen affiliation service, including:
- **Unit Tests**: Service layer logic (CitizenService, TransferService)
- **API Tests**: REST endpoint testing
- **Consumer Tests**: RabbitMQ event handlers
- **Integration Tests**: Complete end-to-end flows

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and test configuration
├── test_citizen_service.py        # CitizenService unit tests
├── test_transfer_service.py       # TransferService unit tests
├── test_api_endpoints.py          # REST API endpoint tests
├── test_consumers.py              # RabbitMQ consumer tests
└── test_integration_flows.py     # End-to-end integration tests
```

## Prerequisites

### Install Test Dependencies

```bash
pip install -r requirements.txt
```

Required test packages:
- `pytest` - Test framework
- `pytest-django` - Django integration
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Enhanced mocking
- `pytest-xdist` - Parallel test execution
- `factory-boy` - Test data factories
- `responses` - HTTP request mocking
- `freezegun` - Time mocking

### Database Setup

Tests use an in-memory SQLite database by default (configured in pytest.ini).
No additional database setup required for testing.

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
# Unit tests only
pytest tests/test_citizen_service.py
pytest tests/test_transfer_service.py

# API tests only
pytest tests/test_api_endpoints.py

# Consumer tests only
pytest tests/test_consumers.py

# Integration tests only
pytest tests/test_integration_flows.py
```

### Run Specific Test Classes

```bash
pytest tests/test_transfer_service.py::TestTransferServiceSendTransfer
pytest tests/test_api_endpoints.py::TestCitizenRegistrationAPI
```

### Run Specific Test Methods

```bash
pytest tests/test_transfer_service.py::TestTransferServiceSendTransfer::test_send_transfer_success
```

### Run with Coverage

```bash
# Generate coverage report
pytest --cov=affiliation --cov-report=html --cov-report=term-missing

# View HTML coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Run Tests in Parallel

```bash
# Run with 4 workers
pytest -n 4

# Run with auto-detected CPU cores
pytest -n auto
```

### Run with Verbose Output

```bash
pytest -v
pytest -vv  # Extra verbose
```

### Run Only Failed Tests

```bash
# Run tests, then re-run only failures
pytest --lf

# Run failures first, then others
pytest --ff
```

## Test Coverage Goals

| Component | Current Coverage | Goal |
|-----------|-----------------|------|
| Services | ~80% | 90% |
| API Views | ~75% | 85% |
| Consumers | ~70% | 80% |
| Models | ~60% | 75% |
| **Overall** | **~75%** | **85%** |

## Writing New Tests

### Using Fixtures

Common fixtures available in `conftest.py`:

```python
def test_example(affiliated_citizen, sample_target_operator, mock_rabbitmq_publisher):
    """Example test using fixtures."""
    citizen, affiliation = affiliated_citizen
    # Test logic here
```

Available fixtures:
- `affiliated_citizen` - Fully affiliated citizen with affiliation
- `transferring_citizen` - Citizen in TRANSFERRING state
- `sample_citizen_data` - Sample citizen dict
- `sample_operator_data` - Sample operator dict
- `sample_transfer_data` - Sample transfer payload
- `mock_rabbitmq_publisher` - Mocked RabbitMQ publisher
- `mock_requests_get/post` - Mocked HTTP requests

### Test Naming Convention

Follow pytest naming conventions:
- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

### Organizing Tests

Group related tests in classes:

```python
@pytest.mark.django_db
class TestTransferServiceSendTransfer:
    """Test cases for sending outgoing transfers."""
    
    def setup_method(self):
        """Set up test dependencies."""
        self.service = TransferService()
    
    def test_send_transfer_success(self, affiliated_citizen):
        """Test successful transfer initiation."""
        # Test implementation
```

### Mocking External Services

Use `@patch` decorator for external API calls:

```python
@patch('affiliation.services.transfer_service.requests.post')
def test_with_external_api(self, mock_post):
    """Test with mocked external API."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {'success': True}
    
    # Test logic
```

## Common Test Patterns

### Testing Service Methods

```python
@pytest.mark.django_db
def test_service_method(self, affiliated_citizen):
    """Test service layer method."""
    service = TransferService()
    citizen, affiliation = affiliated_citizen
    
    result = service.some_method(citizen.id)
    
    assert result['success'] is True
    affiliation.refresh_from_db()
    assert affiliation.status == 'EXPECTED_STATUS'
```

### Testing API Endpoints

```python
@pytest.mark.django_db
def test_api_endpoint(self, client, affiliated_citizen):
    """Test API endpoint."""
    citizen, _ = affiliated_citizen
    url = reverse('endpoint-name', kwargs={'citizen_id': citizen.id})
    
    response = client.get(url)
    
    assert response.status_code == 200
    assert response.data['field'] == 'expected_value'
```

### Testing Event Consumers

```python
@pytest.mark.django_db
@patch('affiliation.rabbitmq.register_citizen_consumer.publish_event')
def test_consumer(self, mock_publish, create_citizen):
    """Test event consumer."""
    citizen = create_citizen(is_verified=False)
    
    event_data = {'id': citizen.id, 'statusCode': 201}
    handle_register_completed(event_data)
    
    citizen.refresh_from_db()
    assert citizen.is_verified is True
```

### Testing Integration Flows

```python
@pytest.mark.django_db
@patch('affiliation.services.transfer_service.requests.post')
def test_integration_flow(self, mock_post):
    """Test complete end-to-end flow."""
    # Step 1: Initial action
    # Step 2: Simulate event
    # Step 3: Verify final state
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests with coverage
      run: |
        pytest --cov=affiliation --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

## Troubleshooting

### Tests Failing Due to RabbitMQ

If tests fail due to RabbitMQ connection issues:
- Ensure `mock_rabbitmq_publisher` fixture is used
- Check that `@patch` decorators are properly applied

### Tests Failing Due to Database

If tests fail due to database issues:
- Ensure `@pytest.mark.django_db` decorator is present
- Check that migrations are up to date

### Tests Timing Out

If tests timeout:
- Reduce timeout values in test configuration
- Use mocks for external API calls
- Run tests in parallel: `pytest -n auto`

## Best Practices

1. **Keep tests isolated** - Each test should be independent
2. **Use fixtures** - Reuse common test setup via fixtures
3. **Mock external dependencies** - Don't make real API calls in tests
4. **Test edge cases** - Test failures, missing data, invalid inputs
5. **Maintain test data** - Keep test data realistic but minimal
6. **Document complex tests** - Add docstrings explaining test purpose
7. **Run tests frequently** - Run tests before committing changes
8. **Aim for high coverage** - Target 80%+ code coverage

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)
- [Django Testing Guide](https://docs.djangoproject.com/en/5.0/topics/testing/)
- [Mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
