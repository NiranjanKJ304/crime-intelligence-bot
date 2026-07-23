"""
LLM Client facade.
"""

from typing import AsyncGenerator

from app.core.config import Settings
from app.llm.schemas import ProviderResponse
from app.llm.providers.base import BaseProvider
from app.llm.providers.groq_provider import GroqProvider

class LLMClient:
    """Facade for interacting with LLM providers."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = self._get_provider(settings)
        
    def _get_provider(self, settings: Settings) -> BaseProvider:
        """Factory method to get the configured provider."""
        provider_name = settings.llm_provider.lower()
        if provider_name == "groq":
            return GroqProvider(settings)
        # Future: elif provider_name == "ollama": return OllamaProvider(settings)
        else:
            # Default to Groq
            return GroqProvider(settings)
            
    async def generate(self, system_prompt: str, user_prompt: str) -> ProviderResponse:
        """Generate a full response from the LLM."""
        return await self.provider.generate(system_prompt, user_prompt)
        
    async def stream(self, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
        """Stream a response from the LLM."""
        async for chunk in self.provider.stream(system_prompt, user_prompt):
            yield chunk
