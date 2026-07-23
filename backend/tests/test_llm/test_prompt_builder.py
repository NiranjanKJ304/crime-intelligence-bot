"""
Tests for Prompt Builder.
"""

from app.llm.prompt_builder import PromptBuilder

def test_prompt_builder():
    context = "Case 123 involves theft."
    doc_ids = ["case_123"]
    query = "What does case 123 involve?"
    
    sys_prompt, user_prompt = PromptBuilder.build(query, context, doc_ids)
    
    assert "Never fabricate facts" in sys_prompt
    assert "Karnataka Police" in sys_prompt
    
    assert "case_123" in user_prompt
    assert query in user_prompt
    assert context in user_prompt
