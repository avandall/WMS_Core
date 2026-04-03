# Warehouse Management System (WMS)

A comprehensive Warehouse Management System built with Python, FastAPI, and Clean Architecture.

## 🚀 Quick Start

### Development Environment (Recommended)
```bash
# Start with rich sample data
./start.sh dev

# Access dashboard
# http://localhost:8080
# Login: admin@wms.vn / admin123
```

### Production Environment
```bash
# Start with minimal data
./start.sh prod
```

### Manual Data Loading
If auto-seed doesn't work:
```bash
./fix_seed_data.sh
```

## 🌐 Access URLs

| Service | URL | Description |
|----------|------|-------------|
| **Dashboard** | http://localhost:8080 | Web interface |
| **API** | http://localhost:8000 | REST API |
| **API Docs** | http://localhost:8000/docs | Swagger documentation |
| **Database** | localhost:5433 | PostgreSQL |
| **Adminer** | http://localhost:8090 | Database management |

## 🔑 Login Credentials

| Email | Password | Role | Access |
|-------|----------|-------|--------|
| **admin@wms.vn** | **admin123** | Administrator | Full access |
| warehouse@wms.vn | warehouse123 | Warehouse | Operations |
| sales@wms.vn | sales123 | Sales | Import documents |
| accountant@wms.vn | account123 | Accountant | Prices + Reports |

## 📊 Sample Data

### Development Mode
- **5 warehouses** - Vietnamese locations
- **22 products** - Office supplies, electronics
- **4 users** - Different roles with permissions
- **22 inventory records** - Stock levels
- **5 customers** - Vietnamese companies

### Production Mode
- **5 warehouses** - Essential locations
- **22 products** - Core inventory
- **4 users** - Basic roles
- **22 inventory records** - Initial stock
- **5 customers** - Key accounts

## 🛠️ Useful Commands

```bash
# View logs
docker compose logs -f api

# Restart services
docker compose restart api

# Stop everything
docker compose --profile dev down -v

# Database access
docker compose exec db psql -U wms_user -d warehouse_db

# Show login credentials
python3 show_login_credentials.py
```

## 🏗️ Project Structure

```
WMS/
├── 📄 Configuration
│   ├── .env.dev/.prod/.docker    # Environment files
│   ├── docker-compose.yml         # Service orchestration
│   └── Dockerfile               # Container build
├── 🚀 Quick Start
│   ├── quick_start.sh            # Environment launcher
│   ├── fix_seed_data.sh          # Data fix script
│   └── show_login_credentials.py # Login info
├── 📦 Source Code
│   └── src/                    # Application source
│       └── app/
│           ├── api/               # API endpoints
│           ├── core/              # Core functionality
│           ├── data/              # Data management
│           │   └── seed_data/    # Seed data scripts
│           ├── domain/            # Domain entities
│           ├── infrastructure/    # Infrastructure
│           └── main.py           # Application entry
├── 🎯 Dashboard
│   └── dashboard/              # Static web files
├── 🧪 Testing
│   └── tests/                  # Comprehensive test suite
└── 📚 Documentation
    ├── README.md                # This file
    └── PROJECT_STRUCTURE.md     # Detailed structure
```

## 🔧 Development

### Dependencies
```bash
# Install with uv (recommended)
uv sync

# Or with pip
pip install -r requirements.txt
```

### Running Tests
```bash
pytest
```

### Environment Variables
See `.env.example` for available configuration options.

## 🐳 Docker

### Build & Run
```bash
# Development
docker compose up -d

# With profile
docker compose --profile dev up -d

# Stop
docker compose down -v
```

## 🎯 Features

- **User Management** - Role-based permissions (admin, warehouse, sales, accountant)
- **Warehouse Management** - Multiple locations with inventory tracking
- **Product Management** - Catalog with pricing and descriptions
- **Customer Management** - Company accounts with contact info
- **Inventory Tracking** - Real-time stock levels across warehouses
- **Document Management** - Import/export/transfer documents
- **API Access** - RESTful API with authentication
- **Dashboard** - Web interface for warehouse operations

## 🔐 Security

- JWT-based authentication
- Role-based access control
- Password hashing with bcrypt
- Environment-based configuration

## 📈 Architecture

- **Clean Architecture** - Separation of concerns
- **Domain-Driven Design** - Business logic isolation
- **Repository Pattern** - Data access abstraction
- **Dependency Injection** - Testable components
- **FastAPI** - Modern async web framework
- **PostgreSQL** - Robust relational database
- **Docker** - Containerized deployment

## 📝 License

[Add your license information here]
