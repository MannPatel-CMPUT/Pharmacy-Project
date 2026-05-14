"""Unit tests for DDII text → severity (no DB)."""

from services.ddi_severity_classifier import (
    classify_ddii_interaction_severity,
    parse_explicit_ddii_severity,
)


def test_bleeding_escalation_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Concurrent use may increase bleeding risk."
        )
        == "major"
    )


def test_plain_pk_wording_moderate():
    assert (
        classify_ddii_interaction_severity(
            "Metformin may increase the serum concentration of cimetidine."
        )
        == "moderate"
    )


def test_decrease_cardiotoxic_not_major_from_toxicity_word():
    assert (
        classify_ddii_interaction_severity(
            "Paclitaxel may decrease the cardiotoxic activities of Digoxin."
        )
        == "moderate"
    )


def test_increase_cardiotoxic_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Cyclophosphamide may increase the cardiotoxic activities of Verteporfin."
        )
        == "major"
    )


def test_explicit_csv_cell_aliases():
    assert parse_explicit_ddii_severity("Major") == "major"
    assert parse_explicit_ddii_severity("low") == "minor"
    assert parse_explicit_ddii_severity("very high") == "contraindicated"
