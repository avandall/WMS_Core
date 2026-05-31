"""
WMS AI Engine Integration - Add AI endpoints to existing dashboard backend
"""
import os
import sys
import json
import asyncio
from datetime import datetime
from pathlib import Path

# Add parent directory to path for AI engine imports
sys.path.append(str(Path(__file__).parent.parent / 'src' / 'ai_engine'))

from ai_engine import WMSEngine, ProcessingMode

# Global AI engine instance
ai_engine = None

def initialize_ai_engine():
    """Initialize the AI engine"""
    global ai_engine
    try:
        ai_engine = WMSEngine(mode=ProcessingMode.HYBRID)
        ai_engine.initialize_sample_data()
        return True
    except Exception as e:
        print(f"Error initializing AI engine: {e}")
        return False

def get_ai_engine():
    """Get the AI engine instance"""
    global ai_engine
    if ai_engine is None:
        initialize_ai_engine()
    return ai_engine

# AI Engine API Handlers
async def handle_ai_query(data):
    """Handle AI query requests"""
    try:
        engine = get_ai_engine()
        if not engine:
            return {"success": False, "detail": "AI engine not initialized"}
        
        question = data.get('question', '')
        mode_str = data.get('mode', 'hybrid')
        
        if not question:
            return {"success": False, "detail": "Question is required"}
        
        # Convert mode string to enum
        mode_map = {
            "rag": ProcessingMode.RAG,
            "agent": ProcessingMode.AGENT,
            "hybrid": ProcessingMode.HYBRID
        }
        processing_mode = mode_map.get(mode_str.lower(), ProcessingMode.HYBRID)
        
        start_time = datetime.now()
        result = await engine.process_query(question, mode=processing_mode)
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return {
            "success": True,
            "response": result.get("response", ""),
            "mode": result.get("mode", "unknown"),
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"success": False, "detail": str(e)}

def handle_ai_document_upload(data):
    """Handle document upload requests"""
    try:
        engine = get_ai_engine()
        if not engine:
            return {"success": False, "detail": "AI engine not initialized"}
        
        documents = data if isinstance(data, list) else [data]
        texts = []
        metadatas = []
        
        for doc in documents:
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            
            if content:
                texts.append(content)
                metadatas.append(metadata)
        
        if not texts:
            return {"success": False, "detail": "No valid documents provided"}
        
        success = engine.add_documents(texts, metadatas)
        
        return {
            "success": success,
            "documents_added": len(texts),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"success": False, "detail": str(e)}

def handle_ai_init_sample():
    """Handle sample data initialization"""
    try:
        engine = get_ai_engine()
        if not engine:
            return {"success": False, "detail": "AI engine not initialized"}
        
        success = engine.initialize_sample_data()
        
        return {
            "success": success,
            "message": "Sample WMS data initialized successfully" if success else "Failed to initialize sample data",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"success": False, "detail": str(e)}

def handle_ai_engine_info():
    """Handle engine info requests"""
    try:
        engine = get_ai_engine()
        if not engine:
            return {"success": False, "detail": "AI engine not initialized"}
        
        return engine.get_engine_info()
        
    except Exception as e:
        return {"success": False, "detail": str(e)}

def handle_ai_document_stats():
    """Handle document statistics requests"""
    try:
        engine = get_ai_engine()
        if not engine:
            return {"success": False, "detail": "AI engine not initialized"}
        
        vectorstore = engine.retriever.vectorstore
        collection_info = vectorstore._collection.count()
        
        return {
            "total_documents": collection_info,
            "vector_db_path": engine.retriever.vectorstore.persist_directory,
            "embedding_model": engine.retriever.embeddings.model_name,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"success": False, "detail": str(e)}

# Flask/FastAPI Integration Functions
def add_ai_routes_to_flask(app):
    """Add AI routes to existing Flask app"""
    from flask import request, jsonify
    
    @app.route('/api/ai/query', methods=['POST'])
    def api_ai_query():
        try:
            data = request.get_json()
            result = handle_ai_query(data)
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "detail": str(e)}), 500
    
    @app.route('/api/ai/documents/upload', methods=['POST'])
    def api_ai_documents_upload():
        try:
            data = request.get_json()
            result = handle_ai_document_upload(data)
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "detail": str(e)}), 500
    
    @app.route('/api/ai/documents/init-sample', methods=['POST'])
    def api_ai_init_sample():
        try:
            result = handle_ai_init_sample()
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "detail": str(e)}), 500
    
    @app.route('/api/ai/engine/info', methods=['GET'])
    def api_ai_engine_info():
        try:
            result = handle_ai_engine_info()
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "detail": str(e)}), 500
    
    @app.route('/api/ai/documents/stats', methods=['GET'])
    def api_ai_document_stats():
        try:
            result = handle_ai_document_stats()
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "detail": str(e)}), 500

def add_ai_routes_to_fastapi(app):
    """Add AI routes to existing FastAPI app"""
    from fastapi import HTTPException
    from pydantic import BaseModel
    from typing import List, Optional, Dict, Any
    
    class QueryRequest(BaseModel):
        question: str
        mode: Optional[str] = "hybrid"
    
    class DocumentUpload(BaseModel):
        content: str
        metadata: Optional[Dict[str, Any]] = {}
    
    @app.post("/api/ai/query")
    async def api_ai_query(request: QueryRequest):
        try:
            result = await handle_ai_query(request.dict())
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/ai/documents/upload")
    async def api_ai_documents_upload(documents: List[DocumentUpload]):
        try:
            result = handle_ai_document_upload([doc.dict() for doc in documents])
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/ai/documents/init-sample")
    async def api_ai_init_sample():
        try:
            result = handle_ai_init_sample()
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/ai/engine/info")
    async def api_ai_engine_info():
        try:
            result = handle_ai_engine_info()
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/ai/documents/stats")
    async def api_ai_document_stats():
        try:
            result = handle_ai_document_stats()
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Example usage with Flask
if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    
    # Add AI routes to existing Flask app
    add_ai_routes_to_flask(app)
    
    # Initialize AI engine
    initialize_ai_engine()
    
    app.run(debug=True, port=8000)
