"""
Tests for Query Processor.
"""

from app.retrieval.query_processor import QueryProcessor


def test_process_empty():
    processor = QueryProcessor()
    assert processor.process("") == ""
    assert processor.process("   ") == ""


def test_process_normalize():
    processor = QueryProcessor()
    assert processor.process(" Hello   World\n\nTest ") == "hello world test"
    

def test_process_abbreviations():
    processor = QueryProcessor()
    assert processor.process("Find FIR for this case") == "find first information report for this case"
    assert processor.process("the ipc section 302") == "the indian penal code section 302"
    assert processor.process("my crpc rights") == "my code of criminal procedure rights"
    
    # Check word boundaries (should not expand 'fire')
    assert processor.process("fire and fir") == "fire and first information report"


def test_unicode():
    processor = QueryProcessor()
    # NFKC normalizes full-width characters
    # Actually, it normalizes to 'fir' then expands to 'first information report'
    assert processor.process("ｆｉｒ") == "first information report"
