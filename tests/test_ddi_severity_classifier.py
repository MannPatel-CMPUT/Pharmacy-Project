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


def test_decrease_cardiotoxic_is_protective_minor():
    """A combination that *reduces* the second drug's adverse activity is low risk."""
    assert (
        classify_ddii_interaction_severity(
            "Paclitaxel may decrease the cardiotoxic activities of Digoxin."
        )
        == "minor"
    )


def test_increase_cardiotoxic_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Cyclophosphamide may increase the cardiotoxic activities of Verteporfin."
        )
        == "major"
    )


def test_increase_qt_prolonging_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Amiodarone may increase the QTc-prolonging activities of Citalopram."
        )
        == "major"
    )


def test_increase_serotonergic_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Sertraline may increase the serotonergic activities of Tramadol."
        )
        == "major"
    )


def test_increase_anticoagulant_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Aspirin may increase the anticoagulant activities of Warfarin."
        )
        == "major"
    )


def test_increase_hypoglycemic_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Propranolol may increase the hypoglycemic activities of Insulin."
        )
        == "major"
    )


def test_increase_hypokalemic_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Furosemide may increase the hypokalemic activities of Hydrochlorothiazide."
        )
        == "major"
    )


def test_increase_av_block_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Diltiazem may increase the atrioventricular blocking (AV block) activities of Digoxin."
        )
        == "major"
    )


def test_increase_arrhythmogenic_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Quinidine may increase the arrhythmogenic activities of Sotalol."
        )
        == "major"
    )


def test_increase_cns_depressant_is_major():
    assert (
        classify_ddii_interaction_severity(
            "Alprazolam may increase the central nervous system depressant (CNS depressant) "
            "activities of Hydrocodone."
        )
        == "major"
    )


def test_increase_photosensitizing_is_moderate():
    assert (
        classify_ddii_interaction_severity(
            "Trioxsalen may increase the photosensitizing activities of Verteporfin."
        )
        == "moderate"
    )


def test_metabolism_decrease_is_moderate():
    assert (
        classify_ddii_interaction_severity(
            "The metabolism of Diazepam can be decreased when combined with Cimetidine."
        )
        == "moderate"
    )


def test_decrease_sedative_is_minor_protective():
    assert (
        classify_ddii_interaction_severity(
            "Caffeine may decrease the sedative activities of Diphenhydramine."
        )
        == "minor"
    )


def test_no_clinically_significant_is_minor():
    assert (
        classify_ddii_interaction_severity(
            "Co-administration has no clinically significant effect on exposure."
        )
        == "minor"
    )


def test_contraindicated_wording():
    assert (
        classify_ddii_interaction_severity(
            "This drug is contraindicated with MAO inhibitors."
        )
        == "contraindicated"
    )


def test_explicit_csv_cell_aliases():
    assert parse_explicit_ddii_severity("Major") == "major"
    assert parse_explicit_ddii_severity("low") == "minor"
    assert parse_explicit_ddii_severity("very high") == "contraindicated"
