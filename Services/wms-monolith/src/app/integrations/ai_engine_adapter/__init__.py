"""
AI Engine Adapter Module
Single point of contact for all AI operations in the system
"""

from .interface import IAIEngine
from .adapter import AIEngineAdapter, create_ai_engine_adapter

__all__ = ['IAIEngine', 'AIEngineAdapter', 'create_ai_engine_adapter']
