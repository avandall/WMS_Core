"""
Security Tests for AI SQL Injection Prevention
Tests that the AI chat endpoint properly blocks SQL injection attempts
"""

import pytest
from app.infrastructure.ai.chains import is_relevant_query, generate_sql_from_question, _validate_table_access


class TestAISQLInjectionPrevention:
    """Test SQL injection prevention in AI chains"""

    def test_relevance_filter_blocks_generic_database_queries(self):
        """Test that generic database terms are blocked"""
        
        # These should be blocked now (generic terms removed + forbidden patterns)
        blocked_queries = [
            "show me data from the users table",
            "query the database for user passwords", 
            "list all records in auth table",
            "select from system tables",
            "admin user credentials access",
            "show me user passwords",
            "get system admin data",
            "access user authentication table"
        ]
        
        for query in blocked_queries:
            result = is_relevant_query(query)
            assert not result, f"Query should be blocked: {query}"

    def test_relevance_filter_allows_wms_queries(self):
        """Test that legitimate WMS queries are still allowed"""
        
        allowed_queries = [
            "show me products in inventory",
            "warehouse stock levels", 
            "customer orders status",
            "product information",
            "inventory quantities",
            "warehouse locations",
            "supplier information"
        ]
        
        for query in allowed_queries:
            result = is_relevant_query(query)
            assert result, f"WMS query should be allowed: {query}"

    def test_table_access_validation_blocks_forbidden_tables(self):
        """Test that forbidden tables are blocked"""
        
        forbidden_sql_queries = [
            "SELECT * FROM users",
            "SELECT hashed_password FROM users",
            "SELECT * FROM auth",
            "SELECT * FROM system_tables",
            "SELECT * FROM information_schema",
            "SELECT * FROM pg_user",
            "JOIN users ON products.user_id = users.id"
        ]
        
        for sql in forbidden_sql_queries:
            with pytest.raises(ValueError, match="Access to forbidden tables"):
                _validate_table_access(sql)

    def test_table_access_validation_allows_wms_tables(self):
        """Test that WMS tables are allowed"""
        
        allowed_sql_queries = [
            "SELECT * FROM products",
            "SELECT * FROM inventory",
            "SELECT * FROM warehouses",
            "SELECT * FROM customers",
            "JOIN products ON inventory.product_id = products.id"
        ]
        
        for sql in allowed_sql_queries:
            try:
                result = _validate_table_access(sql)
                assert result == sql
            except ValueError:
                pytest.fail(f"WMS table access should be allowed: {sql}")

    def test_sql_generation_blocks_forbidden_tables(self):
        """Test that SQL generation blocks access to forbidden tables"""
        
        malicious_questions = [
            "show me all user passwords from the users table",
            "list all users and their hashed passwords", 
            "query the auth table for user data",
            "get system information from database tables"
        ]
        
        for question in malicious_questions:
            # These should be blocked by relevance filter first
            result = is_relevant_query(question)
            assert not result, f"Malicious query should be blocked by relevance filter: {question}"

    def test_sql_generation_allows_wms_queries(self):
        """Test that legitimate WMS queries pass relevance filter"""
        
        legitimate_questions = [
            "show me all products",
            "what is the inventory level",
            "list all warehouses", 
            "show customer orders"
        ]
        
        for question in legitimate_questions:
            # These should pass relevance filter
            result = is_relevant_query(question)
            assert result, f"WMS query should pass relevance filter: {question}"

    def test_case_insensitive_table_detection(self):
        """Test that table detection works case-insensitively"""
        
        # These should be blocked regardless of case
        blocked_variants = [
            "SELECT * FROM Users",
            "SELECT * FROM USERS", 
            "SELECT * FROM users",
            "select * from USERS",
            "Join users On products.id = users.id"
        ]
        
        for sql in blocked_variants:
            with pytest.raises(ValueError, match="Access to forbidden tables"):
                _validate_table_access(sql)

    def test_complex_sql_injection_attempts(self):
        """Test complex SQL injection attempts"""
        
        injection_attempts = [
            "SELECT * FROM products; SELECT * FROM users",
            "SELECT * FROM products UNION SELECT * FROM users",
            "SELECT * FROM information_schema.columns WHERE table_name = 'users'",
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'users'",
            "SELECT * FROM pg_catalog.pg_user"
        ]
        
        for sql in injection_attempts:
            with pytest.raises(ValueError):
                _validate_table_access(sql)
