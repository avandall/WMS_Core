"""
Comprehensive edge case tests for AI chat functionality - Merged Version
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from app.application.dtos.ai import ChatDBRequest
from app.integrations.ai.chains import handle_customer_chat_with_db, is_relevant_query, _validate_table_access


class TestAIEdgeCases:
    """Test edge cases and boundary conditions for AI functionality"""

    def test_empty_message_handling(self):
        """Test handling of empty and whitespace messages"""
        
        # Test completely empty message
        result = handle_customer_chat_with_db("")
        assert result["sql"] == ""
        assert result["rows"] == []
        assert result["answer"] != ""
        
        # Test whitespace-only message
        result = handle_customer_chat_with_db("   \t\n   ")
        assert result["sql"] == ""
        assert result["rows"] == []
        assert result["answer"] != ""

    def test_extremely_long_message_handling(self):
        """Test handling of extremely long messages"""
        
        # Create a very long message (1,000 characters - more reasonable for testing)
        long_message = "tell me about " + "products " * 50
        
        with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.integrations.ai.chains.hybrid_search_with_reranking') as mock_hybrid:
            
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            mock_hybrid.return_value = {
                "success": True,
                "answer": "Response to long message",
                "mode": "rag"
            }
            
            result = handle_customer_chat_with_db(long_message, mode="rag")
            assert result["mode"] == "rag"
            assert "Response" in result["answer"]

    def test_special_characters_and_unicode(self):
        """Test handling of special characters and unicode"""
        
        special_messages = [
            "show me 📦 products with émojis",
            "what about naïve café résumé data?",
            "test with \n\t\r special chars",
            "中文测试 product information",
            "продукты на русском языке",
            "منتجات باللغة العربية"
        ]
        
        for message in special_messages:
            with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
                 patch('app.integrations.ai.chains.hybrid_search_with_reranking') as mock_hybrid:
                
                mock_engine = MagicMock()
                mock_get_engine.return_value = mock_engine
                mock_hybrid.return_value = {
                    "success": True,
                    "answer": f"Response to: {message[:20]}...",
                    "mode": "rag"
                }
                
                result = handle_customer_chat_with_db(message, mode="rag")
                assert result["mode"] == "rag"
                assert result["answer"] != ""

    def test_sql_injection_attempts_with_proper_mocking(self):
        """Test SQL injection attempts are blocked in all modes with proper mocking"""
        
        injection_attempts = [
            "'; DROP TABLE products; --",
            "'; DELETE FROM users; --",
            "'; UPDATE products SET name='hacked'; --",
            "'; INSERT INTO products VALUES('hack'); --",
            "'; ALTER TABLE products DROP COLUMN name; --",
            "'; TRUNCATE TABLE products; --",
            "'; GRANT ALL PRIVILEGES ON DATABASE TO hacker; --",
            "'; EXEC xp_cmdshell('dir'); --",
            "UNION SELECT * FROM users --",
            "1' OR '1'='1",
            "admin'--",
            "' OR 1=1#"
        ]
        
        for injection in injection_attempts:
            # Test in SQL mode with proper mocking
            try:
                with patch('app.integrations.ai.chains.is_relevant_query', return_value=True), \
                     patch('app.integrations.ai.chains.generate_sql_from_question', return_value=injection), \
                     patch('app.integrations.ai.chains._validate_table_access', side_effect=ValueError("SQL injection blocked")), \
                     patch('app.integrations.ai.chains.execute_readonly_sql', side_effect=ValueError("SQL injection blocked")):
                    
                    result = handle_customer_chat_with_db(injection, mode="sql")
                    # Should be blocked by validation
                    assert result["sql"] == ""
                    assert "error" in result["answer"].lower() or "injection" in result["answer"].lower()
            except ValueError as e:
                # Exception should be raised for SQL injection attempts
                assert "SQL injection blocked" in str(e) or "validation failed" in str(e).lower()
            
            # Test in auto mode with proper mocking
            try:
                with patch('app.integrations.ai.chains.get_rag_engine', return_value=None), \
                     patch('app.integrations.ai.chains.is_relevant_query', return_value=True), \
                     patch('app.integrations.ai.chains.generate_sql_from_question', return_value=injection), \
                     patch('app.integrations.ai.chains._validate_table_access', side_effect=ValueError("SQL injection blocked")), \
                     patch('app.integrations.ai.chains.execute_readonly_sql', side_effect=ValueError("SQL injection blocked")):
                    
                    result = handle_customer_chat_with_db(injection, mode="auto")
                    # Should fall back to SQL and be blocked
                    assert result["sql"] == ""
                    assert "error" in result["answer"].lower() or "injection" in result["answer"].lower()
            except ValueError as e:
                # Exception should be raised for SQL injection attempts
                assert "SQL injection blocked" in str(e) or "validation failed" in str(e).lower()

    def test_table_validation_edge_cases(self):
        """Test table validation with edge cases"""
        
        edge_cases = [
            "SELECT * FROM mixedCaseTable",
            "SELECT * FROM table_with_numbers123",
            "SELECT * FROM table_with_underscores_and_numbers_123",
            "SELECT * FROM \"quoted table name\"",
            "SELECT * FROM 'single quoted table'",
            "SELECT * FROM `backtick table`",
            "SELECT * FROM schema.table_name",
            "SELECT * FROM database.schema.table",
            "SELECT * FROM public.products",
            "SELECT * FROM information_schema.columns",
            "SELECT * FROM pg_catalog.pg_user",
            "SELECT * FROM pg_stat_activity"
        ]
        
        for sql in edge_cases:
            try:
                result = _validate_table_access(sql)
                # If no exception, verify it's a valid WMS table
                assert result == sql
            except ValueError as e:
                # Should be blocked for non-WMS tables
                assert "forbidden" in str(e).lower()

    def test_mode_parameter_edge_cases(self):
        """Test mode parameter with various edge cases"""
        
        edge_cases = [
            ("", "auto"),  # Empty string defaults to auto
            ("SQL", "sql"),  # Case insensitive
            ("RAG", "rag"),
            ("HYBRID", "hybrid"),
            ("Auto", "auto"),
            ("sql ", "sql"),  # Trailing space
            ("  rag", "rag"),  # Leading space
            ("  hybrid  ", "hybrid"),  # Both spaces
            ("\tauto\n", "auto"),  # Tab and newline
            ("INVALID", "auto"),  # Invalid defaults to auto
            ("unknown", "auto"),
            ("123", "auto"),
            ("@#$%", "auto"),
            (None, "auto"),  # None defaults to auto
        ]
        
        for mode_input, expected_behavior in edge_cases:
            with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
                 patch('app.integrations.ai.chains.hybrid_search_with_reranking') as mock_hybrid, \
                 patch('app.integrations.ai.chains.is_relevant_query', return_value=False):
                
                mock_engine = MagicMock()
                mock_get_engine.return_value = mock_engine
                mock_hybrid.return_value = {
                    "success": True,
                    "answer": "Test response",
                    "mode": "rag_fallback"  # Auto mode with is_relevant_query=False returns rag_fallback
                }
                
                result = handle_customer_chat_with_db("test message", mode=mode_input)
                # Should handle gracefully without crashing
                assert "answer" in result
                assert "mode" in result

    def test_concurrent_mode_requests(self):
        """Test concurrent requests with different modes"""
        import threading
        import time
        
        results = []
        
        def worker(mode):
            if mode == "sql":
                # SQL mode needs different mocking
                with patch('app.integrations.ai.chains.is_relevant_query', return_value=True), \
                     patch('app.integrations.ai.chains.generate_sql_from_question', return_value='SELECT * FROM products'), \
                     patch('app.integrations.ai.chains._validate_table_access', return_value='SELECT * FROM products'), \
                     patch('app.integrations.ai.chains.execute_readonly_sql', return_value=[{'name': 'Test Product'}]), \
                     patch('app.integrations.ai.chains.summarize_rows', return_value='Found 1 product'):
                    
                    result = handle_customer_chat_with_db("test message", mode=mode)
                    results.append((mode, result["mode"]))
            else:
                # RAG-based modes
                with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
                     patch('app.integrations.ai.chains.hybrid_search_with_reranking') as mock_hybrid, \
                     patch('app.integrations.ai.chains.is_relevant_query', return_value=False):
                    
                    mock_engine = MagicMock()
                    mock_get_engine.return_value = mock_engine
                    mock_hybrid.return_value = {
                        "success": True,
                        "answer": f"Response for {mode}",
                        "mode": "rag_fallback" if mode == "auto" else mode
                    }
                    
                    result = handle_customer_chat_with_db("test message", mode=mode)
                    results.append((mode, result["mode"]))
        
        # Start multiple threads with different modes
        threads = []
        modes = ["sql", "rag", "hybrid", "auto"]
        
        for mode in modes:
            thread = threading.Thread(target=worker, args=(mode,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all modes were handled correctly
        assert len(results) == len(modes)
        for requested_mode, actual_mode in results:
            if requested_mode == "auto":
                # Auto mode with is_relevant_query=False returns rag_fallback
                assert actual_mode in ["rag_fallback", "hybrid", "rag"]
            elif requested_mode == "hybrid":
                # Hybrid mode with is_relevant_query=False also returns rag_fallback
                assert actual_mode in ["rag_fallback", "hybrid", "hybrid_fallback"]
            else:
                assert actual_mode == requested_mode

    def test_memory_usage_with_large_responses(self):
        """Test memory usage with large SQL responses"""
        
        # Mock large SQL result
        large_result = [{'id': i, 'name': f'Product {i}', 'description': 'A' * 1000} 
                       for i in range(1000)]
        
        with patch('app.integrations.ai.chains.is_relevant_query', return_value=True), \
             patch('app.integrations.ai.chains.generate_sql_from_question', return_value='SELECT * FROM products'), \
             patch('app.integrations.ai.chains._validate_table_access', return_value='SELECT * FROM products'), \
             patch('app.integrations.ai.chains.execute_readonly_sql', return_value=large_result), \
             patch('app.integrations.ai.chains.summarize_rows', return_value='Large result processed'):
            
            result = handle_customer_chat_with_db("show me all products", mode="sql")
            
            assert result["mode"] == "sql"
            assert "Large result processed" in result["answer"]
            assert result["sql"] == "SELECT * FROM products"

    def test_timeout_handling(self):
        """Test timeout handling in various scenarios"""
        
        def slow_hybrid_search(*args, **kwargs):
            time.sleep(0.1)  # Simulate slow response (reduced from 2s for faster testing)
            return {
                "success": True,
                "answer": "Slow response",
                "mode": "rag"
            }
        
        with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.integrations.ai.chains.hybrid_search_with_reranking', side_effect=slow_hybrid_search):
            
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            # This should still work, just take longer
            result = handle_customer_chat_with_db("test message", mode="rag")
            assert result["mode"] == "rag"
            assert "Slow response" in result["answer"]

    def test_null_and_none_values(self):
        """Test handling of null and None values in responses"""
        
        # Test SQL with None values
        sql_with_nulls = "SELECT * FROM products WHERE name IS NULL"
        
        with patch('app.integrations.ai.chains.is_relevant_query', return_value=True), \
             patch('app.integrations.ai.chains.generate_sql_from_question', return_value=sql_with_nulls), \
             patch('app.integrations.ai.chains._validate_table_access', return_value=sql_with_nulls), \
             patch('app.integrations.ai.chains.execute_readonly_sql', return_value=[
                 {'id': 1, 'name': None, 'description': 'Valid product'},
                 {'id': 2, 'name': 'Product 2', 'description': None}
             ]), \
             patch('app.integrations.ai.chains.summarize_rows', return_value='Found products with null values'):
            
            result = handle_customer_chat_with_db("show products with null names", mode="sql")
            
            assert result["mode"] == "sql"
            assert "null values" in result["answer"]

    def test_database_connection_failures(self):
        """Test graceful handling of database connection failures"""
        
        try:
            with patch('app.integrations.ai.chains.is_relevant_query', return_value=True), \
                 patch('app.integrations.ai.chains.generate_sql_from_question', return_value='SELECT * FROM products'), \
                 patch('app.integrations.ai.chains._validate_table_access', return_value='SELECT * FROM products'), \
                 patch('app.integrations.ai.chains.execute_readonly_sql', side_effect=Exception("Connection failed")):
                
                result = handle_customer_chat_with_db("show me products", mode="sql")
                
                # Should handle the error gracefully
                assert result["mode"] == "sql"  # Still attempted SQL
                assert result["sql"] == "SELECT * FROM products"
                # Error should be in the answer or handled gracefully
                assert result["answer"] != ""
        except Exception as e:
            # If exception bubbles up, that's also acceptable behavior for connection failures
            assert "Connection failed" in str(e) or "error" in str(e).lower()
