"""Robust SQL parsing and validation using AST-based analysis."""

from __future__ import annotations

import re
from typing import List, Dict, Any, Set, Tuple, Optional
from dataclasses import dataclass

try:
    import sqlparse
    HAS_SQLPARSE = True
except ImportError:
    HAS_SQLPARSE = False

@dataclass
class SQLParseResult:
    """Result of SQL parsing analysis."""
    is_valid: bool
    violations: List[str]
    statement_count: int
    statement_types: List[str]
    dangerous_functions: List[str]
    has_comments: bool
    has_string_literals: bool

class SQLParserValidator:
    """Robust SQL parser and validator using AST-based analysis."""
    
    # Dangerous PostgreSQL functions
    DANGEROUS_FUNCTIONS = {
        'pg_sleep', 'benchmark', 'version', 'current_database',
        'current_user', 'session_user', 'user', 'pg_cancel_backend',
        'pg_terminate_backend', 'pg_reload_conf', 'pg_start_backup',
        'pg_stop_backup', 'pg_switch_wal', 'pg_current_wal_lsn'
    }
    
    # Allowed statement types for read-only operations
    ALLOWED_STATEMENT_TYPES = {'SELECT', 'WITH'}
    
    # Dangerous keywords (in addition to statement types)
    DANGEROUS_KEYWORDS = {
        'insert', 'update', 'delete', 'drop', 'alter', 'create',
        'truncate', 'grant', 'revoke', 'copy', 'do', 'call', 'execute',
        'commit', 'rollback', 'savepoint', 'release', 'prepare', 'deallocate'
    }
    
    @classmethod
    def validate_sql_structure(
        cls, 
        sql: str, 
        allowed_operations: Optional[Set[str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate SQL structure using AST-based parsing.
        
        Args:
            sql: SQL query to validate
            allowed_operations: Set of allowed statement types (defaults to SELECT/WITH)
            
        Returns:
            Tuple of (is_valid, violations)
        """
        if allowed_operations is None:
            allowed_operations = cls.ALLOWED_STATEMENT_TYPES
        
        violations = []
        
        # Parse SQL into AST
        try:
            if HAS_SQLPARSE:
                return cls._validate_with_sqlparse(sql, allowed_operations)
            else:
                return cls._validate_with_regex(sql, allowed_operations)
        except Exception as e:
            violations.append(f"SQL parsing failed: {str(e)}")
            return False, violations
    
    @classmethod
    def _validate_with_sqlparse(
        cls, 
        sql: str, 
        allowed_operations: Set[str]
    ) -> Tuple[bool, List[str]]:
        """Validate using sqlparse library for robust AST analysis."""
        violations = []
        
        # Parse SQL into tokens
        parsed = sqlparse.parse(sql)
        
        if not parsed:
            violations.append("Empty or invalid SQL")
            return False, violations
        
        # Check for multiple statements
        if len(parsed) > 1:
            violations.append(f"Multiple statements detected: {len(parsed)} statements")
        
        # Analyze each statement
        for i, statement in enumerate(parsed):
            # Get statement type
            stmt_type = cls._get_statement_type(statement)
            
            if stmt_type not in allowed_operations:
                violations.append(f"Statement {i+1}: '{stmt_type}' not allowed. Allowed: {', '.join(allowed_operations)}")
            
            # Check for dangerous functions
            dangerous_funcs = cls._find_dangerous_functions(statement)
            if dangerous_funcs:
                violations.append(f"Statement {i+1}: Dangerous functions detected: {', '.join(dangerous_funcs)}")
            
            # Check for dangerous keywords
            dangerous_keywords = cls._find_dangerous_keywords(statement)
            if dangerous_keywords:
                violations.append(f"Statement {i+1}: Dangerous keywords detected: {', '.join(dangerous_keywords)}")
        
        return len(violations) == 0, violations
    
    @classmethod
    def _validate_with_regex(
        cls, 
        sql: str, 
        allowed_operations: Set[str]
    ) -> Tuple[bool, List[str]]:
        """Fallback validation using enhanced regex patterns."""
        violations = []
        
        # Remove comments and string literals for analysis
        cleaned_sql = cls._remove_comments_and_strings(sql)
        
        # Check for multiple statements (after removing strings/comments)
        if cls._has_multiple_statements(cleaned_sql):
            violations.append("Multiple statements detected")
        
        # Check statement type
        stmt_type = cls._get_statement_type_regex(cleaned_sql)
        if stmt_type not in allowed_operations:
            violations.append(f"Statement type '{stmt_type}' not allowed. Allowed: {', '.join(allowed_operations)}")
        
        # Check for dangerous functions
        dangerous_funcs = cls._find_dangerous_functions_regex(cleaned_sql)
        if dangerous_funcs:
            violations.append(f"Dangerous functions detected: {', '.join(dangerous_funcs)}")
        
        # Check for dangerous keywords
        dangerous_keywords = cls._find_dangerous_keywords_regex(cleaned_sql)
        if dangerous_keywords:
            violations.append(f"Dangerous keywords detected: {', '.join(dangerous_keywords)}")
        
        return len(violations) == 0, violations
    
    @classmethod
    def _get_statement_type(cls, statement) -> str:
        """Extract statement type from parsed SQL."""
        # Get first non-whitespace token
        tokens = [t for t in statement.flatten() if not t.is_whitespace]
        if tokens:
            return tokens[0].ttype.upper() if tokens[0].ttype else tokens[0].value.upper()
        return "UNKNOWN"
    
    @classmethod
    def _get_statement_type_regex(cls, sql: str) -> str:
        """Extract statement type using regex (fallback)."""
        # Look for first word at start of SQL
        match = re.match(r'^\s*([a-zA-Z_]+)', sql.strip(), re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return "UNKNOWN"
    
    @classmethod
    def _find_dangerous_functions(cls, statement) -> List[str]:
        """Find dangerous function calls in parsed SQL."""
        dangerous_funcs = []
        
        for token in statement.flatten():
            if token.value and token.value.lower() in cls.DANGEROUS_FUNCTIONS:
                # Check if it's actually a function call (followed by parentheses)
                next_tokens = [t for t in statement.flatten() if not t.is_whitespace]
                for i, t in enumerate(next_tokens):
                    if t == token and i + 1 < len(next_tokens):
                        if next_tokens[i + 1].value == '(':
                            dangerous_funcs.append(token.value.lower())
                            break
        
        return dangerous_funcs
    
    @classmethod
    def _find_dangerous_functions_regex(cls, sql: str) -> List[str]:
        """Find dangerous function calls using regex (fallback)."""
        dangerous_funcs = []
        
        for func in cls.DANGEROUS_FUNCTIONS:
            # Pattern: function name followed by parentheses
            pattern = rf'\b{re.escape(func)}\s*\('
            if re.search(pattern, sql, re.IGNORECASE):
                dangerous_funcs.append(func)
        
        return dangerous_funcs
    
    @classmethod
    def _find_dangerous_keywords(cls, statement) -> List[str]:
        """Find dangerous keywords in parsed SQL."""
        dangerous_keywords = []
        
        for token in statement.flatten():
            if (token.value and 
                token.value.lower() in cls.DANGEROUS_KEYWORDS and
                token.ttype not in (sqlparse.tokens.String, sqlparse.tokens.Comment)):
                dangerous_keywords.append(token.value.lower())
        
        return dangerous_keywords
    
    @classmethod
    def _find_dangerous_keywords_regex(cls, sql: str) -> List[str]:
        """Find dangerous keywords using regex (fallback)."""
        dangerous_keywords = []
        
        for keyword in cls.DANGEROUS_KEYWORDS:
            # Pattern: word boundary around keyword
            pattern = rf'\b{re.escape(keyword)}\b'
            if re.search(pattern, sql, re.IGNORECASE):
                dangerous_keywords.append(keyword)
        
        return dangerous_keywords
    
    @classmethod
    def _has_multiple_statements(cls, sql: str) -> bool:
        """Check if SQL contains multiple statements."""
        # Look for semicolons that are not in strings
        # This is a simplified check - sqlparse would be more reliable
        return ';' in sql
    
    @classmethod
    def _remove_comments_and_strings(cls, sql: str) -> str:
        """Remove comments and string literals for analysis."""
        # Remove single-line comments
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        
        # Remove multi-line comments
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        # Remove dollar-quoted strings (PostgreSQL)
        sql = re.sub(r'\$\$[^$]*?\$\$', '', sql)
        sql = re.sub(r'\$[^$\s]*\$(.*?)\$\1\$', r'\1', sql, flags=re.DOTALL)
        
        # Remove single-quoted strings
        sql = re.sub(r"'(?:\\.|[^'\\])*'", '', sql)
        
        # Remove double-quoted strings
        sql = re.sub(r'"(?:\\.|[^"\\])*"', '', sql)
        
        return sql
    
    @classmethod
    def parse_sql_info(cls, sql: str) -> SQLParseResult:
        """Parse SQL and return detailed analysis."""
        violations = []
        
        try:
            if HAS_SQLPARSE:
                parsed = sqlparse.parse(sql)
                statement_count = len(parsed)
                statement_types = [cls._get_statement_type(stmt) for stmt in parsed]
                
                dangerous_functions = []
                for stmt in parsed:
                    dangerous_functions.extend(cls._find_dangerous_functions(stmt))
                
                has_comments = any('--' in sql or '/*' in sql for _ in parsed)
                has_string_literals = bool(re.search(r'["\']', sql))
                
            else:
                # Fallback analysis
                cleaned_sql = cls._remove_comments_and_strings(sql)
                statement_count = 1 if sql.strip() else 0
                statement_types = [cls._get_statement_type_regex(sql)]
                dangerous_functions = cls._find_dangerous_functions_regex(cleaned_sql)
                has_comments = '--' in sql or '/*' in sql
                has_string_literals = bool(re.search(r'["\']', sql))
            
            is_valid = len(violations) == 0
            
            return SQLParseResult(
                is_valid=is_valid,
                violations=violations,
                statement_count=statement_count,
                statement_types=statement_types,
                dangerous_functions=dangerous_functions,
                has_comments=has_comments,
                has_string_literals=has_string_literals
            )
            
        except Exception as e:
            return SQLParseResult(
                is_valid=False,
                violations=[f"Parse error: {str(e)}"],
                statement_count=0,
                statement_types=[],
                dangerous_functions=[],
                has_comments=False,
                has_string_literals=False
            )
