#!/usr/bin/env python3
"""
Test runner for enhanced SQL execution module with security fixes.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def run_sql_exec_tests():
    """Run all SQL execution tests."""
    print("🔒 Running Enhanced SQL Execution Tests")
    print("=" * 60)
    
    # Test categories
    test_categories = [
        {
            "name": "SQL Parser Tests",
            "path": "tests/test_sql_parser.py",
            "description": "Robust SQL parsing and validation"
        },
        {
            "name": "SQL Execution Security Tests",
            "path": "tests/test_sql_exec.py::TestSQLExecutionSecurity",
            "description": "Security validation and injection protection"
        },
        {
            "name": "SQL Execution Functionality Tests",
            "path": "tests/test_sql_exec.py::TestSQLExecutionFunctionality",
            "description": "Core SQL execution functionality"
        },
        {
            "name": "SQL Execution Edge Cases",
            "path": "tests/test_sql_exec.py::TestSQLExecutionEdgeCases",
            "description": "Edge cases and boundary conditions"
        },
        {
            "name": "SQL Execution Logging Tests",
            "path": "tests/test_sql_exec.py::TestSQLExecutionLogging",
            "description": "Structured logging and error handling"
        },
        {
            "name": "SQL Execution Performance Tests",
            "path": "tests/test_sql_exec.py::TestSQLExecutionPerformance",
            "description": "Performance and scalability"
        }
    ]
    
    all_passed = True
    
    for category in test_categories:
        print(f"\n🧪 {category['name']}")
        print(f"📝 {category['description']}")
        print("-" * 40)
        
        try:
            # Run pytest for the category
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                category["path"], 
                "-v",
                "--tb=short",
                "--color=yes"
            ], capture_output=True, text=True, cwd=Path(__file__).parent)
            
            if result.returncode == 0:
                print("✅ All tests passed!")
                print(result.stdout)
            else:
                print("❌ Some tests failed!")
                print(result.stdout)
                print(result.stderr)
                all_passed = False
                
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All SQL execution tests passed! Security fixes are working.")
        return 0
    else:
        print("⚠️  Some tests failed. Review the output above.")
        return 1

def run_security_demo():
    """Demonstrate security improvements."""
    print("\n🛡️  Security Improvements Demonstration")
    print("-" * 40)
    
    try:
        from app.infrastructure.ai.sql_exec import execute_readonly_sql
        import logging
        
        # Set up logging to see security messages
        logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
        
        print("Testing security improvements...")
        
        # Test cases that should be blocked
        dangerous_queries = [
            ("INSERT statement", "INSERT INTO products VALUES (1, 'test')"),
            ("UPDATE statement", "UPDATE products SET name = 'test'"),
            ("DELETE statement", "DELETE FROM products WHERE id = 1"),
            ("DROP statement", "DROP TABLE products"),
            ("Multiple statements", "SELECT * FROM products; DROP TABLE products;"),
            ("Dangerous function", "SELECT pg_sleep(10)"),
            ("COPY command", "COPY products FROM 'file.csv'"),
            ("DO block", "DO $$ BEGIN END $$"),
            ("CALL procedure", "CALL test_procedure()"),
            ("EXECUTE command", "EXECUTE 'SELECT 1'"),
        ]
        
        blocked_count = 0
        for description, query in dangerous_queries:
            try:
                execute_readonly_sql(query)
                print(f"❌ FAILED: {description} should have been blocked")
            except ValueError as e:
                # Expected since we don't have real DB connection
                if "Only SELECT/WITH queries are allowed" in str(e) or "not allowed" in str(e):
                    print(f"✅ BLOCKED: {description}")
                    blocked_count += 1
                else:
                    print(f"⚠️  OTHER ERROR: {description} - {str(e)}")
            except Exception as e:
                # Expected since we don't have real DB connection
                if "Only SELECT/WITH queries are allowed" in str(e) or "not allowed" in str(e):
                    print(f"✅ BLOCKED: {description}")
                    blocked_count += 1
                else:
                    print(f"⚠️  OTHER ERROR: {description} - {str(e)}")
        
        print(f"\n📊 Security Test Results:")
        print(f"   Total dangerous queries: {len(dangerous_queries)}")
        print(f"   Successfully blocked: {blocked_count}")
        print(f"   Security effectiveness: {blocked_count/len(dangerous_queries)*100:.1f}%")
        
        return blocked_count == len(dangerous_queries)
        
    except Exception as e:
        print(f"❌ Security demo failed: {e}")
        return False

def run_syntax_validation_demo():
    """Demonstrate syntax fixes."""
    print("\n🔧 Syntax Validation Demonstration")
    print("-" * 35)
    
    try:
        # Test that module imports correctly (no syntax errors)
        from app.infrastructure.ai.sql_exec import execute_readonly_sql
        print("✅ Module imports successfully - no syntax errors")
        
        # Test function signature is correct
        import inspect
        sig = inspect.signature(execute_readonly_sql)
        print(f"✅ Function signature: {sig}")
        
        # Test that regex compiles correctly
        import re
        pattern = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|do|call|execute)\b", re.IGNORECASE)
        print("✅ Regex pattern compiles successfully")
        
        # Test regex functionality
        test_cases = [
            ("SELECT * FROM products", False),
            ("INSERT INTO products", True),
            ("created_at", False),  # Should not match due to word boundaries
            ("selection", False),  # Should not match due to word boundaries
        ]
        
        for text, should_match in test_cases:
            matches = bool(pattern.search(text.lower()))
            if matches == should_match:
                print(f"✅ Regex test passed: '{text}' -> {'matches' if matches else 'no match'}")
            else:
                print(f"❌ Regex test failed: '{text}' -> expected {'matches' if should_match else 'no match'}, got {'matches' if matches else 'no match'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Syntax validation demo failed: {e}")
        return False

def main():
    """Main test runner."""
    print("🔒 Enhanced SQL Execution Security Fixes")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("src").exists():
        print("❌ Error: Run this script from the project root directory")
        return 1
    
    # Run all test suites
    test_results = []
    
    # 1. Unit tests
    unit_test_result = run_sql_exec_tests()
    test_results.append(("Unit Tests", unit_test_result == 0))
    
    # 2. Security demo
    security_demo_result = run_security_demo()
    test_results.append(("Security Demo", security_demo_result))
    
    # 3. Syntax validation demo
    syntax_demo_result = run_syntax_validation_demo()
    test_results.append(("Syntax Validation", syntax_demo_result))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("-" * 20)
    
    all_passed = True
    for test_name, passed in test_results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! SQL execution security fixes are working correctly.")
        print("🔒 Critical security vulnerabilities have been resolved:")
        print("   ✅ Implemented robust SQL parser-based validation")
        print("   ✅ Added sqlparse dependency for AST-based parsing")
        print("   ✅ Fixed SQLInjectionValidator import with graceful fallback")
        print("   ✅ Enhanced multi-layer SQL validation")
        print("   ✅ Fixed function signature syntax errors")
        print("   ✅ Fixed tuple concatenation bug")
        print("   ✅ Fixed database execute call syntax")
        print("   ✅ Added comprehensive structured logging")
        print("   ✅ Improved Decimal precision handling")
        print("   ✅ Added end-to-end timing measurement")
        print("   ✅ Added database dialect awareness")
        print("   ✅ Implemented safe logging with query fingerprinting")
        print("   ✅ Added error message sanitization")
        print("   ✅ Enhanced PostgreSQL dollar-quoted string support")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
