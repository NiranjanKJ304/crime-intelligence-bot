"""
Tests for the Intent Detector.
"""

import pytest
from app.services.tools.intent_detector import IntentDetector


class TestIntentDetector:
    """Test suite for intent detection patterns."""

    def test_case_lookup_by_id(self):
        result = IntentDetector.detect("Show case 202300001")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "case_by_number"
        assert result.identifiers.get("case_number") == 202300001

    def test_case_lookup_with_number_prefix(self):
        result = IntentDetector.detect("case number 15")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "case_by_number"
        assert result.identifiers.get("case_number") == 15

    def test_case_lookup_with_hash(self):
        result = IntentDetector.detect("case #42")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "case_by_number"
        assert result.identifiers.get("case_number") == 42

    def test_officer_lookup(self):
        result = IntentDetector.detect("Officer 102")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "officer"
        assert result.identifiers.get("officer_id") == 102

    def test_officer_lookup_with_id(self):
        result = IntentDetector.detect("employee id 55")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "officer"
        assert result.identifiers.get("officer_id") == 55

    def test_victim_lookup(self):
        result = IntentDetector.detect("Victim 14")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "victim"
        assert result.identifiers.get("victim_id") == 14

    def test_accused_lookup(self):
        result = IntentDetector.detect("accused 15")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "accused"
        assert result.identifiers.get("accused_id") == 15

    def test_suspect_is_accused(self):
        result = IntentDetector.detect("suspect 99")
        # suspect without case context is semantic search or default
        assert result.intent in ("identifier_lookup", "semantic_search")

    def test_crime_number_lookup(self):
        result = IntentDetector.detect("crime number CR/2023/001")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "case_by_crime"

    def test_fir_lookup(self):
        result = IntentDetector.detect("FIR number 12345")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "case_by_crime"

    def test_relationship_keyword_who_arrested(self):
        result = IntentDetector.detect("Who arrested accused 15?")
        # Has "arrested by" / "who arrested", so graph query or reasoning
        assert result.intent in ("graph_query", "reasoning")

    def test_relationship_keyword_co_accused(self):
        result = IntentDetector.detect("Find co-accused in these cases")
        assert result.intent in ("graph_query", "reasoning")

    def test_relationship_keyword_network(self):
        result = IntentDetector.detect("Show the network of related crimes")
        assert result.intent in ("graph_query", "reasoning")

    def test_semantic_search_default(self):
        result = IntentDetector.detect("Find robbery cases involving machetes")
        assert result.intent == "semantic_search"

    def test_semantic_search_descriptive(self):
        result = IntentDetector.detect("domestic violence cases in Bangalore")
        assert result.intent == "semantic_search"

    def test_confidence_exact_match(self):
        result = IntentDetector.detect("case 1")
        assert result.confidence >= 0.8

    def test_confidence_semantic(self):
        result = IntentDetector.detect("theft patterns")
        assert result.confidence <= 0.6


class TestIdentifierKinds:
    """CaseNo, CrimeNo, CaseMasterID and EmployeeID are distinct identifiers."""

    def test_caseno_compact_spelling(self):
        result = IntentDetector.detect("Find CaseNo 202300001")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "case_by_number"
        assert result.identifiers == {"case_number": 202300001}

    def test_case_id_means_case_master_id(self):
        result = IntentDetector.detect("case id 1")
        assert result.sub_intent == "case_by_id"
        assert result.identifiers == {"case_id": 1}

    def test_case_master_id(self):
        result = IntentDetector.detect("CaseMasterID 1")
        assert result.identifiers == {"case_id": 1}

    def test_crime_no_is_crime_number_not_case_number(self):
        result = IntentDetector.detect("crime no 100170200202300001")
        assert result.sub_intent == "case_by_crime"
        assert result.identifiers == {"crime_number": 100170200202300001}

    def test_officer_employee_id_phrasing(self):
        result = IntentDetector.detect("Find officer EmployeeID 5313")
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "officer"
        assert result.identifiers == {"officer_id": 5313}

    def test_investigating_officer_for_caseno(self):
        result = IntentDetector.detect("Who is the investigating officer for CaseNo 202300001?")
        assert result.intent == "factual_query"
        assert result.sub_intent == "officer_for_case"
        assert result.identifiers == {"case_number": 202300001}

    def test_that_case_has_no_identifier(self):
        result = IntentDetector.detect("Who is the investigating officer for that case?")
        assert result.intent == "factual_query"
        assert result.sub_intent == "officer_for_case"
        assert result.identifiers == {}

    def test_identifiers_are_typed(self):
        assert isinstance(IntentDetector.detect("Show case 202300001").identifiers["case_number"], int)
        assert isinstance(IntentDetector.detect("FIR number CR/2023/001").identifiers["crime_number"], str)


class TestAccusedByName:
    @pytest.mark.parametrize("query", ["Fiyaz Saran", "accused Fiyaz Saran", "Find accused named Fiyaz Saran"])
    def test_name_lookup(self, query):
        result = IntentDetector.detect(query)
        assert result.intent == "identifier_lookup"
        assert result.sub_intent == "accused_by_name"
        assert result.identifiers == {"accused_name": "Fiyaz Saran"}

    def test_accused_id_still_wins_over_name(self):
        result = IntentDetector.detect("accused 15")
        assert result.sub_intent == "accused"

    def test_descriptive_accused_query_is_not_a_name(self):
        result = IntentDetector.detect("accused persons in Bangalore")
        assert result.sub_intent != "accused_by_name"

    def test_co_accused_query_is_graph(self):
        result = IntentDetector.detect("Find co-accused in these cases")
        assert result.intent in ("graph_query", "reasoning")
