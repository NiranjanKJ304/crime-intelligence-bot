"""
Tests for the Intent Detector.
"""

import pytest
from app.services.tools.intent_detector import IntentDetector


class TestIntentDetector:
    """Test suite for intent detection patterns."""

    def test_case_lookup_by_id(self):
        result = IntentDetector.detect("Show case 202300001")
        assert result.intent == "case_lookup"
        assert result.identifiers.get("case_id") == 202300001

    def test_case_lookup_with_number_prefix(self):
        result = IntentDetector.detect("case number 15")
        assert result.intent == "case_lookup"
        assert result.identifiers.get("case_id") == 15

    def test_case_lookup_with_hash(self):
        result = IntentDetector.detect("case #42")
        assert result.intent == "case_lookup"
        assert result.identifiers.get("case_id") == 42

    def test_officer_lookup(self):
        result = IntentDetector.detect("Officer 102")
        assert result.intent == "officer_lookup"
        assert result.identifiers.get("officer_id") == 102

    def test_officer_lookup_with_id(self):
        result = IntentDetector.detect("employee id 55")
        assert result.intent == "officer_lookup"
        assert result.identifiers.get("officer_id") == 55

    def test_victim_lookup(self):
        result = IntentDetector.detect("Victim 14")
        assert result.intent == "victim_lookup"
        assert result.identifiers.get("victim_id") == 14

    def test_accused_lookup(self):
        result = IntentDetector.detect("accused 15")
        assert result.intent == "accused_lookup"
        assert result.identifiers.get("accused_id") == 15

    def test_suspect_is_accused(self):
        result = IntentDetector.detect("suspect 99")
        assert result.intent == "accused_lookup"
        assert result.identifiers.get("accused_id") == 99

    def test_complainant_lookup(self):
        result = IntentDetector.detect("complainant 7")
        assert result.intent == "complainant_lookup"
        assert result.identifiers.get("complainant_id") == 7

    def test_crime_number_lookup(self):
        result = IntentDetector.detect("crime number CR/2023/001")
        assert result.intent == "crime_number_lookup"

    def test_fir_lookup(self):
        result = IntentDetector.detect("FIR number 12345")
        assert result.intent == "crime_number_lookup"

    def test_relationship_keyword_who_arrested(self):
        result = IntentDetector.detect("Who arrested accused 15?")
        # Should match accused_lookup first (more specific pattern)
        assert result.intent == "accused_lookup"

    def test_relationship_keyword_co_accused(self):
        result = IntentDetector.detect("Find co-accused in these cases")
        assert result.intent == "relationship_query"

    def test_relationship_keyword_network(self):
        result = IntentDetector.detect("Show the network of related crimes")
        assert result.intent == "relationship_query"

    def test_semantic_search_default(self):
        result = IntentDetector.detect("Find robbery cases involving machetes")
        assert result.intent == "semantic_search"

    def test_semantic_search_descriptive(self):
        result = IntentDetector.detect("domestic violence cases in Bangalore")
        assert result.intent == "semantic_search"

    def test_statistics_query(self):
        result = IntentDetector.detect("How many cases were filed?")
        assert result.intent == "statistics_query"

    def test_confidence_exact_match(self):
        result = IntentDetector.detect("case 1")
        assert result.confidence >= 0.8

    def test_confidence_semantic(self):
        result = IntentDetector.detect("theft patterns")
        assert result.confidence <= 0.6
