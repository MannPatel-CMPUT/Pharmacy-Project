from services.normalization_service import expanded_terms_for_matching, normalize_token, split_medications


def test_normalize_token_lowercases_and_strips_symbols():
    assert normalize_token("  Warfarin!! ") == "warfarin"


def test_split_medications_handles_commas_semicolons_and_newlines():
    meds = split_medications("Warfarin, Aspirin; Lisinopril\nAtorvastatin")
    assert meds == ["warfarin", "aspirin", "lisinopril", "atorvastatin"]


def test_expanded_terms_for_matching_includes_class_and_member_names():
    assert "nsaids" in expanded_terms_for_matching("ibuprofen")
    assert "ibuprofen" in expanded_terms_for_matching("NSAIDs")
