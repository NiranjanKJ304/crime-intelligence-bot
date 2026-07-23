"""
Tests for LLM Client and Groq Provider.
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.llm.client import LLMClient
from app.llm.providers.groq_provider import GroqProvider

@pytest.fixture
def settings():
    class MockSettings:
        llm_provider = "groq"
        groq_api_key = "test_key"
        model_name = "test_model"
        temperature = 0.0
        max_tokens = 100
        llm_timeout = 10
        llm_max_retries = 1
    return MockSettings()

def test_client_factory(settings):
    client = LLMClient(settings)
    assert isinstance(client.provider, GroqProvider)

@pytest.mark.asyncio
async def test_groq_provider_generate(settings):
    provider = GroqProvider(settings)
    
    with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        # Mock the Groq response
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 10
        mock_create.return_value = mock_response
        
        resp = await provider.generate("sys", "user")
        
        assert resp.content == "Test response"
        assert resp.total_tokens == 10
        mock_create.assert_called_once()
