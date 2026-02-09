"""
Drug Interaction Checking Service
Provides basic drug interaction checking functionality
"""
from typing import List, Dict
import re

# Common drug interaction database (simplified for demo)
# In production, this would connect to a comprehensive drug database API
DRUG_INTERACTIONS = {
    # Warfarin interactions
    "warfarin": {
        "aspirin": "Major: Increased bleeding risk. Monitor INR closely.",
        "ibuprofen": "Major: Increased bleeding risk. Avoid concurrent use.",
        "naproxen": "Major: Increased bleeding risk. Monitor for bleeding.",
        "acetaminophen": "Moderate: May enhance anticoagulant effect.",
    },
    # ACE Inhibitors interactions
    "lisinopril": {
        "potassium": "Moderate: Risk of hyperkalemia. Monitor potassium levels.",
        "spironolactone": "Major: Risk of hyperkalemia. Monitor closely.",
    },
    # Statins interactions
    "atorvastatin": {
        "erythromycin": "Major: Increased risk of myopathy. Monitor for muscle pain.",
        "grapefruit": "Moderate: May increase statin levels. Limit grapefruit intake.",
    },
    # Antibiotics
    "amoxicillin": {
        "warfarin": "Moderate: May enhance anticoagulant effect.",
    },
    # Common OTC interactions
    "aspirin": {
        "ibuprofen": "Moderate: Increased GI bleeding risk.",
        "warfarin": "Major: Increased bleeding risk.",
    },
}

# Drug categories for broader checking
DRUG_CATEGORIES = {
    "nsaids": ["ibuprofen", "naproxen", "aspirin", "diclofenac"],
    "anticoagulants": ["warfarin", "apixaban", "rivaroxaban"],
    "ace_inhibitors": ["lisinopril", "enalapril", "ramipril"],
    "statins": ["atorvastatin", "simvastatin", "rosuvastatin"],
}


def normalize_drug_name(drug: str) -> str:
    """Normalize drug name for comparison"""
    return drug.lower().strip()


def check_drug_interactions(new_medications: str, current_medications: str = None) -> List[Dict]:
    """
    Check for drug interactions between new medications and current medications
    
    Returns list of interaction warnings
    """
    interactions = []
    
    # Parse medications (split by comma, semicolon, or newline)
    new_meds = [normalize_drug_name(m) for m in re.split(r'[,;\n]', new_medications) if m.strip()]
    
    if not current_medications:
        # Check interactions within new medications themselves
        for i, med1 in enumerate(new_meds):
            for med2 in new_meds[i+1:]:
                interaction = find_interaction(med1, med2)
                if interaction:
                    interactions.append({
                        "drug1": med1,
                        "drug2": med2,
                        "severity": interaction["severity"],
                        "description": interaction["description"]
                    })
        return interactions
    
    # Parse current medications
    current_meds = [normalize_drug_name(m) for m in re.split(r'[,;\n]', current_medications) if m.strip()]
    
    # Check interactions between new and current medications
    for new_med in new_meds:
        for current_med in current_meds:
            interaction = find_interaction(new_med, current_med)
            if interaction:
                interactions.append({
                    "drug1": new_med,
                    "drug2": current_med,
                    "severity": interaction["severity"],
                    "description": interaction["description"]
                })
    
    return interactions


def find_interaction(drug1: str, drug2: str) -> Dict:
    """Find interaction between two drugs"""
    drug1_norm = normalize_drug_name(drug1)
    drug2_norm = normalize_drug_name(drug2)
    
    # Direct lookup
    if drug1_norm in DRUG_INTERACTIONS:
        if drug2_norm in DRUG_INTERACTIONS[drug1_norm]:
            description = DRUG_INTERACTIONS[drug1_norm][drug2_norm]
            severity = "Major" if "Major:" in description else "Moderate"
            return {"severity": severity, "description": description}
    
    # Reverse lookup
    if drug2_norm in DRUG_INTERACTIONS:
        if drug1_norm in DRUG_INTERACTIONS[drug2_norm]:
            description = DRUG_INTERACTIONS[drug2_norm][drug1_norm]
            severity = "Major" if "Major:" in description else "Moderate"
            return {"severity": severity, "description": description}
    
    # Category-based checking
    for category, drugs in DRUG_CATEGORIES.items():
        if drug1_norm in drugs and drug2_norm in drugs and drug1_norm != drug2_norm:
            if category == "nsaids":
                return {
                    "severity": "Moderate",
                    "description": "Moderate: Multiple NSAIDs may increase GI bleeding risk."
                }
    
    return None


def generate_counseling_points(medications: str, interactions: List[Dict] = None) -> str:
    """Generate counseling points based on medications and interactions"""
    points = []
    
    meds_lower = medications.lower()
    
    # General counseling points
    if "warfarin" in meds_lower:
        points.append("• Take at the same time each day")
        points.append("• Avoid sudden changes in diet (especially vitamin K-rich foods)")
        points.append("• Report any unusual bleeding or bruising immediately")
        points.append("• Regular INR monitoring required")
    
    if "antibiotic" in meds_lower or any(ab in meds_lower for ab in ["amoxicillin", "azithromycin", "penicillin"]):
        points.append("• Complete the full course even if you feel better")
        points.append("• Take with food to reduce stomach upset")
        points.append("• May reduce effectiveness of birth control pills")
    
    if "statin" in meds_lower or any(s in meds_lower for s in ["atorvastatin", "simvastatin"]):
        points.append("• Take in the evening for best results")
        points.append("• Report any muscle pain or weakness")
        points.append("• Limit alcohol consumption")
        points.append("• Avoid grapefruit juice")
    
    if "ace" in meds_lower or "lisinopril" in meds_lower:
        points.append("• May cause dry cough (usually harmless)")
        points.append("• Monitor blood pressure regularly")
        points.append("• Stay hydrated")
    
    # Add interaction-specific counseling
    if interactions:
        points.append("\n⚠️ DRUG INTERACTION WARNINGS:")
        for interaction in interactions:
            points.append(f"• {interaction['drug1']} + {interaction['drug2']}: {interaction['description']}")
    
    if not points:
        points.append("• Take medication as directed by your healthcare provider")
        points.append("• Do not stop taking without consulting your doctor")
        points.append("• Store medications in a cool, dry place")
    
    return "\n".join(points)
