import pytest
from app.retrieval.entity_extractor import EntityExtractor
from app.retrieval.schemas import ExtractedEntities

@pytest.fixture
def extractor():
    return EntityExtractor()

def test_extract_empty(extractor):
    entities = extractor.extract("")
    assert isinstance(entities, ExtractedEntities)
    assert entities.district is None

def test_extract_district(extractor):
    entities = extractor.extract("Show cases in Mysuru")
    assert entities.district == "Mysuru"
    
    entities = extractor.extract("What happened in bangalore?")
    assert entities.district == "Bengaluru"

def test_extract_crime_type(extractor):
    entities = extractor.extract("Find murder cases")
    assert entities.crime_type == "murder"
    
    entities = extractor.extract("Show theft in udupi")
    assert entities.crime_type == "theft"
    assert entities.district == "Udupi"

def test_extract_year(extractor):
    entities = extractor.extract("Robbery in 2023")
    assert entities.year == 2023

def test_extract_case_numbers(extractor):
    entities = extractor.extract("Details for cr/123/2023 and fir no 456")
    assert "cr/123/2023" in entities.case_numbers
    assert "fir no 456" in entities.case_numbers

def test_extract_ipc_sections(extractor):
    entities = extractor.extract("Cases under ipc 302 and sec 420")
    assert "302" in entities.ipc_sections
    assert "420" in entities.ipc_sections

def test_extract_names(extractor):
    entities = extractor.extract("Accused ramesh kumar was arrested by inspector sharma")
    assert "Ramesh Kumar" in entities.names or "Ramesh" in entities.names
    assert "Sharma" in entities.names

def test_extract_document_type(extractor):
    entities = extractor.extract("Show officer profiles for bengaluru")
    assert entities.document_type == "officer_profile"
    assert entities.district == "Bengaluru"
