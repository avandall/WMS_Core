# Warehouse Management System (WMS)

A warehouse management system built with Python, FastAPI, and Clean Architecture.

## Quick Start

**Development** (with sample data):
```bash
./start.sh dev
```

**Production** (minimal data):
```bash
./start.sh prod
```

# Seed sample data (see scripts/seed.py for details)
python3 ./scripts/seed.py

## Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Dashboard | http://localhost:8080 | admin@wms.vn / admin123 |
| API | http://localhost:8000 | - |
| API Docs | http://localhost:8000/docs | - |
| Database | localhost:5433 | - |

### User Roles
- `admin@wms.vn` / admin123 - Full access
- `warehouse@wms.vn` / warehouse123 - Operations
- `sales@wms.vn` / sales123 - Import documents
- `accountant@wms.vn` / account123 - Prices + Reports

## Development

**Setup:**
```bash
uv sync  # or: pip install -r requirements.txt
pytest   # run tests
```

**Common Commands:**
```bash
# View logs
docker compose logs -f api

# Database access
docker compose exec db psql -U wms_user -d warehouse_db

# Stop all services
docker compose down -v
```

## Features

- User management with role-based access control
- Multi-warehouse inventory tracking
- Product & customer management
- Document workflows (import/export/transfer)
- RESTful API with JWT authentication
- Web dashboard
- Real-time stock level monitoring

## Architecture

- **Framework**: FastAPI + PostgreSQL
- **Pattern**: Clean Architecture with DDD
- **Auth**: JWT + bcrypt
- **Deployment**: Docker & Docker Compose
- **Testing**: Pytest suite (unit, integration, regression)

## Project Structure

```
WMS/
├── src/                         # Main source code
│   ├── app/                     # FastAPI application
│   │   ├── api/                 # REST API endpoints
│   │   ├── modules/             # Feature modules (users, warehouses, products, etc.)
│   │   ├── shared/              # Shared utilities (auth, database, core)
│   │   └── main.py
│   ├── ai_engine/               # AI integration & LLM features
│   │   ├── agents/              # AI agents
│   │   ├── core/                # Engine core
│   │   └── generation/          # LLM generation
│   └── data/                    # Data management & seed data
│
├── tests/                       # Comprehensive test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   ├── functional/              # Functional tests
│   ├── regression/              # Regression tests
│   ├── security/                # Security tests
│   └── performance/             # Performance tests
│
├── dashboard/                   # Web dashboard (HTML/JS)
├── scripts/                     # Utility scripts (seed.py, etc.)
├── alembic/                     # Database migrations
├── lessons/                     # Learning materials & examples
├── docker-compose.yml           # Service orchestration
├── Dockerfile                   # Container build
├── pyproject.toml               # Project configuration
└── README.md
```
