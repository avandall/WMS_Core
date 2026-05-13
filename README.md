# Warehouse Management System (WMS)

A comprehensive, modern Warehouse Management System built with Python FastAPI, Clean Architecture, and advanced AI capabilities. Features real-time inventory tracking, role-based access control, and intelligent AI-powered warehouse operations.

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

### Core WMS Features
- **User Management** - Role-based permissions (admin, warehouse, sales, accountant)
- **Warehouse Management** - Multiple locations with inventory tracking
- **Product Management** - Catalog with pricing and descriptions
- **Customer Management** - Company accounts with contact info
- **Inventory Tracking** - Real-time stock levels across warehouses
- **Document Management** - Import/export/transfer documents
- **API Access** - RESTful API with authentication
- **Dashboard** - Web interface for warehouse operations

### 🤖 AI Engine Features
- **Hybrid RAG Search** - Combines semantic search with keyword search using embeddings
- **Intelligent Agents** - Database-integrated AI agents for real-time queries
- **Quality Evaluation** - Automated response quality assessment with fallback mechanisms
- **Multi-Mode Processing** - RAG, Agent, and Hybrid processing modes
- **WMS-Specific Intelligence** - Understanding of warehouse operations and business logic
- **Vector Database** - ChromaDB integration for efficient semantic search

## 🔐 Security

- JWT-based authentication
- Role-based access control
- Password hashing with bcrypt
- Environment-based configuration

## 📈 Architecture & Technology Stack

### Core Architecture
- **Clean Architecture** - Separation of concerns with layered design
- **Domain-Driven Design (DDD)** - Business logic isolation with bounded contexts
- **Repository Pattern** - Data access abstraction and testability
- **Dependency Injection** - Loose coupling and testable components


### Technology Stack
- **Backend**: FastAPI (modern async web framework)
- **Database**: PostgreSQL 16 with SQLAlchemy 2.0+ ORM
- **Authentication**: JWT tokens with bcrypt password hashing
- **AI Engine**: LangChain, Groq LLMs, ChromaDB vector storage
- **Containerization**: Docker & Docker Compose
- **Testing**: pytest with comprehensive test coverage
- **Code Quality**: Black formatting, MyPy type checking

### Project Structure
```text
src/
├── app/                          # Main application
│   ├── api/                      # FastAPI endpoints & middleware
│   ├── modules/                  # Business modules (DDD)
│   │   ├── users/               # User management & auth
│   │   ├── warehouses/          # Warehouse operations
│   │   ├── products/            # Product catalog
│   │   ├── inventory/           # Real-time inventory
│   │   ├── documents/           # Document management
│   │   ├── customers/           # Customer management
│   │   └── audit/               # Audit logging
│   └── shared/                  # Shared components
│       ├── core/               # Core functionality
│       ├── domain/             # Domain entities
│       └── utils/              # Utilities
└── ai_engine/                   # Advanced AI capabilities
    ├── retrieval/              # Hybrid RAG search
    ├── generation/             # LLM response generation
    ├── agents/                 # WMS-specific AI agents
    └── workflows/              # AI workflow orchestration
```

## 📚 Documentation

- **[PROJECT_DOCUMENTATION.md](./PROJECT_DOCUMENTATION.md)** - Comprehensive technical documentation
- **[API Documentation](http://localhost:8000/docs)** - Interactive Swagger API docs
- **[AI Engine Documentation](./src/ai_engine/README.md)** - AI capabilities and usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## 📝 License

[Add your license information here]
