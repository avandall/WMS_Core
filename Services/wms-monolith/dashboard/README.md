# WMS Dashboard

A modern web dashboard for the Warehouse Management System (WMS) API.

## Features

- **Real-time Overview**: Live statistics and recent activity
- **Product Management**: Create, view, and manage products
- **Warehouse Management**: Manage warehouse locations and inventory
- **Inventory Tracking**: Monitor stock levels across all warehouses
- **Document Processing**: Create and manage import/export/transfer documents
- **Reports**: Generate comprehensive reports on products, inventory, documents, and warehouses

## Getting Started

### Prerequisites

- Python 3.12+
- FastAPI server running on `http://127.0.0.1:8000`

### Running the Dashboard

1. **Start the WMS API Server**:
   ```bash
   cd WMS-Project-main/WMS
   source venv/bin/activate
   python -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload
   ```

2. **Serve the Dashboard**:
   ```bash
   cd WMS-Project-main/dashboard
   python3 -m http.server 8080
   ```

3. **Open in Browser**:
   Navigate to `http://127.0.0.1:8080`

## Dashboard Sections

### Overview
- Real-time statistics (total products, warehouses, inventory items, today's documents)
- Recent activity feed
- Connection status indicator

### Products
- View all products in a table format
- Create new products with name, price, and description
- Edit and delete existing products (coming soon)

### Warehouses
- View all warehouse locations
- Create new warehouses
- View warehouse-specific inventory (coming soon)

### Inventory
- Overview of inventory across all warehouses
- Total items and value per warehouse
- Real-time stock levels

### Documents
- View all transaction documents (import, export, transfer)
- Create new documents with multiple items
- Post draft documents to finalize transactions

### Reports
- Generate inventory reports
- Product catalog reports
- Transaction history reports
- Warehouse utilization reports

## API Integration

The dashboard communicates with the WMS API using REST endpoints:

- `GET /api/products` - Retrieve all products
- `POST /api/products` - Create new product
- `GET /api/warehouses` - Retrieve all warehouses
- `POST /api/warehouses` - Create new warehouse
- `GET /api/inventory` - Retrieve inventory data
- `GET /api/documents` - Retrieve all documents
- `POST /api/documents` - Create new document
- `POST /api/documents/{id}/post` - Post a draft document
- `GET /api/reports/*` - Generate various reports

## Technologies Used

- **Frontend**: Vanilla HTML, CSS, JavaScript
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL with SQLAlchemy
- **Architecture**: Clean Architecture with domain-driven design

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Troubleshooting

### Connection Issues
- Ensure the API server is running on port 8000
- Check the connection status indicator in the dashboard header
- Verify CORS settings allow requests from `http://127.0.0.1:8080`

### API Errors
- Check browser console for detailed error messages
- Verify all required fields are filled in forms
- Ensure document items have valid product IDs and quantities

### Performance
- Dashboard loads data on page load and section changes
- Large datasets may take time to load
- Consider pagination for very large inventories

## Development

### File Structure
```
dashboard/
├── index.html      # Main dashboard interface
├── styles.css      # Responsive styling and animations
└── script.js       # API integration and interactivity
```

### Adding New Features
1. Update HTML structure in `index.html`
2. Add corresponding CSS in `styles.css`
3. Implement JavaScript logic in `script.js`
4. Test API integration thoroughly

## License

This dashboard is part of the WMS project. See project license for details.