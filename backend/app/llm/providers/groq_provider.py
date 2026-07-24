"""
Groq LLM Provider Implementation.
"""

import logging
from typing import AsyncGenerator
from groq import AsyncGroq, APIConnectionError, RateLimitError, APIError

from app.core.config import Settings
from app.llm.schemas import ProviderResponse
from app.llm.providers.base import BaseProvider
from app.llm.exceptions import LLMConnectionError, LLMRateLimitError, LLMError

logger = logging.getLogger(__name__)

class GroqProvider(BaseProvider):
    """Implementation for Groq Cloud API."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        if not settings.groq_api_key:
            logger.warning("GROQ_API_KEY is not set. GroqProvider will fail on generation.")
            
        self.client = AsyncGroq(
            api_key=settings.groq_api_key,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries
        )
        
    async def generate(self, system_prompt: str, user_prompt: str) -> ProviderResponse:
        """Call Groq API synchronously-like for a full response."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False
            )
            
            return ProviderResponse(
                content=response.choices[0].message.content or "",
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0
            )
            
        except APIConnectionError as e:
            logger.error(f"Groq connection error: {e}")
            raise LLMConnectionError(f"Failed to connect to Groq: {e}")
        except RateLimitError as e:
            logger.error(f"Groq rate limit error: {e}")
            raise LLMRateLimitError(f"Rate limited by Groq: {e}")
        except APIError as e:
            logger.error(f"Groq API error: {e}")
            raise LLMError(f"Groq API returned an error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in Groq generation")
            raise LLMError(f"Unexpected error: {e}")

    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
    ):
        """
        Call Groq API with tool/function definitions.
        Returns the raw API response object so the caller can inspect tool_calls.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
            )
            return response

        except APIConnectionError as e:
            logger.error(f"Groq connection error (tools): {e}")
            raise LLMConnectionError(f"Failed to connect to Groq: {e}")
        except RateLimitError as e:
            logger.error(f"Groq rate limit error (tools): {e}")
            raise LLMRateLimitError(f"Rate limited by Groq: {e}")
        except APIError as e:
            logger.error(f"Groq API error (tools): {e}")
            raise LLMError(f"Groq API returned an error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in Groq tool-calling generation")
            raise LLMError(f"Unexpected error: {e}")
            
    async def stream(self, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
        """Stream chunks from Groq API."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except APIConnectionError as e:
            logger.error(f"Groq connection error during stream: {e}")
            raise LLMConnectionError(f"Failed to connect to Groq: {e}")
        except RateLimitError as e:
            logger.error(f"Groq rate limit error during stream: {e}")
            raise LLMRateLimitError(f"Rate limited by Groq: {e}")
        except APIError as e:
            logger.error(f"Groq API error during stream: {e}")
            raise LLMError(f"Groq API returned an error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in Groq stream")
            raise LLMError(f"Unexpected error: {e}")
