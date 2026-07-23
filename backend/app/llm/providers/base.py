"""
Abstract base class for LLM providers.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator

from app.llm.schemas import ProviderResponse
from app.core.config import Settings

class BaseProvider(ABC):
    """Abstract interface for interacting with LLM providers."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.model_name
        self.temperature = settings.temperature
        self.max_tokens = settings.max_tokens
        
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> ProviderResponse:
        """Generate a complete response."""
        pass
        
    @abstractmethod
    async def stream(self, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
        """Stream a response back token by token."""
        pass
