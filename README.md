# MyCurrency - Currency Exchange Rate Platform

A Django-based web platform for calculating currency exchange rates.

## Supported Currencies

- EUR
- USD
- GBP
- CHF

## Technology Stack

- **Python**: 3.11+
- **Django**: >=4.0,<=5.0
- **Django REST Framework**: REST API
- **Celery + Redis**: Async task processing
- **SQLite**: Database
- **httpx**: Async HTTP client
- **drf-spectacular**: OpenAPI documentation

## Project Structure

```
mycurrency/
├── adapters/                   # Exchange rate provider adapters
│   ├── base.py                # Abstract base adapter
│   ├── currencybeacon.py      # CurrencyBeacon API adapter
│   └── mock.py                # Mock data adapter
├── apps/
│   ├── currencies/            # Currency models and API
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   └── providers/             # Provider management
│       ├── models.py
│       └── admin.py
├── config/                    # Django project settings
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   └── celery.py
├── services/                  # Business logic layer
│   ├── exchange_rate_service.py
│   └── provider_manager.py
├── tasks/                     # Celery async tasks
│   └── historical_data.py
├── templates/                 # Django templates
├── tests/                     # Test suite
├── fixtures/                  # Initial data
└── scripts/                   # Utility scripts
```

## Quick Start

### Prerequisites

- Python 3.11+
- pip
- Redis (for Celery)
- PostgreSQL (optional, SQLite works for development)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mycurrency
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   make install
   # or
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run migrations and load initial data**
   ```bash
   make dev
   # or
   python manage.py makemigrations
   python manage.py migrate
   python manage.py loaddata fixtures/initial_data.json
   ```

6. **Create a superuser**
   ```bash
   make superuser
   # or
   python manage.py createsuperuser
   ```

7. **Start the development server**
   ```bash
   make run
   # or
   python manage.py runserver
   ```

### Using Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | (dev key) |
| `DEBUG` | Debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `DATABASE_URL` | Database connection URL | SQLite |
| `CELERY_BROKER_URL` | Redis URL for Celery | `redis://localhost:6379/0` |
| `CURRENCY_BEACON_API_KEY` | CurrencyBeacon API key | (empty) |

### CurrencyBeacon Setup

1. Register at https://currencybeacon.com/register
2. Get your API key
3. Add to `.env`: `CURRENCY_BEACON_API_KEY=currencybeacon-api-key`
4. Enable the CurrencyBeacon provider in Django Admin

## API Endpoints

### Currencies (CRUD)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/currencies/` | List all currencies |
| POST | `/api/v1/currencies/` | Create a currency |
| GET | `/api/v1/currencies/{code}/` | Get currency by code |
| PUT | `/api/v1/currencies/{code}/` | Update currency |
| DELETE | `/api/v1/currencies/{code}/` | Delete currency |

### Exchange Rates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/rates/` | Get rates for a time period |
| POST | `/api/v1/rates/load-historical/` | Load historical data (async) |

**Query Parameters for `/api/v1/rates/`:**
- `source_currency`: Source currency code (required)
- `date_from`: Start date YYYY-MM-DD (required)
- `date_to`: End date YYYY-MM-DD (required)

### Currency Converter

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/convert/` | Convert amount between currencies |

**Query Parameters:**
- `source_currency`: Source currency code
- `exchanged_currency`: Target currency code
- `amount`: Amount to convert

### API Documentation

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **OpenAPI Schema**: http://localhost:8000/api/schema/

## Provider Management

Providers can be managed via Django Admin at `/admin/providers/provider/`.

### Priority System
- Lower priority number = higher preference
- Providers are tried in priority order
- Failed providers are skipped, next one is tried

### Available Providers

1. **CurrencyBeacon**
   - Real exchange rate data
   - Requires API key
   - Adapter: `adapters.currencybeacon.CurrencyBeaconAdapter`

2. **Mock Provider**
   - Generates realistic mock data
   - No API key required
   - Adapter: `adapters.mock.MockAdapter`

### Adding a New Provider

1. Create adapter in `adapters/`:
   ```python
   from adapters.base import BaseExchangeRateAdapter
   
   class MyProviderAdapter(BaseExchangeRateAdapter):
       @property
       def name(self) -> str:
           return "My Provider"
       
       def get_exchange_rate(self, source, target, date):
           # implementation
           pass
   ```

2. Register in Django Admin with adapter path

## Async Historical Data Loading

For loading historical data efficiently:

```bash
# Start Celery worker
make celery

# In another terminal, start Celery beat (for scheduled tasks)
make celery-beat
```

**Why Concurrency over Parallelism?**

Historical data loading is I/O-bound (API calls), not CPU-bound. Concurrency with async I/O is:
- More memory efficient
- Better for network-bound operations
- Lower overhead than multiprocessing

## Generating Test Data

```bash
# Generate 1 year of mock data
python scripts/generate_mock_data.py

# Generate 30 days of sample data
python scripts/generate_mock_data.py --sample

# Custom number of days
python scripts/generate_mock_data.py --days 90
```

## Admin Interface

Access at: http://localhost:8000/admin/

### Custom Converter View

Navigate to Admin → Currency Converter to:
- Select source currency
- Enter amount
- Select multiple target currencies
- View all conversions at once

## Testing

```bash
# Run all tests
make test

# Run with coverage
pytest -v --cov=apps --cov=adapters --cov=services

# Run specific tests
pytest tests/test_adapters.py -v
```

## API Versioning

The API supports versioning via URL path:
- Current: `/api/v1/...`
- Future versions: `/api/v2/...`

Configure in `settings.py`:
```python
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],
}
```

## Postman Collection

Import `postman_collection.json` into Postman for ready-to-use API requests.

## Future Improvements

1. **Rate Limiting**: Implement API rate limiting
2. **Authentication**: Add auth to the API
3. **More Providers**: Integrate additional data sources
4. **Real-time Updates**: WebSocket for live rate updates
5. **Monitoring**: Add logs and metrics monitoring (like Grafana or Datadog)
6. **CI/CD**: Add GitHub Actions workflow
