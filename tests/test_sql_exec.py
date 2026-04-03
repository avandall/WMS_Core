"""Comprehensive unit tests for enhanced SQL execution module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from typing import Dict, Any, List
import hashlib

from app.infrastructure.ai.sql_exec import execute_readonly_sql

class TestSQLExecutionSecurity:
    """Test security features of SQL execution."""
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_valid_select_query(self, mock_engine):
        """Test that valid SELECT queries are allowed."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [
            {"id": 1, "name": "Test Product", "price": Decimal("99.99")}
        ]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Test valid SELECT query
        result = execute_readonly_sql("SELECT * FROM products")
        
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["name"] == "Test Product"
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_valid_with_query(self, mock_engine):
        """Test that valid WITH queries are allowed."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [
            {"id": 1, "name": "Test"}
        ]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Test valid WITH query
        result = execute_readonly_sql("WITH cte AS (SELECT * FROM products) SELECT * FROM cte")
        
        assert len(result) == 1
    
    def test_blocks_non_select_queries(self):
        """Test that non-SELECT/WITH queries are blocked."""
        dangerous_queries = [
            "INSERT INTO products VALUES (1, 'test')",
            "UPDATE products SET name = 'test' WHERE id = 1",
            "DELETE FROM products WHERE id = 1",
            "DROP TABLE products",
            "CREATE TABLE test (id INT)",
            "ALTER TABLE products ADD COLUMN test VARCHAR",
            "TRUNCATE TABLE products",
            "GRANT SELECT ON products TO user",
            "REVOKE SELECT ON products FROM user",
            "COPY products FROM 'file.csv'",
            "DO $$ BEGIN END $$",
            "CALL test_procedure()",
            "EXECUTE 'SELECT 1'",
        ]
        
        for query in dangerous_queries:
            with pytest.raises(ValueError, match="SQL validation failed|Only SELECT/WITH queries are allowed"):
                execute_readonly_sql(query)
    
    def test_blocks_multiple_statements(self):
        """Test that multiple SQL statements are blocked."""
        multiple_statement_queries = [
            "SELECT * FROM products; DROP TABLE products;",
            "SELECT * FROM users; SELECT * FROM products;",
            "WITH cte AS (SELECT * FROM products) SELECT * FROM cte; DELETE FROM cte;",
        ]
        
        for query in multiple_statement_queries:
            with pytest.raises(ValueError, match="SQL validation failed|Multiple SQL statements are not allowed"):
                execute_readonly_sql(query)
    
    def test_blocks_dangerous_functions(self):
        """Test that dangerous PostgreSQL functions are blocked."""
        dangerous_function_queries = [
            "SELECT pg_sleep(10)",
            "SELECT BENCHMARK(1000000, ENCODE('hello', RAND()))",
            "SELECT version()",
            "SELECT current_database()",
            "SELECT current_user",
            "SELECT session_user",
            "SELECT user",
        ]
        
        for query in dangerous_function_queries:
            with pytest.raises(ValueError, match="SQL validation failed|not allowed"):
                execute_readonly_sql(query)
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_empty_query_blocked(self, mock_engine):
        """Test that empty queries are blocked."""
        with pytest.raises(ValueError, match="SQL query cannot be empty"):
            execute_readonly_sql("")
        
        with pytest.raises(ValueError, match="SQL query cannot be empty"):
            execute_readonly_sql("   \n\t   ")
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_semicolon_in_string_literal_allowed(self, mock_engine):
        """Test that semicolons in string literals are allowed."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # This should be allowed (semicolon is inside string literal)
        result = execute_readonly_sql("SELECT * FROM products WHERE name = 'test;semicolon'")
        
        assert len(result) == 1
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_comments_stripped_before_validation(self, mock_engine):
        """Test that comments are stripped before validation."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # This should be allowed (comment should be stripped)
        result = execute_readonly_sql("SELECT * FROM products -- This is a comment")
        
        assert len(result) == 1
    
    def test_parser_validator_fallback(self):
        """Test parser validator fallback behavior."""
        # This test verifies that the function works even when advanced validators are unavailable
        # The parser validator should still block dangerous queries
        
        dangerous_queries = [
            "DROP TABLE products",
            "INSERT INTO test VALUES (1)",
            "SELECT pg_sleep(10)",
        ]
        
        for query in dangerous_queries:
            with pytest.raises(ValueError, match="SQL validation failed|not allowed"):
                execute_readonly_sql(query)
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_dollar_quoted_strings(self, mock_engine):
        """Test PostgreSQL dollar-quoted strings are handled."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Dollar-quoted strings should be allowed
        result = execute_readonly_sql("SELECT $$This contains ; semicolon$$")
        assert len(result) == 1
        
        result = execute_readonly_sql("SELECT $tag$This contains ; semicolon$tag$")
        assert len(result) == 1

class TestSQLExecutionFunctionality:
    """Test functional aspects of SQL execution."""
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_custom_max_rows(self, mock_engine):
        """Test custom max_rows parameter."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Test with custom max_rows
        execute_readonly_sql("SELECT * FROM products", max_rows=50)
        
        # Should use custom limit
        mock_result.mappings.return_value.fetchmany.assert_called_with(50)
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    @patch('app.infrastructure.ai.sql_exec.ai_engine_settings')
    def test_default_max_rows(self, mock_settings, mock_engine):
        """Test default max_rows from settings."""
        mock_settings.db_max_rows = 200
        
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Test without custom max_rows
        execute_readonly_sql("SELECT * FROM products")
        
        # Should use default limit from settings
        mock_result.mappings.return_value.fetchmany.assert_called_with(200)
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_with_parameters(self, mock_engine):
        """Test SQL execution with parameters."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1, "name": "Test"}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        params = {"id": 1, "name": "test"}
        result = execute_readonly_sql("SELECT * FROM products WHERE id = :id AND name = :name", params)
        
        # Should pass parameters to execute
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == params  # Second argument should be params
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_decimal_precision_preservation(self, mock_engine):
        """Test that Decimal precision is preserved."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [
            {"id": 1, "price": Decimal("99.9999999999")},
            {"id": 2, "price": Decimal("123.45")}
        ]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        result = execute_readonly_sql("SELECT * FROM products")
        
        # Decimal should be converted to string to preserve precision
        assert result[0]["price"] == "99.9999999999"
        assert result[1]["price"] == "123.45"
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_database_execution_error(self, mock_engine):
        """Test handling of database execution errors."""
        # Mock database execution
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Database connection failed")
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        with pytest.raises(Exception, match="Database connection failed"):
            execute_readonly_sql("SELECT * FROM products")
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_postgresql_specific_options(self, mock_engine):
        """Test PostgreSQL-specific execution options."""
        # Mock database execution with PostgreSQL dialect
        mock_engine.dialect.name = 'postgresql'
        mock_engine.dialect = Mock()
        mock_engine.dialect.name = 'postgresql'
        
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        result = execute_readonly_sql("SELECT * FROM products")
        
        # Should set postgresql_readonly option
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        executed_text = call_args[0][0]
        assert 'postgresql_readonly' in executed_text.execution_options
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_non_postgresql_engine(self, mock_engine):
        """Test non-PostgreSQL engine execution."""
        # Mock database execution without PostgreSQL dialect
        mock_engine.dialect = Mock()
        mock_engine.dialect.name = 'mysql'
        
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        result = execute_readonly_sql("SELECT * FROM products")
        
        # Should not set postgresql_readonly option
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        executed_text = call_args[0][0]
        # execution_options should be empty for non-PostgreSQL
        assert executed_text.execution_options == {}

class TestSQLExecutionEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_case_insensitive_select(self, mock_engine):
        """Test case-insensitive SELECT detection."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Test various cases
        for query in ["select * from products", "SELECT * FROM products", "Select * From Products"]:
            result = execute_readonly_sql(query)
            assert len(result) == 1
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_case_insensitive_with(self, mock_engine):
        """Test case-insensitive WITH detection."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Test various cases
        for query in ["with cte as (select * from products) select * from cte", "WITH cte AS (SELECT * FROM products) SELECT * FROM cte"]:
            result = execute_readonly_sql(query)
            assert len(result) == 1

class TestSQLExecutionLogging:
    """Test logging functionality."""
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    @patch('app.infrastructure.ai.sql_exec.logger')
    def test_successful_execution_logging(self, mock_logger, mock_engine):
        """Test logging for successful execution."""
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        execute_readonly_sql("SELECT * FROM products")
        
        # Check that info logs were called
        mock_logger.info.assert_called()
        
        # Check specific log calls
        info_calls = [call for call in mock_logger.info.call_args_list]
        
        # Should log start of execution
        start_log_found = any("Starting SQL execution" in str(call) for call in info_calls)
        assert start_log_found
        
        # Should log successful completion
        success_log_found = any("SQL execution completed successfully" in str(call) for call in info_calls)
        assert success_log_found
        
        # Should log execution time
        time_log_found = any("execution_time_ms" in str(call) for call in info_calls)
        assert time_log_found
    
    @patch('app.infrastructure.ai.sql_exec.logger')
    def test_blocked_query_logging(self, mock_logger):
        """Test logging for blocked queries."""
        # Test blocking for non-SELECT query
        with pytest.raises(ValueError):
            execute_readonly_sql("INSERT INTO products VALUES (1, 'test')")
        
        # Check that warning log was called
        mock_logger.warning.assert_called()
        
        # Check specific warning content
        warning_calls = [call for call in mock_logger.warning.call_args_list]
        blocked_log_found = any("invalid statement type" in str(call) for call in warning_calls)
        assert blocked_log_found
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    @patch('app.infrastructure.ai.sql_exec.logger')
    def test_database_error_logging(self, mock_logger, mock_engine):
        """Test logging for database errors."""
        # Mock database execution
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Database error")
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        with pytest.raises(Exception):
            execute_readonly_sql("SELECT * FROM products")
        
        # Check that error log was called
        mock_logger.error.assert_called()
        
        # Check specific error content
        error_calls = [call for call in mock_logger.error.call_args_list]
        error_log_found = any("SQL execution failed" in str(call) for call in error_calls)
        assert error_log_found
    
    @patch('app.infrastructure.ai.sql_exec.logger')
    def test_safe_logging_no_sensitive_data(self, mock_logger):
        """Test that logging doesn't expose sensitive SQL data."""
        with pytest.raises(ValueError):
            execute_readonly_sql("SELECT * FROM users WHERE email = 'sensitive@example.com'")
        
        # Check that no raw SQL is logged
        warning_calls = [call for call in mock_logger.warning.call_args_list]
        for call in warning_calls:
            log_data = call[1] if call else {}
            # Should not contain raw SQL or sensitive data
            assert "sensitive@example.com" not in str(log_data)
            # Should contain fingerprint instead
            assert "query_fingerprint" in str(log_data)

class TestSQLExecutionSecurityHelpers:
    """Test security helper functions."""
    
    def test_remove_comments_and_strings(self):
        """Test comment and string removal function."""
        from app.infrastructure.ai.sql_exec import _remove_comments_and_strings
        
        test_cases = [
            ("SELECT * FROM users -- comment", "SELECT * FROM users "),
            ("SELECT * /* comment */ FROM users", "SELECT *  FROM users"),
            ("SELECT * FROM users WHERE name = 'test; DROP'", "SELECT * FROM users WHERE name = "),
            ('SELECT * FROM users WHERE name = "test; DROP"', "SELECT * FROM users WHERE name = "),
            ("SELECT * FROM users WHERE name = 'test' -- comment", "SELECT * FROM users WHERE name = 'test' "),
        ]
        
        for input_sql, expected in test_cases:
            result = _remove_comments_and_strings(input_sql)
            assert result == expected
    
    def test_detect_semicolons_outside_strings(self):
        """Test semicolon detection function."""
        from app.infrastructure.ai.sql_exec import _detect_semicolons_outside_strings
        
        # Should detect semicolon outside strings
        assert _detect_semicolons_outside_strings("SELECT * FROM users; DROP TABLE") is True
        
        # Should not detect semicolon inside strings
        assert _detect_semicolons_outside_strings("SELECT * FROM users WHERE name = 'test;semicolon'") is False
    
    def test_create_query_fingerprint(self):
        """Test query fingerprinting function."""
        from app.infrastructure.ai.sql_exec import _create_query_fingerprint
        
        # Should create consistent fingerprint
        query1 = "SELECT * FROM users WHERE id = 1"
        query2 = "SELECT * FROM users WHERE id = 1"
        
        fp1 = _create_query_fingerprint(query1)
        fp2 = _create_query_fingerprint(query2)
        
        assert fp1 == fp2
        assert len(fp1) == 16  # Should be truncated to 16 chars
        assert fp1 != query1  # Should not be the original query
    
    def test_sanitize_for_logging(self):
        """Test logging sanitization function."""
        from app.infrastructure.ai.sql_exec import _sanitize_for_logging
        
        query = "SELECT * FROM users WHERE email = 'sensitive@example.com'"
        log_data = _sanitize_for_logging(query)
        
        # Should include fingerprint but not raw query
        assert "query_fingerprint" in log_data
        assert "sensitive@example.com" not in str(log_data)
        assert log_data["query_length"] == len(query)
        assert log_data["starts_with"] == "select * from users"

class TestSQLExecutionPerformance:
    """Test performance aspects."""
    
    @patch('app.infrastructure.ai.sql_exec.engine')
    def test_large_result_set_handling(self, mock_engine):
        """Test handling of large result sets."""
        # Create large result set
        large_result = [{"id": i, "name": f"Product {i}"} for i in range(1000)]
        
        # Mock database execution
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.mappings.return_value.fetchmany.return_value = large_result
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        result = execute_readonly_sql("SELECT * FROM products", max_rows=1000)
        
        assert len(result) == 1000
        assert result[999]["id"] == 999

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
