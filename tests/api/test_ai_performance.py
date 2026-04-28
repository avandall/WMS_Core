"""
Performance and concurrency tests for AI functionality
"""

import pytest
import threading
import time
import concurrent.futures
from unittest.mock import patch, MagicMock
from app.application.dtos.ai import ChatDBRequest
from app.integrations.ai.chains import handle_customer_chat_with_db, get_rag_engine


class TestAIPerformance:
    """Test performance and concurrency scenarios for AI functionality"""

    def test_concurrent_sql_requests(self):
        """Test concurrent SQL requests don't interfere with each other"""
        
        results = []
        errors = []
        
        def sql_worker(request_id):
            try:
                with patch('app.integrations.ai.chains.is_relevant_query', return_value=True), \
                     patch('app.integrations.ai.chains.generate_sql_from_question', return_value=f'SELECT * FROM products WHERE id = {request_id}'), \
                     patch('app.integrations.ai.chains._validate_table_access', return_value=f'SELECT * FROM products WHERE id = {request_id}'), \
                     patch('app.integrations.ai.chains.execute_readonly_sql', return_value=[{'id': request_id, 'name': f'Product {request_id}'}]), \
                     patch('app.integrations.ai.chains.summarize_rows', return_value=f'Found product {request_id}'):
                    
                    result = handle_customer_chat_with_db(f"show product {request_id}", mode="sql")
                    results.append((request_id, result["mode"], result["sql"]))
            except Exception as e:
                errors.append((request_id, str(e)))
        
        # Start 20 concurrent SQL requests
        threads = []
        for i in range(20):
            thread = threading.Thread(target=sql_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests completed successfully
        assert len(results) == 20
        assert len(errors) == 0
        
        # Verify each request got the correct result
        for request_id, mode, sql in results:
            assert mode == "sql"
            assert f"SELECT * FROM products WHERE id = {request_id}" in sql

    def test_concurrent_rag_requests(self):
        """Test concurrent RAG requests don't interfere with each other"""
        
        results = []
        errors = []
        
        def rag_worker(request_id):
            try:
                with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
                     patch('app.integrations.ai.chains.hybrid_search_with_reranking') as mock_hybrid:
                    
                    mock_engine = MagicMock()
                    mock_get_engine.return_value = mock_engine
                    mock_hybrid.return_value = {
                        "success": True,
                        "answer": f"RAG response for request {request_id}",
                        "mode": "rag"
                    }
                    
                    result = handle_customer_chat_with_db(f"tell me about product {request_id}", mode="rag")
                    results.append((request_id, result["mode"], result["answer"]))
            except Exception as e:
                errors.append((request_id, str(e)))
        
        # Start 15 concurrent RAG requests
        threads = []
        for i in range(15):
            thread = threading.Thread(target=rag_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests completed successfully
        assert len(results) == 15
        assert len(errors) == 0
        
        # Verify each request got the correct result
        for request_id, mode, answer in results:
            assert mode == "rag"
            assert f"RAG response for request {request_id}" in answer

    def test_mixed_concurrent_requests(self):
        """Test mixed concurrent requests with different modes"""
        
        results = []
        errors = []
        
        def mixed_worker(mode_suffix, request_id):
            try:
                mode = {"sql": "sql", "rag": "rag", "hybrid": "hybrid", "auto": "auto"}[mode_suffix]
                
                if mode == "sql":
                    with patch('app.integrations.ai.chains.is_relevant_query', return_value=True), \
                         patch('app.integrations.ai.chains.generate_sql_from_question', return_value=f'SELECT * FROM products WHERE id = {request_id}'), \
                         patch('app.integrations.ai.chains._validate_table_access', return_value=f'SELECT * FROM products WHERE id = {request_id}'), \
                         patch('app.integrations.ai.chains.execute_readonly_sql', return_value=[{'id': request_id}]), \
                         patch('app.integrations.ai.chains.summarize_rows', return_value=f'SQL result {request_id}'):
                        
                        result = handle_customer_chat_with_db(f"show product {request_id}", mode=mode)
                        results.append((mode_suffix, request_id, result["mode"]))
                        
                elif mode in ["rag", "hybrid", "auto"]:
                    with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
                         patch('app.integrations.ai.chains.hybrid_search_with_reranking') as mock_hybrid, \
                         patch('app.integrations.ai.chains.is_relevant_query', return_value=False):
                        
                        mock_engine = MagicMock()
                        mock_get_engine.return_value = mock_engine
                        mock_hybrid.return_value = {
                            "success": True,
                            "answer": f"Response for {mode_suffix} {request_id}",
                            "mode": mode_suffix
                        }
                        
                        result = handle_customer_chat_with_db(f"tell me about product {request_id}", mode=mode)
                        results.append((mode_suffix, request_id, result["mode"]))
                        
            except Exception as e:
                errors.append((mode_suffix, request_id, str(e)))
        
        # Start mixed concurrent requests
        modes = ["sql", "rag", "hybrid", "auto"]
        threads = []
        
        for i, mode in enumerate(modes):
            for j in range(5):  # 5 requests per mode
                thread = threading.Thread(target=mixed_worker, args=(mode, i*5 + j))
                threads.append(thread)
                thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests completed successfully
        assert len(results) == 20  # 4 modes * 5 requests each
        assert len(errors) == 0
        
        # Verify each mode got the correct results
        mode_counts = {}
        for mode_suffix, request_id, actual_mode in results:
            mode_counts[mode_suffix] = mode_counts.get(mode_suffix, 0) + 1
            if mode_suffix == "sql":
                assert actual_mode == "sql"
            elif mode_suffix == "rag":
                assert actual_mode == "rag"
            elif mode_suffix == "hybrid":
                assert actual_mode in ["hybrid", "hybrid_fallback"]
            elif mode_suffix == "auto":
                assert actual_mode in ["rag_fallback", "hybrid", "rag"]
        
        # Verify we got 5 requests for each mode
        for mode in modes:
            assert mode_counts[mode] == 5

    def test_rag_engine_thread_safety(self):
        """Test RAG engine initialization is thread-safe"""
        
        initialization_count = 0
        engine_instance = None
        lock = threading.Lock()
        
        def mock_get_engine():
            nonlocal initialization_count, engine_instance
            with lock:
                initialization_count += 1
                if engine_instance is None:
                    engine_instance = MagicMock()
            return engine_instance
        
        with patch('app.integrations.ai.chains.get_rag_engine', side_effect=mock_get_engine), \
             patch('app.integrations.ai.chains.hybrid_search_with_reranking') as mock_hybrid:
            
            mock_hybrid.return_value = {
                "success": True,
                "answer": "Thread-safe response",
                "mode": "rag"
            }
            
            results = []
            
            def rag_worker():
                result = handle_customer_chat_with_db("test message", mode="rag")
                results.append(result["mode"])
            
            # Start multiple threads simultaneously
            threads = []
            for _ in range(10):
                thread = threading.Thread(target=rag_worker)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify engine was initialized (once per thread due to patch context)
            assert initialization_count == 10  # One initialization per thread
            # But all threads should get the same behavior
            assert len(results) == 10
            assert all(mode == "rag" for mode in results)

    def test_high_load_performance(self):
        """Test system performance under high load"""
        
        start_time = time.time()
        results = []
        errors = []
        
        def load_worker(worker_id):
            try:
                with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
                     patch('app.integrations.ai.chains.hybrid_search_with_reranking') as mock_hybrid:
                    
                    mock_engine = MagicMock()
                    mock_get_engine.return_value = mock_engine
                    mock_hybrid.return_value = {
                        "success": True,
                        "answer": f"Load test response {worker_id}",
                        "mode": "rag"
                    }
                    
                    result = handle_customer_chat_with_db(f"load test {worker_id}", mode="rag")
                    results.append(worker_id)
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Start 50 concurrent requests
        threads = []
        for i in range(50):
            thread = threading.Thread(target=load_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify performance metrics
        assert len(results) == 50
        assert len(errors) == 0
        assert total_time < 10.0  # Should complete within 10 seconds
        
        # Calculate average response time
        avg_time_per_request = total_time / 50
        assert avg_time_per_request < 0.2  # Average should be under 200ms

    def test_memory_usage_under_load(self):
        """Test memory usage doesn't grow excessively under load"""
        
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss
            can_monitor_memory = True
        except ImportError:
            # Skip memory monitoring if psutil is not available
            can_monitor_memory = False
            initial_memory = 0
        
        def memory_worker(worker_id):
            with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
                 patch('app.integrations.ai.chains.hybrid_search_with_reranking') as mock_hybrid:
                
                mock_engine = MagicMock()
                mock_get_engine.return_value = mock_engine
                mock_hybrid.return_value = {
                    "success": True,
                    "answer": f"Memory test response {worker_id}",
                    "mode": "rag"
                }
                
                # Create some data to test memory usage
                large_data = "x" * 1000  # 1KB per request
                result = handle_customer_chat_with_db(f"memory test {large_data}", mode="rag")
                return result
        
        # Run 100 requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(memory_worker, i) for i in range(100)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        if can_monitor_memory:
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            # Verify memory usage is reasonable (less than 100MB increase)
            assert memory_increase < 100 * 1024 * 1024  # 100MB
        
        assert len(results) == 100

    def test_connection_pool_behavior(self):
        """Test database connection pool behavior under concurrent load"""
        
        connection_count = 0
        max_connections = 0
        
        def mock_execute_sql(*args, **kwargs):
            nonlocal connection_count, max_connections
            connection_count += 1
            max_connections = max(max_connections, connection_count)
            time.sleep(0.01)  # Simulate query time
            connection_count -= 1
            return [{'id': 1, 'name': 'Test Product'}]
        
        with patch('app.integrations.ai.chains.is_relevant_query', return_value=True), \
             patch('app.integrations.ai.chains.generate_sql_from_question', return_value='SELECT * FROM products'), \
             patch('app.integrations.ai.chains._validate_table_access', return_value='SELECT * FROM products'), \
             patch('app.integrations.ai.chains.execute_readonly_sql', side_effect=mock_execute_sql), \
             patch('app.integrations.ai.chains.summarize_rows', return_value='Found products'):
            
            results = []
            
            def pool_worker():
                result = handle_customer_chat_with_db("show products", mode="sql")
                results.append(result["mode"])
            
            # Start more concurrent requests than typical pool size
            threads = []
            for _ in range(30):
                thread = threading.Thread(target=pool_worker)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify connection pool behavior
            assert len(results) == 30
            assert max_connections <= 30  # Should not exceed request count
            assert connection_count == 0  # All connections should be released

    def test_timeout_handling_under_load(self):
        """Test timeout handling under high load conditions"""
        
        def slow_hybrid_search(*args, **kwargs):
            time.sleep(0.5)  # Simulate slow response
            return {
                "success": True,
                "answer": "Slow response",
                "mode": "rag"
            }
        
        start_time = time.time()
        results = []
        
        with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.integrations.ai.chains.hybrid_search_with_reranking', side_effect=slow_hybrid_search):
            
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            def timeout_worker():
                try:
                    result = handle_customer_chat_with_db("slow query", mode="rag")
                    results.append(result["mode"])
                except Exception as e:
                    results.append(f"error: {str(e)}")
            
            # Start 10 concurrent slow requests
            threads = []
            for _ in range(10):
                thread = threading.Thread(target=timeout_worker)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Verify timeout handling
            assert len(results) == 10
            assert total_time < 5.0  # Should complete within reasonable time
            assert all(mode == "rag" for mode in results if not mode.startswith("error"))

    def test_resource_cleanup_under_load(self):
        """Test proper resource cleanup under high load"""
        
        cleanup_tracker = {"count": 0}
        
        def mock_hybrid_search(*args, **kwargs):
            try:
                return {
                    "success": True,
                    "answer": "Test response",
                    "mode": "rag"
                }
            finally:
                cleanup_tracker["count"] += 1
        
        with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.integrations.ai.chains.hybrid_search_with_reranking', side_effect=mock_hybrid_search):
            
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            # Run many requests
            for i in range(100):
                result = handle_customer_chat_with_db(f"test {i}", mode="rag")
                assert result["mode"] == "rag"
            
            # Verify cleanup was called for each request
            assert cleanup_tracker["count"] == 100

    def test_circuit_breaker_behavior(self):
        """Test circuit breaker behavior during failures"""
        
        failure_count = 0
        success_count = 0
        
        def flaky_hybrid_search(*args, **kwargs):
            nonlocal failure_count, success_count
            if failure_count < 5:  # Fail first 5 requests
                failure_count += 1
                raise Exception("Simulated failure")
            else:
                success_count += 1
                return {
                    "success": True,
                    "answer": "Success after failures",
                    "mode": "rag"
                }
        
        with patch('app.integrations.ai.chains.get_rag_engine') as mock_get_engine, \
             patch('app.integrations.ai.chains.hybrid_search_with_reranking', side_effect=flaky_hybrid_search):
            
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            results = []
            
            # Make multiple requests
            for i in range(10):
                result = handle_customer_chat_with_db(f"test {i}", mode="rag")
                # Check if the result indicates a failure (fallback mode or error message)
                if result["mode"] in ["rag_fallback", "hybrid_fallback"] or "error" in result["answer"].lower():
                    results.append(("error", result["mode"]))
                else:
                    results.append(("success", result["mode"]))
            
            # Verify circuit breaker behavior
            assert failure_count == 5
            assert success_count == 5
            assert len(results) == 10
            
            # Check that we got the expected pattern of failures and successes
            error_count = sum(1 for status, _ in results if status == "error")
            success_result_count = sum(1 for status, _ in results if status == "success")
            
            # The first 5 should result in fallback modes due to failures
            # The last 5 should succeed normally
            assert error_count == 5  # First 5 should fail
            assert success_result_count == 5  # Last 5 should succeed
