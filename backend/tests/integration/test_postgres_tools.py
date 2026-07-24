"""
Integration tests for PostgreSQL tool functions using ColumnMapper.

These tests run against the actual Docker PostgreSQL database to ensure
the dynamic column mappings correctly resolve logical IDs to physical columns.
"""

import pytest

from app.core.config import get_settings
from app.services.tools.mapper import ColumnMapper
from app.services.tools.postgres_tools import (
    get_case_by_number,
    get_case_by_crime_number,
    get_officer,
    get_victim,
    get_accused,
)


@pytest.fixture(scope="module", autouse=True)
def setup_mapper():
    """Ensure the column mapper is initialized before tests run."""
    settings = get_settings()
    # Ensure we use the clean schema configured for the environment
    mapper = ColumnMapper.get_instance()
    # Try initializing the mapper; this requires the DB to be up and populated.
    try:
        mapper.initialize()
    except Exception as e:
        pytest.skip(f"Database not available or clean schema not populated: {e}")
    yield


def test_get_case_by_number():
    """Test fetching a case by its Case Number."""
    # We use a known synthetic Case Number from the data profile (e.g. 202300001)
    case_number = "202300001"
    result = get_case_by_number(case_number)
    
    # Assert result is found
    assert result is not None
    assert isinstance(result, dict)
    
    # Assert enriched lists are attached
    assert "accused" in result
    assert "victims" in result
    assert "arrests" in result
    assert "chargesheets" in result


def test_get_case_by_crime_number():
    """Test fetching a case by its Crime Number (FIR No)."""
    # We use a known synthetic Crime Number (e.g. 100170200202300001)
    crime_number = "100170200202300001"
    result = get_case_by_crime_number(crime_number)
    
    assert result is not None
    assert isinstance(result, dict)
    
    # Ensure they don't share identical lookup behaviors (a case_no shouldn't return a crime_no search)
    assert get_case_by_crime_number("202300001") is None
    assert get_case_by_number("100170200202300001") is None


def test_get_officer():
    """Test fetching an officer by EmployeeID."""
    # Assuming Officer IDs are in the 5001-5500 range
    officer_id = 5001
    result = get_officer(officer_id)
    assert result is not None
    assert isinstance(result, dict)


def test_get_victim():
    """Test fetching a victim by VictimMasterID."""
    victim_id = 1
    result = get_victim(victim_id)
    assert result is not None
    assert isinstance(result, dict)


def test_get_accused():
    """Test fetching an accused by AccusedMasterID."""
    accused_id = 1
    result = get_accused(accused_id)
    assert result is not None
    assert isinstance(result, dict)
