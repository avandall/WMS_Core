"""Comprehensive tests for SQL parser validator."""

import pytest
from unittest.mock import Mock, patch

from app.infrastructure.ai.sql_parser import SQLParserValidator, SQLParseResult

class TestSQLParserValidator:
    """Test robust SQL parser validation."""
    
    def test_valid_select_queries(self):
        """Test that valid SELECT queries pass validation."""
        valid_queries = [
            "SELECT * FROM users",
            "SELECT id, name FROM products WHERE price > 100",
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)",
            "WITH cte AS (SELECT * FROM products) SELECT * FROM cte",
            "SELECT * FROM users ORDER BY name LIMIT 10",
            "SELECT COUNT(*) FROM orders",
            "SELECT u.*, o.total FROM users u JOIN orders o ON u.id = o.user_id",
        ]
        
        for query in valid_queries:
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            assert is_valid, f"Query should be valid: {query}"
            assert len(violations) == 0, f"No violations expected: {violations}"
    
    def test_dangerous_statements_blocked(self):
        """Test that dangerous statements are blocked."""
        dangerous_queries = [
            "INSERT INTO users VALUES (1, 'test')",
            "UPDATE users SET name = 'test' WHERE id = 1",
            "DELETE FROM users WHERE id = 1",
            "DROP TABLE users",
            "CREATE TABLE test (id INT)",
            "ALTER TABLE users ADD COLUMN email VARCHAR",
            "TRUNCATE TABLE orders",
            "GRANT SELECT ON users TO role",
            "REVOKE SELECT ON users FROM role",
            "COPY users FROM 'file.csv'",
            "DO $$ BEGIN END $$",
            "CALL test_procedure()",
            "EXECUTE 'SELECT 1'",
            "COMMIT",
            "ROLLBACK",
            "SAVEPOINT test",
            "PREPARE stmt AS SELECT 1",
        ]
        
        for query in dangerous_queries:
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            assert not is_valid, f"Query should be invalid: {query}"
            assert len(violations) > 0, f"Violations expected for: {query}"
    
    def test_dangerous_functions_blocked(self):
        """Test that dangerous PostgreSQL functions are blocked."""
        dangerous_function_queries = [
            "SELECT pg_sleep(10)",
            "SELECT BENCHMARK(1000000, ENCODE('hello', RAND()))",
            "SELECT version()",
            "SELECT current_database()",
            "SELECT current_user",
            "SELECT session_user",
            "SELECT user",
            "SELECT pg_cancel_backend(123)",
            "SELECT pg_terminate_backend(456)",
            "SELECT pg_reload_conf()",
        ]
        
        for query in dangerous_function_queries:
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            assert not is_valid, f"Query should be invalid: {query}"
            assert any("function" in v.lower() for v in violations), f"Function violation expected: {query}"
    
    def test_multiple_statements_blocked(self):
        """Test that multiple statements are blocked."""
        multi_statement_queries = [
            "SELECT * FROM users; DROP TABLE users;",
            "SELECT * FROM users; SELECT * FROM orders;",
            "WITH cte AS (SELECT * FROM users) SELECT * FROM cte; DELETE FROM cte;",
            "SELECT 1; SELECT 2; SELECT 3;",
        ]
        
        for query in multi_statement_queries:
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            assert not is_valid, f"Multi-statement query should be invalid: {query}"
            assert any("multiple" in v.lower() or "statement" in v.lower() for v in violations), f"Multiple statement violation expected: {query}"
    
    def test_comments_and_strings_handled(self):
        """Test that comments and string literals are properly handled."""
        queries_with_comments_strings = [
            "SELECT * FROM users -- This is a comment",
            "SELECT * FROM users /* This is a comment */",
            "SELECT * FROM users WHERE name = 'test; DROP TABLE'",
            "SELECT * FROM users WHERE name = \"test; semicolon\"",
            "SELECT * FROM users WHERE note = $$This contains ; semicolon$$",
            "SELECT * FROM users WHERE note = $tag$This contains ; semicolon$tag$",
            "SELECT * FROM users WHERE name = 'test' /* comment */",
        ]
        
        for query in queries_with_comments_strings:
            # These should be valid (single SELECT statements)
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            assert is_valid, f"Query with comments/strings should be valid: {query}"
    
    def test_dollar_quoted_strings(self):
        """Test PostgreSQL dollar-quoted strings are handled."""
        dollar_quote_queries = [
            "SELECT $$This is a string with ; semicolon$$",
            "SELECT $tag$This is a tagged string with ; semicolon$tag$",
            "SELECT * FROM users WHERE note = $$Contains ; semicolon$$",
            "SELECT * FROM users WHERE note = $outer$Inner $inner$nested$inner$ string$outer$",
        ]
        
        for query in dollar_quote_queries:
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            assert is_valid, f"Dollar-quoted string query should be valid: {query}"
    
    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        edge_cases = [
            ("", "Empty query"),
            ("   ", "Whitespace only"),
            (";", "Just semicolon"),
            ("-- comment only", "Comment only"),
            ("/* comment only */", "Block comment only"),
        ]
        
        for query, description in edge_cases:
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            if query.strip():  # Non-empty queries
                assert not is_valid, f"Edge case should be invalid: {description}"
    
    def test_custom_allowed_operations(self):
        """Test custom allowed operations."""
        # Allow INSERT for testing
        is_valid, violations = SQLParserValidator.validate_sql_structure(
            "INSERT INTO users VALUES (1, 'test')",
            allowed_operations={'SELECT', 'WITH', 'INSERT'}
        )
        assert is_valid, "INSERT should be allowed when specified"
        
        # Disallow INSERT
        is_valid, violations = SQLParserValidator.validate_sql_structure(
            "INSERT INTO users VALUES (1, 'test')",
            allowed_operations={'SELECT', 'WITH'}
        )
        assert not is_valid, "INSERT should be blocked when not allowed"
    
    def test_parse_sql_info(self):
        """Test detailed SQL parsing information."""
        query = "SELECT * FROM users WHERE name = 'test' -- comment"
        
        parse_result = SQLParserValidator.parse_sql_info(query)
        
        assert isinstance(parse_result, SQLParseResult)
        assert parse_result.statement_count == 1
        assert 'SELECT' in parse_result.statement_types
        assert len(parse_result.dangerous_functions) == 0
        assert parse_result.has_comments == True
        assert parse_result.has_string_literals == True
    
    def test_remove_comments_and_strings(self):
        """Test comment and string removal."""
        test_cases = [
            ("SELECT * FROM users -- comment", "SELECT * FROM users "),
            ("SELECT * /* comment */ FROM users", "SELECT *  FROM users"),
            ("SELECT * FROM users WHERE name = 'test; DROP'", "SELECT * FROM users WHERE name = "),
            ('SELECT * FROM users WHERE name = "test; DROP"', "SELECT * FROM users WHERE name = "),
            ("SELECT $$contains ; semicolon$$", "SELECT "),
            ("SELECT $tag$contains ; semicolon$tag$", "SELECT "),
        ]
        
        for input_sql, expected in test_cases:
            result = SQLParserValidator._remove_comments_and_strings(input_sql)
            # Check that the expected pattern is in result
            assert expected.replace(' ', '') in result.replace(' ','), f"String removal failed for: {input_sql}"
    
    def test_dangerous_function_detection(self):
        """Test dangerous function detection."""
        queries_with_functions = [
            ("SELECT pg_sleep(10)", ["pg_sleep"]),
            ("SELECT version(), current_user()", ["version", "current_user"]),
            ("SELECT user()", ["user"]),
            ("SELECT safe_function()", []),  # Not in dangerous list
        ]
        
        for query, expected_funcs in queries_with_functions:
            if hasattr(SQLParserValidator, '_find_dangerous_functions_regex'):
                dangerous_funcs = SQLParserValidator._find_dangerous_functions_regex(query)
                assert set(dangerous_funcs) == set(expected_funcs), f"Function detection failed for: {query}"
    
    def test_statement_type_detection(self):
        """Test statement type detection."""
        statement_type_tests = [
            ("SELECT * FROM users", "SELECT"),
            ("WITH cte AS (SELECT * FROM users) SELECT * FROM cte", "WITH"),
            ("INSERT INTO users VALUES (1)", "INSERT"),
            ("  select * from users  ", "SELECT"),  # Case insensitive
            ("", "UNKNOWN"),
        ]
        
        for query, expected_type in statement_type_tests:
            stmt_type = SQLParserValidator._get_statement_type_regex(query)
            assert stmt_type == expected_type, f"Statement type detection failed for: {query}"

class TestSQLParserFallback:
    """Test fallback behavior when sqlparse is not available."""
    
    @patch('app.infrastructure.ai.sql_parser.HAS_SQLPARSE', False)
    def test_fallback_validation(self):
        """Test fallback validation when sqlparse is unavailable."""
        # Should still work with regex-based validation
        is_valid, violations = SQLParserValidator.validate_sql_structure("SELECT * FROM users")
        assert is_valid, "Valid SELECT should pass even without sqlparse"
        
        is_valid, violations = SQLParserValidator.validate_sql_structure("DROP TABLE users")
        assert not is_valid, "Dangerous query should be blocked even without sqlparse"
    
    @patch('app.infrastructure.ai.sql_parser.HAS_SQLPARSE', False)
    def test_fallback_parse_info(self):
        """Test fallback parsing info when sqlparse is unavailable."""
        parse_result = SQLParserValidator.parse_sql_info("SELECT * FROM users")
        
        assert isinstance(parse_result, SQLParseResult)
        assert parse_result.statement_count == 1
        assert parse_result.statement_types == ["SELECT"]

class TestSQLParserSecurity:
    """Test security aspects of SQL parser."""
    
    def test_bypass_attempts(self):
        """Test various bypass attempts."""
        bypass_attempts = [
            # Comment-based bypasses
            "SELECT/**/ * FROM users",
            "SELECT-- comment\n* FROM users",
            "SELECT /*comment*/ * FROM users",
            
            # String-based bypasses
            "SELECT * FROM users WHERE 'DROP TABLE' = 'test'",
            "SELECT * FROM users WHERE \"INSERT\" = 'test'",
            
            # Case-based bypasses
            "select * from users",
            "Select * From Users",
            "SELECT * FROM USERS",
            
            # Whitespace-based bypasses
            "SELECT\t*\nFROM\tusers",
            "SELECT  *  FROM  users",
        ]
        
        for query in bypass_attempts:
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            assert is_valid, f"Legitimate bypass attempt should be valid: {query}"
    
    def test_obfuscated_dangerous_queries(self):
        """Test obfuscated dangerous queries are still blocked."""
        obfuscated_dangerous = [
            "selECT/**/ * FROM users; DROP TABLE users",
            "SELECT * FROM users -- comment\nDROP TABLE users",
            "SELECT * FROM users WHERE 1=1; INSERT INTO users VALUES (1)",
            "WITH cte AS (SELECT * FROM users) SELECT * FROM cte; DO $$ BEGIN END $$",
        ]
        
        for query in obfuscated_dangerous:
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            assert not is_valid, f"Obfuscated dangerous query should be blocked: {query}"
    
    def test_function_call_detection_accuracy(self):
        """Test accurate function call detection."""
        function_test_cases = [
            ("SELECT user FROM users", []),  # Column named 'user', not function
            ("SELECT user() FROM users", ["user"]),  # Function call
            ("SELECT current_user_setting FROM config", []),  # Column name
            ("SELECT current_user() FROM users", ["current_user"]),  # Function call
            ("SELECT version FROM users", []),  # Column name
            ("SELECT version() FROM users", ["version"]),  # Function call
        ]
        
        for query, expected_funcs in function_test_cases:
            is_valid, violations = SQLParserValidator.validate_sql_structure(query)
            if expected_funcs:
                assert not is_valid, f"Query with dangerous functions should be blocked: {query}"
                assert any("function" in v.lower() for v in violations), f"Function violation expected: {query}"
            else:
                assert is_valid, f"Query with safe column names should be valid: {query}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
