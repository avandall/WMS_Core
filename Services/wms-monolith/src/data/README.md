# Data Layer

This directory contains data management components for the WMS application.

## Structure

```
data/
├── seed_data/          # Test data for development and testing
│   ├── users.json
│   ├── warehouses.json
│   ├── products.json
│   ├── customers.json
│   └── inventory.json
└── logs/               # Application logs with automatic cleanup
    ├── log_manager.py
    ├── app.log
    ├── error.log
    └── audit.log
```

## Seed Data

The `seed_data/` folder contains JSON files with sample data for:

- **Users**: Test user accounts with different roles
- **Warehouses**: Sample warehouse locations
- **Products**: Product catalog with pricing
- **Customers**: Sample customer information
- **Inventory**: Initial inventory quantities

### Usage

```python
from data.logs import load_json_file
from pathlib import Path

# Load seed data
seed_dir = Path('src/data/seed_data')
users = load_json_file(seed_dir / 'users.json')
products = load_json_file(seed_dir / 'products.json')
```

Or use the script:

```bash
python scripts/load_seed_data.py
```

## Logs

The `logs/` folder handles system logging with automatic cleanup.

### Features

- **Automatic Cleanup**: Removes logs older than 7 days
- **Log Rotation**: Prevents large log files
- **Multiple Log Types**: App, error, and audit logs
- **Size Management**: Tracks total log size

### Usage

```python
from data.logs import setup_logging_with_cleanup

# Setup logging with automatic cleanup
setup_logging_with_cleanup()
```

Or run cleanup manually:

```bash
python scripts/cleanup_logs.py
```

### Log Files

- `app.log` - General application logs
- `error.log` - Error-specific logs
- `audit.log` - Audit trail for sensitive operations

### Automatic Cleanup

- Logs older than 7 days are automatically removed
- Cleanup runs on application startup
- Can be scheduled via cron for regular maintenance

## Security Notes

- Seed data contains only test information
- Log files may contain sensitive data
- Restrict access to log files in production
- Regular backup recommended for compliance

## Scripts

- `scripts/cleanup_logs.py` - Manual log cleanup
- `scripts/load_seed_data.py` - Seed data information loader
