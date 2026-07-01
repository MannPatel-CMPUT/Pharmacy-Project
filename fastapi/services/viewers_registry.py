"""
In-memory registry of "who is currently viewing which intake".

Each entry is a `(intake_id, username) -> last_seen (utc datetime)` heartbeat.
Entries older than :data:`STALE_AFTER_SECONDS` are treated as inactive and cleaned
up lazily on each read/write. Ephemeral by design — a process restart is
functionally equivalent to "everyone stopped looking" which is what we want.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, Iterable, List, Tuple

STALE_AFTER_SECONDS = 40  # heartbeats fire every ~20s from the client

_state: Dict[Tuple[int, str], datetime] = {}
_lock = Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sweep_locked(cutoff: datetime) -> None:
    """Assumes caller holds ``_lock``. Drops stale entries in place."""
    stale = [k for k, ts in _state.items() if ts < cutoff]
    for k in stale:
        _state.pop(k, None)


def heartbeat(username: str, intake_ids: Iterable[int]) -> None:
    """Record that ``username`` is currently viewing each id in ``intake_ids``."""
    if not username:
        return
    now = _now()
    with _lock:
        _sweep_locked(now - timedelta(seconds=STALE_AFTER_SECONDS))
        for iid in intake_ids:
            try:
                iid_int = int(iid)
            except (TypeError, ValueError):
                continue
            _state[(iid_int, username)] = now


def viewers_for(
    intake_ids: Iterable[int],
    *,
    exclude_username: str | None = None,
) -> Dict[int, List[str]]:
    """
    Return a mapping ``{intake_id: [username, …]}`` for the given intakes.

    Users in ``exclude_username`` (typically the caller themselves) are omitted so
    the UI shows only *other* pharmacists co-viewing.
    """
    ids = {int(i) for i in intake_ids if str(i).lstrip("-").isdigit()}
    if not ids:
        return {}
    cutoff = _now() - timedelta(seconds=STALE_AFTER_SECONDS)
    out: Dict[int, List[str]] = {i: [] for i in ids}
    with _lock:
        _sweep_locked(cutoff)
        for (iid, user), ts in _state.items():
            if iid in ids and user != exclude_username:
                out[iid].append(user)
    for iid in out:
        out[iid].sort()
    return out
