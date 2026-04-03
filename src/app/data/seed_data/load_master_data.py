#!/usr/bin/env python3
"""
Load master seed data into the database.
This script should be run after the application has created the tables.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

try:
    from app.core.settings import settings
except ImportError:
    print("Error: Could not import WMS settings.")
    sys.exit(1)

def load_master_data():
    """Load master seed data from SQL file."""
    try:
        # Connect to database
        engine = create_engine(settings.database_url)
        
        # Read and execute SQL script
        sql_file_path = os.path.join(os.path.dirname(__file__), 'init_master_data.sql')
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Split SQL script by semicolon and execute each statement
        statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]
        
        with engine.connect() as conn:
            for statement in statements:
                if statement:
                    conn.execute(text(statement))
            conn.commit()
        
        print("✅ Master seed data loaded successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error loading master data: {e}")
        return False

if __name__ == '__main__':
    load_master_data()
