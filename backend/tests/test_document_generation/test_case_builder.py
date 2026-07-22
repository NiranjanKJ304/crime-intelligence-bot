"""
Tests for Case Summary Builder.
"""

from unittest.mock import MagicMock
from app.document_generation.case_builder import CaseSummaryBuilder
from app.document_generation.config import DocumentConfig

def test_case_summary_builder():
    mock_engine = MagicMock()
    
    # Mock the execute method to return one row
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_exec = mock_conn.execution_options.return_value.execute.return_value
    mock_exec.keys.return_value = [
        "CaseMasterID", "CrimeNo", "CaseNo", "CrimeRegistered Date", "DistrictName", "UnitName",
        "OfficerName", "OfficerKGID", "AccusedList", "VictimList", "ComplainantList", 
        "IncidentFromDate", "IncidentToDate", "BriefFacts", "cstype", "csdate", "ArrestCount", "CourtName"
    ]
    mock_exec.fetchall.return_value = [[
        1001, "CR/2024/001", None, "2024-01-15T00:00:00Z", "Bangalore Urban", "Whitefield PS",
        "Ramesh Kumar", "KGID123", "Suresh Patil (Age: 28)", "Meena Devi (Age: 42)", "Meena Devi",
        "2024-01-10T00:00:00Z", "2024-01-10T00:00:00Z", "Stolen laptop from cafe.",
        "Final", "2024-02-20T00:00:00Z", 1, "3rd ACMM Court"
    ]]

    config = DocumentConfig(
        clean_schema="clean",
        document_store_path="/tmp/store",
        batch_size=10,
        max_document_length=1000
    )
    
    builder = CaseSummaryBuilder(mock_engine, config)
    
    batch = builder.build_batch(offset=0, limit=10)
    assert len(batch) == 1
    
    doc = batch[0]
    assert doc.document_id == "case_summary_1001"
    assert doc.document_type == "case_summary"
    
    # Check text content
    text = doc.text
    assert "Crime No. CR/2024/001" in text
    assert "Whitefield PS" in text
    assert "Bangalore Urban" in text
    assert "15 January 2024" in text
    assert "Ramesh Kumar" in text
    assert "KGID123" in text
    assert "Suresh Patil" in text
    assert "Meena Devi" in text
    assert "Stolen laptop from cafe" in text
    assert "3rd ACMM Court" in text
    
    # Check metadata
    assert doc.metadata.entity_id == 1001
    assert doc.metadata.crime_number == "CR/2024/001"
    assert doc.metadata.district_name == "Bangalore Urban"
    assert doc.metadata.police_station_name == "Whitefield PS"
    assert doc.metadata.text_length == len(text)
    assert doc.metadata.section_count == 8
