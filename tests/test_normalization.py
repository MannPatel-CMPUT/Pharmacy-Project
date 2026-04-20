from services.normalization_service import normalize_token, split_medications


def test_normalize_token_lowercases_and_strips_symbols():
    assert normalize_token("  Warfarin!! ") == "warfarin"


def test_split_medications_handles_commas_semicolons_and_newlines():
    meds = split_medications("Warfarin, Aspirin; Lisinopril\nAtorvastatin")
    assert meds == ["warfarin", "aspirin", "lisinopril", "atorvastatin"]
