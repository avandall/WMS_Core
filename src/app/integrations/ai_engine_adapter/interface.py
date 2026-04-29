"""
AI Engine Interface - Single point of contact for AI functionality
This provides a clean abstraction layer between the application and AI implementation
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IAIEngine(ABC):
    """Interface for AI Engine operations"""
    
    @abstractmethod
    async def generate_sql_query(self, natural_language: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate SQL query from natural language"""
        pass
    
    @abstractmethod
    async def analyze_data(self, data: Any, analysis_type: str = "general") -> Dict[str, Any]:
        """Analyze data using AI"""
        pass
    
    @abstractmethod
    async def get_recommendations(self, entity_type: str, entity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get AI-powered recommendations"""
        pass
    
    @abstractmethod
    async def process_document(self, document_content: str, document_type: str = "general") -> Dict[str, Any]:
        """Process document using AI"""
        pass
    
    @abstractmethod
    async def validate_business_rules(self, entity_data: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
        """Validate business rules using AI"""
        pass
