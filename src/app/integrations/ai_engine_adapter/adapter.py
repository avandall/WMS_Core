"""
AI Engine Adapter - Converts data between application and AI engine
This is the single entry point for all AI operations in the system
"""

from typing import Any, Dict, List, Optional
from .interface import IAIEngine


class AIEngineAdapter(IAIEngine):
    """Adapter for AI Engine operations"""
    
    def __init__(self, ai_engine):
        """Initialize adapter with AI engine implementation"""
        self._ai_engine = ai_engine
    
    async def generate_sql_query(self, natural_language: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate SQL query from natural language"""
        # Convert application format to AI engine format
        return await self._ai_engine.generate_sql_query(natural_language, context)
    
    async def analyze_data(self, data: Any, analysis_type: str = "general") -> Dict[str, Any]:
        """Analyze data using AI"""
        # Convert application data to AI engine format
        return await self._ai_engine.analyze_data(data, analysis_type)
    
    async def get_recommendations(self, entity_type: str, entity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get AI-powered recommendations"""
        # Convert application entity data to AI engine format
        return await self._ai_engine.get_recommendations(entity_type, entity_data)
    
    async def process_document(self, document_content: str, document_type: str = "general") -> Dict[str, Any]:
        """Process document using AI"""
        # Convert document format to AI engine format
        return await self._ai_engine.process_document(document_content, document_type)
    
    async def validate_business_rules(self, entity_data: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
        """Validate business rules using AI"""
        # Convert business rule validation to AI engine format
        return await self._ai_engine.validate_business_rules(entity_data, entity_type)


def create_ai_engine_adapter() -> IAIEngine:
    """Factory function to create AI engine adapter"""
    # Import here to avoid circular dependencies
    from app.integrations.ai.ai import AIEngine
    from app.integrations.ai.chains import SQLGenerationChain, DataAnalysisChain
    
    # Create AI engine implementation
    ai_engine = AIEngine(
        sql_chain=SQLGenerationChain(),
        analysis_chain=DataAnalysisChain()
    )
    
    # Return adapter wrapping the AI engine
    return AIEngineAdapter(ai_engine)
