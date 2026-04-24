"""
Tests for AI chat endpoint mode functionality
"""

import pytest
from unittest.mock import patch, MagicMock
from app.application.dtos.ai import ChatDBRequest
from app.infrastructure.ai.chains import handle_customer_chat_with_db


class TestAIModeFunctionality:
    """Test AI chat endpoint respects mode field"""

    def test_sql_mode_forces_sql_processing(self):
        """Test that mode='sql' forces SQL processing"""
        
        # Mock the SQL-related functions
        with patch('app.infrastructure.ai.chains.is_relevant_query', return_value=True), \
             patch('app.infrastructure.ai.chains.generate_sql_from_question', return_value='SELECT * FROM products'), \
             patch('app.infrastructure.ai.chains._validate_table_access', return_value='SELECT * FROM products'), \
             patch('app.infrastructure.ai.chains.execute_readonly_sql', return_value=[{'name': 'Test Product'}]), \
             patch('app.infrastructure.ai.chains.summarize_rows', return_value='Found 1 product'):
            
            result = handle_customer_chat_with_db("show me products", mode="sql")
            
            assert result["mode"] == "sql"
            assert result["sql"] == "SELECT * FROM products"
            assert "Found 1 product" in result["answer"]

    def test_sql_mode_blocks_irrelevant_queries(self):
        """Test that mode='sql' blocks irrelevant queries"""
        
        with patch('app.infrastructure.ai.chains.is_relevant_query', return_value=False):
            
            result = handle_customer_chat_with_db("what is the weather", mode="sql")
            
            assert result["mode"] == "sql_blocked"
            assert "Xin loi" in result["answer"]
            assert result["sql"] == ""

    def test_rag_mode_forces_rag_processing(self):
        """Test that mode='rag' forces RAG processing"""
        
        with patch('app.infrastructure.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.infrastructure.ai.chains.hybrid_search_with_reranking') as mock_hybrid:
            
            # Mock successful RAG engine
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            # Mock successful hybrid search
            mock_hybrid.return_value = {
                "success": True,
                "answer": "Product information from RAG engine",
                "mode": "rag"
            }
            
            result = handle_customer_chat_with_db("tell me about products", mode="rag")
            
            assert result["mode"] == "rag"
            assert "Product information from RAG engine" in result["answer"]
            assert result["sql"] == ""

    def test_rag_mode_handles_unavailable_engine(self):
        """Test that mode='rag' handles unavailable RAG engine"""
        
        with patch('app.infrastructure.ai.chains.get_rag_engine', return_value=None):
            
            result = handle_customer_chat_with_db("tell me about products", mode="rag")
            
            assert result["mode"] == "rag_unavailable"
            assert "not available" in result["answer"]

    def test_hybrid_mode_with_rag_success(self):
        """Test that mode='hybrid' uses RAG when successful"""
        
        with patch('app.infrastructure.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.infrastructure.ai.chains.hybrid_search_with_reranking') as mock_hybrid:
            
            # Mock successful RAG engine
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            # Mock successful hybrid search with good answer
            mock_hybrid.return_value = {
                "success": True,
                "answer": "This is a comprehensive answer about products from hybrid search",
                "mode": "hybrid"
            }
            
            result = handle_customer_chat_with_db("tell me about products", mode="hybrid")
            
            assert result["mode"] == "hybrid"
            assert "comprehensive answer" in result["answer"]

    def test_hybrid_mode_falls_back_to_sql(self):
        """Test that mode='hybrid' falls back to SQL when RAG is insufficient"""
        
        with patch('app.infrastructure.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.infrastructure.ai.chains.hybrid_search_with_reranking') as mock_hybrid, \
             patch('app.infrastructure.ai.chains.is_relevant_query', return_value=True), \
             patch('app.infrastructure.ai.chains.generate_sql_from_question', return_value='SELECT * FROM products'), \
             patch('app.infrastructure.ai.chains._validate_table_access', return_value='SELECT * FROM products'), \
             patch('app.infrastructure.ai.chains.execute_readonly_sql', return_value=[{'name': 'Test Product'}]), \
             patch('app.infrastructure.ai.chains.summarize_rows', return_value='Found 1 product'):
            
            # Mock RAG engine
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            # Mock insufficient RAG response (short answer)
            mock_hybrid.return_value = {
                "success": True,
                "response": "Short",  # Too short, will trigger fallback
                "mode": "hybrid"
            }
            
            result = handle_customer_chat_with_db("show me products", mode="hybrid")
            
            # Should fall back to SQL
            assert result["mode"] == "sql"
            assert result["sql"] == "SELECT * FROM products"

    def test_auto_mode_behavior(self):
        """Test that auto mode (default) behaves as expected"""
        
        with patch('app.infrastructure.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.infrastructure.ai.chains.hybrid_search_with_reranking') as mock_hybrid, \
             patch('app.infrastructure.ai.chains.is_relevant_query', return_value=False):
            
            # Mock successful RAG engine
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            # Mock successful RAG response
            mock_hybrid.return_value = {
                "success": True,
                "answer": "This is a good answer from auto mode",
                "mode": "hybrid"
            }
            
            # Test default mode (auto)
            result = handle_customer_chat_with_db("tell me about products")
            
            assert result["mode"] == "rag_fallback"
            assert "good answer" in result["answer"]

    def test_mode_case_insensitivity(self):
        """Test that mode parameter is case insensitive"""
        
        with patch('app.infrastructure.ai.chains.is_relevant_query', return_value=True), \
             patch('app.infrastructure.ai.chains.generate_sql_from_question', return_value='SELECT * FROM products'), \
             patch('app.infrastructure.ai.chains._validate_table_access', return_value='SELECT * FROM products'), \
             patch('app.infrastructure.ai.chains.execute_readonly_sql', return_value=[{'name': 'Test Product'}]), \
             patch('app.infrastructure.ai.chains.summarize_rows', return_value='Found 1 product'):
            
            # Test uppercase mode
            result = handle_customer_chat_with_db("show me products", mode="SQL")
            assert result["mode"] == "sql"
            
            # Test mixed case mode
            result = handle_customer_chat_with_db("show me products", mode="Sql")
            assert result["mode"] == "sql"

    def test_invalid_mode_defaults_to_auto(self):
        """Test that invalid mode defaults to auto behavior"""
        
        with patch('app.infrastructure.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.infrastructure.ai.chains.hybrid_search_with_reranking') as mock_hybrid, \
             patch('app.infrastructure.ai.chains.is_relevant_query', return_value=False):
            
            # Mock successful RAG engine
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            # Mock successful RAG response
            mock_hybrid.return_value = {
                "success": True,
                "answer": "Auto mode response",
                "mode": "hybrid"
            }
            
            # Test invalid mode - should default to auto behavior
            result = handle_customer_chat_with_db("tell me about products", mode="invalid")
            
            # Should behave like auto mode
            assert result["mode"] == "rag_fallback"
            assert "Auto mode response" in result["answer"]
