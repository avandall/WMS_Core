from __future__ import annotations

from typing import Any
import os
import re
import threading
from datetime import datetime, timedelta

from app.infrastructure.ai.database import get_langchain_db
from app.infrastructure.ai.llm import get_chat_model
from app.infrastructure.ai.settings import ai_engine_settings
from app.infrastructure.ai.sql_exec import execute_readonly_sql

# Import advanced RAG engine from lessons
try:
    from ai_engine.core.engine import WMSEngine, ProcessingMode
    from ai_engine.config.settings import settings as ai_settings
    RAG_ENGINE_AVAILABLE = True
except ImportError:
    RAG_ENGINE_AVAILABLE = False
    print("Warning: Advanced RAG engine not available, falling back to SQL-only mode")


def _extract_sql(text: str) -> str:
    cleaned = (text or "").strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]
            cleaned = cleaned.split("\n", 1)[-1]
    return cleaned.strip().rstrip(";").strip()


def _validate_table_access(sql: str) -> str:
    """Validate that SQL only accesses allowed WMS tables."""
    
    # Define allowed table patterns (WMS-specific tables only)
    allowed_tables = {
        'products', 'inventory', 'warehouses', 'customers', 'orders', 
        'documents', 'suppliers', 'transactions', 'shipments', 'positions',
        'product_entities', 'inventory_entities', 'warehouse_entities',
        'user_entities', 'document_entities', 'position_entities'
    }
    
    # Extract table names using regex patterns
    # Look for FROM, JOIN, INTO table references
    table_patterns = [
        r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'\bINTO\s+([a-zA-Z_][a-zA-Z0-9_]*)',
    ]
    
    found_tables = set()
    for pattern in table_patterns:
        matches = re.findall(pattern, sql, re.IGNORECASE)
        found_tables.update(match.lower() for match in matches)
    
    # Check for forbidden tables
    forbidden_tables = found_tables - allowed_tables
    if forbidden_tables:
        raise ValueError(f"Access to forbidden tables not allowed: {', '.join(sorted(forbidden_tables))}")
    
    return sql

def generate_sql_from_question(question: str) -> str:
    """Use an LLM to generate a safe, read-only SQL query for the WMS DB."""

    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Missing dependency: `langchain-core`.") from exc

    db = get_langchain_db()
    schema = db.get_table_info()
    max_rows = ai_engine_settings.db_max_rows

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a Senior PostgreSQL Analyst for a Warehouse Management System.\n"
                "Your goal is to write a syntactically correct SQL query based on the schema provided.\n"
                "Rules:\n"
                f"- Use ONLY SELECT or WITH statements.\n"
                f"- LIMIT results to {max_rows} unless specified.\n"
                "- ONLY query WMS tables: products, inventory, warehouses, customers, orders, documents, suppliers, etc.\n"
                "- NEVER query system tables, user tables, or authentication tables.\n"
                "- Return ONLY the SQL code, no markdown, no explanation.",
            ),
            ("human", "Question: {question}\n\nDatabase schema:\n{schema}\n\nSQL:"),
        ]
    )

    llm = get_chat_model(temperature=0)
    chain = prompt | llm | StrOutputParser()
    sql = chain.invoke({"question": question, "schema": schema})
    cleaned_sql = _extract_sql(sql)
    
    # Validate table access before returning
    return _validate_table_access(cleaned_sql)


def summarize_rows(question: str, sql: str, rows: list[dict[str, Any]]) -> str:
    """Turn SQL rows into a short customer-facing answer."""

    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Missing dependency: `langchain-core`.") from exc

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a professional WMS Support Agent.\n"
                "- Always answer in the SAME LANGUAGE as the customer's question.\n"
                "- Convert technical DB rows into a polite, natural language answer.\n"
                "- If rows are empty, politely inform them no data was found.\n"
                "- Be concise.",
            ),
            ("human", "Question: {question}\nSQL: {sql}\nData: {rows}\nAnswer:"),
        ]
    )

    llm = get_chat_model(temperature=0.7)
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"question": question, "sql": sql, "rows": rows})


def is_relevant_query(question: str) -> bool:
    """Light WMS relevance filter to reduce prompt-injection / off-topic requests."""

    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Missing dependency: `langchain-core`.") from exc

    # First, check for obvious WMS-related keywords (removed generic terms)
    wms_keywords = [
        'product', 'inventory', 'warehouse', 'stock', 'item', 'goods',
        'customer', 'client', 'order', 'document', 'transaction',
        'import', 'export', 'transfer', 'sale', 'purchase',
        'quantity', 'price', 'cost', 'supplier', 'vendor',
        'location', 'storage', 'shelf', 'rack', 'bin',
        'shipment', 'delivery', 'receiving', 'dispatch',
        'how many', 'count', 'list', 'show', 'find', 'search', 'report',
        # Vietnamese keywords
        'sản phẩm', 'hàng tồn kho', 'kho hàng', 'khách hàng', 'đơn hàng',
        'số lượng', 'giá', 'vị trí', 'danh sách', 'hiển thị', 'tìm kiếm',
        'bao nhiêu', 'cái', 'chiếc', 'món', 'hàng', 'kiểm tra', 'tồn kho'
    ]
    
    question_lower = question.lower()
    
    # First check for forbidden table names explicitly
    forbidden_tables = ['users', 'auth', 'system', 'information_schema', 'pg_', 'admin', 'password', 'credentials']
    if any(table in question_lower for table in forbidden_tables):
        return False
    
    # If any WMS keywords are found, consider it relevant
    if any(keyword in question_lower for keyword in wms_keywords):
        return True
    
    # If it's a short question (1-3 words), be more lenient and let LLM decide
    if len(question_lower.split()) <= 3:
        pass  # Continue to LLM evaluation
    else:
        # Additional check for business/financial context that might be WMS-related
        business_keywords = ['market', 'analysis', 'report', 'business', 'financial', 'database', 'optimization', 'api', 'design', 'patterns']
        if any(keyword in question_lower for keyword in business_keywords):
            # For business keywords, be more careful - use LLM to decide
            pass
        else:
            # If no relevant keywords at all, likely irrelevant
            return False
    
    # If no keywords found, use LLM for more nuanced判断
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a relevance filter for a Warehouse Management System (WMS). "
                "Determine if the question is related to warehouse operations, inventory management, "
                "products, customers, orders, or business data analysis. "
                "Be lenient - if the question could reasonably be about warehouse data, mark it relevant. "
                "Return ONLY 'true' or 'false' (lowercase). "
                "Examples of relevant: 'how many items', 'show me products', 'customer orders', 'inventory levels' "
                "Examples of irrelevant: 'weather today', 'sports scores', 'political news', 'personal advice'."
            ),
            ("human", "Question: {question}"),
        ]
    )

    llm = get_chat_model(temperature=0.1)  # Slightly higher temperature for more flexibility
    chain = prompt | llm | StrOutputParser()
    result = (chain.invoke({"question": question}) or "").strip().lower()
    
    # More lenient check - accept various true responses
    return result.startswith("true") or result == "yes" or result == "relevant"


# Global RAG engine instance (thread-safe lazy initialization)
_rag_engine = None
_rag_engine_lock = threading.Lock()
_rag_engine_init_attempted = False
_rag_engine_last_attempt = None
_rag_engine_failure_cooldown = 300  # 5 minutes cooldown between failed attempts

def get_rag_engine():
    """Get or initialize the RAG engine with thread-safe initialization and failure cooldown"""
    global _rag_engine, _rag_engine_init_attempted, _rag_engine_last_attempt
    
    # Return existing engine if available
    if _rag_engine is not None:
        return _rag_engine
    
    # Check if we're in cooldown period after a failed initialization
    if (_rag_engine_init_attempted and 
        _rag_engine_last_attempt and 
        datetime.now() - _rag_engine_last_attempt < timedelta(seconds=_rag_engine_failure_cooldown)):
        return None
    
    # Use lock to prevent race conditions during initialization
    with _rag_engine_lock:
        # Double-check pattern: check again after acquiring lock
        if _rag_engine is not None:
            return _rag_engine
        
        # Check cooldown again inside lock
        if (_rag_engine_init_attempted and 
            _rag_engine_last_attempt and 
            datetime.now() - _rag_engine_last_attempt < timedelta(seconds=_rag_engine_failure_cooldown)):
            return None
        
        # Attempt initialization
        if RAG_ENGINE_AVAILABLE:
            _rag_engine_init_attempted = True
            _rag_engine_last_attempt = datetime.now()
            
            try:
                _rag_engine = WMSEngine(mode=ProcessingMode.HYBRID)
                # Initialize with sample WMS data if not already done
                _rag_engine.initialize_sample_data()
                print("Advanced RAG engine initialized successfully")
                return _rag_engine
            except Exception as e:
                print(f"Failed to initialize RAG engine: {e}")
                _rag_engine = None
                # Keep _rag_engine_init_attempted and _rag_engine_last_attempt set for cooldown
                return None
        else:
            return None

def enhanced_rerank_logic(question: str, docs: list) -> str:
    """Advanced reranking logic from lesson 4 - using Gemini for intelligent reranking"""
    if not docs:
        return ""
    
    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError:
        # Fallback to simple concatenation if langchain not available
        return "\n\n".join([doc.page_content for doc in docs[:3]])
    
    # Reranking prompt from lesson 4
    rerank_prompt = ChatPromptTemplate.from_template("""
    You are a data validation expert. 
    Based on the user's question, select only the 3 most relevant text passages from the list below.
    Sort them by relevance in descending order.

    Question: {question}

    Document list:
    {docs}

    Only return the selected text passages, separated by '---'.
    """)
    
    # Convert docs to string for Gemini
    docs_str = "\n\n".join([f"Passage {i+1}: {doc.page_content}" for i, doc in enumerate(docs)])
    
    try:
        llm = get_chat_model(temperature=0.1)
        reranked_content = (rerank_prompt | llm | StrOutputParser()).invoke({
            "question": question, 
            "docs": docs_str
        })
        return reranked_content
    except Exception as e:
        print(f"Reranking failed: {e}")
        # Fallback to top 3 documents
        return "\n\n".join([doc.page_content for doc in docs[:3]])

def hybrid_search_with_reranking(question: str) -> dict[str, Any]:
    """Advanced hybrid search with reranking from lesson 4 and 5"""
    rag_engine = get_rag_engine()
    if not rag_engine:
        return {"answer": "Advanced RAG engine not available", "mode": "unavailable"}
    
    try:
        # Use hybrid mode (combines semantic + keyword search)
        result = rag_engine.process_query(question, ProcessingMode.HYBRID)
        
        if result.get("success", False):
            answer = result.get("response", "")
            return {
                "answer": answer,
                "mode": result.get("mode", "hybrid"),
                "success": True
            }
        else:
            return {
                "answer": "I couldn't find relevant information in the knowledge base.",
                "mode": "hybrid_failed",
                "success": False
            }
    except Exception as e:
        print(f"Hybrid search error: {e}")
        return {"answer": f"Search error: {str(e)}", "mode": "error", "success": False}

def handle_customer_chat_with_db(message: str, mode: str = "auto") -> dict[str, Any]:
    """Enhanced entry point: Try RAG first, fallback to SQL for database queries."""

    stripped = (message or "").strip()
    greetings = {"hi", "hello", "hey", "hola", "sus di", "xin chào", "xin chao"}
    if stripped.lower() in greetings:
        return {
            "sql": "",
            "rows": [],
            "answer": "Hi! I can help with WMS operations using both knowledge base and database queries. Ask me about products, inventory, documents, customers, or general WMS questions!",
        }

    # Mode-specific processing
    mode = mode.lower() if mode else "auto"
    
    # Force SQL mode
    if mode == "sql":
        if not is_relevant_query(stripped):
            return {
                "sql": "",
                "rows": [],
                "answer": "Xin loi, toi chi co the ho tro cac thong tin lien quan den kho hang va san pham. Ban vui long dat cau hoi khac nhe!",
                "mode": "sql_blocked"
            }
        if stripped.lower().startswith("sql:"):
            sql = stripped[4:].strip()
            sql = _validate_table_access(sql)
        else:
            sql = generate_sql_from_question(stripped)
        rows = execute_readonly_sql(sql)
        answer = summarize_rows(stripped, sql, rows)
        return {
            "sql": sql, 
            "rows": rows, 
            "answer": answer,
            "mode": "sql"
        }
    
    # Force RAG mode
    elif mode == "rag":
        rag_engine = get_rag_engine()
        if not rag_engine:
            return {
                "sql": "",
                "rows": [],
                "answer": "RAG engine not available. Please try 'auto' or 'sql' mode.",
                "mode": "rag_unavailable"
            }
        try:
            rag_result = hybrid_search_with_reranking(stripped)
            if rag_result.get("success", False):
                rag_answer = rag_result.get("answer", "")
                return {
                    "sql": "",
                    "rows": [],
                    "answer": rag_answer,
                    "mode": rag_result.get("mode", "rag"),
                    "engine_info": "Advanced RAG with reranking"
                }
            else:
                return {
                    "sql": "",
                    "rows": [],
                    "answer": "I couldn't find relevant information in the knowledge base.",
                    "mode": "rag_failed"
                }
        except Exception as e:
            print(f"RAG engine error: {e}")
            return {"answer": f"RAG error: {str(e)}", "mode": "rag_error"}
    
    # Force hybrid mode
    elif mode == "hybrid":
        rag_engine = get_rag_engine()
        if not rag_engine:
            return {
                "sql": "",
                "rows": [],
                "answer": "Hybrid mode requires RAG engine. Please try 'auto' or 'sql' mode.",
                "mode": "hybrid_unavailable"
            }
        try:
            rag_result = hybrid_search_with_reranking(stripped)
            if rag_result.get("success", False):
                rag_answer = rag_result.get("answer", "")
                # Hybrid mode: if RAG gives good answer, use it; otherwise fallback to SQL
                if len(rag_answer) > 50 and "couldn't find" not in rag_answer.lower():
                    return {
                        "sql": "",
                        "rows": [],
                        "answer": rag_answer,
                        "mode": rag_result.get("mode", "hybrid"),
                        "engine_info": "Advanced RAG with reranking"
                    }
                # Fallback to SQL for specific data queries
                elif is_relevant_query(stripped):
                    pass  # Continue to SQL processing
                else:
                    return {
                        "sql": "",
                        "rows": [],
                        "answer": rag_answer or "I can help with WMS operations. Could you please rephrase your question?",
                        "mode": "hybrid_fallback"
                    }
            else:
                # Fallback to SQL if RAG fails
                if is_relevant_query(stripped):
                    pass  # Continue to SQL processing
                else:
                    return {
                        "sql": "",
                        "rows": [],
                        "answer": "I couldn't find relevant information in the knowledge base.",
                        "mode": "hybrid_failed"
                    }
        except Exception as e:
            print(f"Hybrid search error: {e}")
            return {"answer": f"Hybrid error: {str(e)}", "mode": "hybrid_error"}
    
    # Auto mode (default): Try RAG first, fallback to SQL
    rag_engine = get_rag_engine()
    if rag_engine and not stripped.lower().startswith("sql:"):
        try:
            # Use hybrid search with reranking for better results
            rag_result = hybrid_search_with_reranking(stripped)
            
            if rag_result.get("success", False):
                rag_answer = rag_result.get("answer", "")
                
                # If RAG gives a good answer, return it
                if len(rag_answer) > 50 and "couldn't find" not in rag_answer.lower():
                    return {
                        "sql": "",
                        "rows": [],
                        "answer": rag_answer,
                        "mode": rag_result.get("mode", "hybrid"),
                        "engine_info": "Advanced RAG with reranking"
                    }
                # If RAG result is insufficient, try SQL for specific data queries
                elif is_relevant_query(stripped):
                    pass  # Continue to SQL processing
                else:
                    return {
                        "sql": "",
                        "rows": [],
                        "answer": rag_answer or "I can help with WMS operations. Could you please rephrase your question?",
                        "mode": "rag_fallback"
                    }
        except Exception as e:
            print(f"RAG engine error: {e}")
            # Fall back to SQL if RAG fails

    # SQL-based processing for database queries and fallback
    if not is_relevant_query(stripped):
        return {
            "sql": "",
            "rows": [],
            "answer": "Xin loi, toi chi co the ho tro cac thong tin lien quan den kho hang va san pham. Ban vui long dat cau hoi khac nhe!",
        }

    if stripped.lower().startswith("sql:"):
        sql = stripped[4:].strip()
        # Validate table access for direct SQL too
        sql = _validate_table_access(sql)
    else:
        sql = generate_sql_from_question(stripped)

    rows = execute_readonly_sql(sql)
    answer = summarize_rows(stripped, sql, rows)
    
    return {
        "sql": sql, 
        "rows": rows, 
        "answer": answer,
        "mode": "sql"
    }
