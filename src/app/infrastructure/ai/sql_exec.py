from __future__ import annotations

import re
import time
import hashlib
from typing import Any, Dict, List
from decimal import Decimal

from sqlalchemy import text
from fastapi.encoders import jsonable_encoder

# Optional advanced validator - import safely with fallback
try:
    from app.core.advanced_validation import SQLInjectionValidator
    HAS_ADVANCED_VALIDATOR = True
except ImportError:
    logger.warning("Advanced SQL validator not available, using parser-based validation")
    SQLInjectionValidator = None
    HAS_ADVANCED_VALIDATOR = False

# Import robust SQL parser
from app.infrastructure.ai.sql_parser import SQLParserValidator

from app.core.logging import get_logger
from app.core.database import engine
from app.infrastructure.ai.settings import ai_engine_settings

logger = get_logger(__name__)

# Enhanced SQL validation patterns (fallback only)
_DANGEROUS_KEYWORDS = [
    'insert', 'update', 'delete', 'drop', 'alter', 'create', 
    'truncate', 'grant', 'revoke', 'copy', 'do', 'call', 'execute'
]

# Dangerous PostgreSQL functions with proper regex patterns (fallback only)
_DANGEROUS_FUNCTION_PATTERNS = [
    r'\bpg_sleep\s*\(',
    r'\bbenchmark\s*\(',
    r'\bversion\s*\(',
    r'\bcurrent_database\s*\(',
    r'\bcurrent_user\s*\(',
    r'\bsession_user\s*\(',
    r'\buser\s*\(',
]

def _remove_comments_and_strings(sql: str) -> str:
    """Remove SQL comments and string literals to prevent bypass attempts."""
    # Use the robust parser's method
    return SQLParserValidator._remove_comments_and_strings(sql)

def _detect_semicolons_outside_strings(sql: str) -> bool:
    """Detect semicolons outside of string literals."""
    # Use parser-based detection for accuracy
    try:
        parse_result = SQLParserValidator.parse_sql_info(sql)
        return parse_result.statement_count > 1
    except Exception:
        # Fallback to simple check
        cleaned_sql = _remove_comments_and_strings(sql)
        return ';' in cleaned_sql

def _create_query_fingerprint(sql: str) -> str:
    """Create a secure fingerprint of the query for logging."""
    return hashlib.sha256(sql.encode('utf-8')).hexdigest()[:16]

def _sanitize_for_logging(sql: str) -> Dict[str, Any]:
    """Prepare SQL data for safe logging without exposing sensitive content."""
    return {
        "query_fingerprint": _create_query_fingerprint(sql),
        "query_length": len(sql),
        "has_params": False,  # Will be set by caller
        "starts_with": sql.strip().lower()[:20] if sql else ""
    }

def _sanitize_error_message(error_msg: str) -> str:
    """Sanitize error messages to prevent leaking sensitive data."""
    # Remove potential SQL literals and parameter values
    sanitized = re.sub(r"'.*'", "'[REDACTED]'", error_msg)
    sanitized = re.sub(r'".*"', '"[REDACTED]"', sanitized)
    # Remove potential numeric values that could be IDs
    sanitized = re.sub(r'\b\d+\b', '[ID]', sanitized)
    return sanitized


def execute_readonly_sql(
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    max_rows: int | None = None,
) -> list[dict[str, Any]]:
    """
    Execute a read-only SQL query with comprehensive security validation.
    
    Features:
    - Multi-layer SQL validation
    - Safe logging with query fingerprinting
    - End-to-end timing measurement
    - Robust Decimal handling
    - Parser-based statement detection
    """
    
    start_time = time.perf_counter()
    
    # Prepare safe logging data
    log_data = _sanitize_for_logging(sql)
    log_data["has_params"] = params is not None
    
    logger.info("Starting SQL execution", extra=log_data)
    
    # Input validation
    if not sql or not sql.strip():
        logger.warning("Empty SQL query provided", extra=log_data)
        raise ValueError("SQL query cannot be empty")
    
    # Clean SQL for validation
    cleaned = sql.strip().rstrip(";").strip()
    lowered = cleaned.lower()
    
    # 1. Robust parser-based validation (primary method)
    try:
        is_valid, violations = SQLParserValidator.validate_sql_structure(
            cleaned, allowed_operations={'SELECT', 'WITH'}
        )
        if not is_valid:
            logger.warning("SQL validation failed", extra={
                **log_data,
                "violations": violations,
                "validation_method": "parser"
            })
            raise ValueError(f"SQL validation failed: {'; '.join(violations)}")
    except Exception as e:
        logger.warning("Parser validation error", extra={
            **log_data,
            "validation_error": str(e),
            "validation_method": "parser_error"
        })
        # Continue to advanced validator if available
    
    # 2. Advanced validation if available (secondary method)
    if HAS_ADVANCED_VALIDATOR and SQLInjectionValidator:
        try:
            is_valid, violations = SQLInjectionValidator.validate_sql_structure(
                cleaned, allowed_operations={'SELECT', 'WITH'}
            )
            if not is_valid:
                logger.warning("SQL validation failed", extra={
                    **log_data,
                    "violations": violations,
                    "validation_method": "advanced"
                })
                raise ValueError(f"SQL validation failed: {'; '.join(violations)}")
        except Exception as e:
            logger.warning("Advanced validation error", extra={
                **log_data,
                "validation_error": str(e),
                "validation_method": "advanced_fallback"
            })
            # Continue to basic validation
    
    # 3. Basic validation (final fallback - should rarely be reached)
    if not lowered.startswith(("select", "with")):
        logger.warning("Blocked SQL query: invalid statement type", extra={
            **log_data,
            "statement_type": lowered[:10],
            "validation_method": "basic"
        })
        raise ValueError("Only SELECT/WITH queries are allowed")
    
    # 4. Multi-statement detection with parser awareness
    if _detect_semicolons_outside_strings(cleaned):
        logger.warning("Blocked SQL query: multiple statements detected", extra={
            **log_data,
            "validation_method": "parser_semicolon"
        })
        raise ValueError("Multiple SQL statements are not allowed")
    
    # 5. Enhanced keyword detection (fallback only)
    for keyword in _DANGEROUS_KEYWORDS:
        if re.search(rf'\b{re.escape(keyword)}\b', lowered):
            logger.warning("Blocked SQL query: dangerous keyword detected", extra={
                **log_data,
                "dangerous_keyword": keyword,
                "validation_method": "basic_keyword"
            })
            raise ValueError(f"Dangerous keyword '{keyword}' not allowed")
    
    # 6. Dangerous function detection (fallback only)
    for pattern in _DANGEROUS_FUNCTION_PATTERNS:
        if re.search(pattern, lowered):
            logger.warning("Blocked SQL query: dangerous function detected", extra={
                **log_data,
                "dangerous_pattern": pattern,
                "validation_method": "basic_function"
            })
            raise ValueError("Dangerous function call not allowed")

    # Prepare for execution
    row_limit = max_rows if max_rows is not None else ai_engine_settings.db_max_rows
    
    try:
        with engine.connect() as conn:
            # Database-specific execution options
            sql_text = text(cleaned)
            
            # Only apply execution_options if available and non-empty
            if hasattr(engine, 'dialect') and engine.dialect.name == 'postgresql':
                sql_text = sql_text.execution_options(postgresql_readonly=True)
                execution_options_applied = True
            else:
                execution_options_applied = False
            
            logger.info("Executing SQL query", extra={
                **log_data,
                "row_limit": row_limit,
                "dialect": getattr(engine.dialect, 'name', 'unknown'),
                "execution_options_applied": execution_options_applied
            })
            
            # Execute query
            result = conn.execute(sql_text, params or {})
            
            # Fetch results
            rows = result.mappings().fetchmany(row_limit)
            
            # Serialize with proper Decimal handling
            serialized_data = []
            for row in rows:
                serialized_row = {}
                for key, value in row.items():
                    # Explicit Decimal type checking
                    if isinstance(value, Decimal):
                        # Convert Decimal to string to preserve precision
                        serialized_row[key] = str(value)
                    else:
                        serialized_row[key] = value
                serialized_data.append(serialized_row)
            
            # Calculate execution time
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            logger.info("SQL execution completed successfully", extra={
                **log_data,
                "row_count": len(serialized_data),
                "execution_time_ms": execution_time_ms,
                "serialization_method": "decimal_preserving"
            })
            
            return jsonable_encoder(serialized_data)
            
    except Exception as e:
        execution_time_ms = (time.perf_counter() - start_time) * 1000
        
        logger.error("SQL execution failed", extra={
            **log_data,
            "error": _sanitize_error_message(str(e)),
            "error_type": type(e).__name__,
            "execution_time_ms": execution_time_ms,
            "failed_at": "execution"
        })
        raise