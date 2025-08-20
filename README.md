# DCPlant - Dental Franchise Case Sharing Platform

A collaborative platform for dental franchises to share treatment cases across headquarters and branches.

## Features

- Multi-tenant architecture (HQ + 3 branches)
- Role-based access control (RBAC)
- Patient and case management
- Treatment plan versioning and approval workflow
- File uploads with de-identification
- Cross-branch case sharing
- Audit logging and compliance features

## Tech Stack

- **Backend**: Django 5 + Django REST Framework
- **Database**: PostgreSQL
- **Cache/Queue**: Redis + Celery
- **Storage**: S3-compatible object storage
- **Deployment**: Docker/Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Development Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd dcplant
```

2. Copy environment variables:
```bash
cp backend/.env.example backend/.env
```

3. Start services with Docker Compose:
```bash
docker-compose up -d
```

4. Run migrations:
```bash
docker-compose exec web python manage.py migrate
```

5. Create superuser:
```bash
docker-compose exec web python manage.py createsuperuser
```

6. Access the application:
- API: http://localhost:8000
- Admin: http://localhost:8000/admin

### Running Tests

```bash
docker-compose exec web pytest
```

### Code Quality

```bash
# Format code
docker-compose exec web black .
docker-compose exec web isort .

# Lint code
docker-compose exec web flake8 .
```

## Project Structure

```
dcplant/
├── backend/           # Django project
│   ├── core/         # Project settings
│   ├── accounts/     # User management app
│   └── ...
├── infra/            # Infrastructure configs
├── docs/             # Documentation
├── ops/              # Operations scripts
└── docker-compose.yml
```

## API Documentation

Once the server is running, API documentation is available at:
- http://localhost:8000/api/schema/swagger-ui/

## Security

See [docs/security.md](docs/security.md) for security configuration details.

## License

Proprietary - All rights reserved