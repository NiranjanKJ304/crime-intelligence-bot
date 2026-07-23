import pytest
from unittest.mock import MagicMock, patch
from app.retrieval.graph_search import GraphSearch
from app.retrieval.schemas import ExtractedEntities, GraphResult


@pytest.fixture
def mock_driver():
    with patch("app.retrieval.graph_search.get_neo4j_driver") as mock_get_driver:
        driver = MagicMock()
        mock_get_driver.return_value = driver
        yield driver


def test_search_by_district(mock_driver):
    # Setup mock session and run
    session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = session
    
    # Mock result for district query
    session.run.return_value = [
        {"District": "Mysuru", "Courts": ["Court 1", "Court 2"], "Units": ["Unit 1"]}
    ]
    
    gs = GraphSearch()
    entities = ExtractedEntities(district="Mysuru")
    results = gs.search_by_entities(entities)
    
    assert len(results) == 1
    assert results[0].node == "District: Mysuru"
    assert "2 Courts" in results[0].connected_to
    assert session.run.call_count == 1


def test_search_by_name(mock_driver):
    session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = session
    
    # Needs to return an iterator, we call run twice (Officer, Accused)
    def side_effect(query, **kwargs):
        if "Employee" in query:
            return [{"Name": "Inspector Raj", "CaseCount": 5}]
        elif "Accused" in query:
            return [{"Name": "Raj Kumar", "CaseCount": 2}]
        return []
        
    session.run.side_effect = side_effect
    
    gs = GraphSearch()
    entities = ExtractedEntities(names=["Raj"])
    results = gs.search_by_entities(entities)
    
    assert len(results) == 2
    assert any(r.node == "Officer: Inspector Raj" for r in results)
    assert any(r.node == "Accused: Raj Kumar" for r in results)


def test_find_connected_accused(mock_driver):
    session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = session
    
    session.run.return_value = [
        {"Accused": "John Doe", "OtherCase": "CASE-123"}
    ]
    
    gs = GraphSearch()
    results = gs.find_connected_accused("CASE-456")
    
    assert len(results) == 1
    assert results[0].node == "Accused: John Doe"
    assert results[0].connected_to == "Case: CASE-123"
