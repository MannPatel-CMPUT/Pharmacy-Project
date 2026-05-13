"""Kroll-style prescription workflow labels for UI and notifications."""

# Maps internal status -> human-readable stage (patient / staff facing)
STAGE_DISPLAY: dict[str, str] = {
    "new": "Prescription received",
    "triage": "Order entry / data entry",
    "waiting_info": "Waiting for clarification",
    "ready_to_fill": "Queued for filling",
    "filled": "Ready for pickup",
    "dispensed": "Picked up / handed to patient",
    "completed": "Completed",
}


def is_pickup_ready(status: str) -> bool:
    """True when the Rx is filled and bagged, waiting for the patient."""
    return status == "filled"


def next_stage_hint(status: str) -> str:
    hints = {
        "new": "Move to triage when Rx is entered.",
        "triage": "Advance to ready to fill or request more info.",
        "waiting_info": "When resolved, move to ready to fill.",
        "ready_to_fill": "After verification and labeling, mark filled.",
        "filled": "Notify patient — ready for pickup. Then mark dispensed when collected.",
        "dispensed": "Mark completed when counseling / documentation is done.",
        "completed": "No further steps.",
    }
    return hints.get(status, "")
