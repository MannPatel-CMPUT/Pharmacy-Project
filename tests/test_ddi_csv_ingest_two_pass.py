"""
Regression test for the two-pass DDII CSV ingest fix (Feb 2026).

The earlier optimisation cached drug ids from ``db.flush()`` inside the same
transaction as interaction inserts. When an interaction row failed and forced
``db.rollback()``, the flushed-but-uncommitted drug rows disappeared, but the
Python cache still held their stale ids — producing a Postgres FK violation
(``drug_interactions_drug_b_id_fkey``) on the next commit. The fix commits
drugs + aliases in an explicit first pass so interaction inserts always see
durable foreign keys.
"""
import io

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Drug, DrugAlias, DrugInteraction
from services.ddi_csv_ingestion import SOURCE_TAG, ingest_ddii_csv_stream

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _csv(rows):
    header = "Drug 1,Drug 2,Interaction Description\n"
    def _quote(s):
        if "," in s or '"' in s:
            return '"' + s.replace('"', '""') + '"'
        return s
    body = "\n".join(f"{_quote(a)},{_quote(b)},{_quote(d)}" for a, b, d in rows)
    return io.StringIO(header + body)


def test_two_pass_ingest_commits_drugs_before_interactions():
    """After ingest, every interaction's FK must resolve to a real Drug row."""
    stream = _csv(
        [
            ("Warfarin", "Aspirin", "Warfarin may increase the anticoagulant activities of Aspirin."),
            ("Warfarin", "Ibuprofen", "The risk of bleeding is increased when Ibuprofen is combined with Warfarin."),
            ("Atorvastatin", "Warfarin", "Atorvastatin may increase the anticoagulant activities of Warfarin."),
            ("Metformin", "Aspirin", "The risk of adverse effects can be increased when Aspirin is combined with Metformin."),
        ]
    )
    with SessionLocal() as db:
        stats = ingest_ddii_csv_stream(db, stream)

    assert stats["inserted"] == 4
    assert stats["failed"] == 0

    with SessionLocal() as db:
        # 5 unique drugs: warfarin, aspirin, ibuprofen, atorvastatin, metformin
        assert db.query(Drug).count() == 5
        drug_ids = {d.id for d in db.query(Drug).all()}
        # Every interaction's FKs must reference a real drug id (the bug that
        # crashed prod was drug_b_id pointing at a rolled-back drug row).
        for ix in db.query(DrugInteraction).all():
            assert ix.drug_a_id in drug_ids, f"orphan drug_a_id={ix.drug_a_id}"
            assert ix.drug_b_id in drug_ids, f"orphan drug_b_id={ix.drug_b_id}"
            assert ix.source == SOURCE_TAG
        # And one alias per unique drug (via first-appearance).
        assert db.query(DrugAlias).count() == 5


def test_ingest_dedupes_reverse_pairs():
    """(Warfarin, Aspirin) and (Aspirin, Warfarin) collapse to one row."""
    stream = _csv(
        [
            ("Warfarin", "Aspirin", "Warfarin may increase the anticoagulant activities of Aspirin."),
            ("Aspirin", "Warfarin", "Aspirin may increase the anticoagulant activities of Warfarin."),
        ]
    )
    with SessionLocal() as db:
        stats = ingest_ddii_csv_stream(db, stream)

    assert stats["inserted"] == 1
    assert stats["skipped"] == 1


def test_ingest_reuses_existing_drug_rows():
    """Second call with new interaction rows for existing drugs must not fail."""
    # First ingest — creates Warfarin + Aspirin
    stream1 = _csv([("Warfarin", "Aspirin", "Warfarin may increase the anticoagulant activities of Aspirin.")])
    with SessionLocal() as db:
        ingest_ddii_csv_stream(db, stream1)

    # Second ingest with a NEW pair reusing an existing drug (Warfarin)
    stream2 = _csv(
        [
            ("Warfarin", "Ibuprofen", "Warfarin may increase the anticoagulant activities of Ibuprofen."),
        ]
    )
    with SessionLocal() as db:
        stats = ingest_ddii_csv_stream(db, stream2)

    assert stats["inserted"] == 1
    assert stats["failed"] == 0

    with SessionLocal() as db:
        # 3 unique drugs total — Warfarin was reused, not duplicated.
        assert db.query(Drug).count() == 3
        # 2 interactions total (warfarin+aspirin, warfarin+ibuprofen)
        assert db.query(DrugInteraction).count() == 2


def test_ingest_survives_orphan_alias_from_previous_partial_run():
    """
    On a real production hosted-Postgres, a previous partial ingest left an
    orphan `DrugAlias` row (drug_id points at a since-deleted drug or the alias
    exists without a corresponding drug of the same generic name). Because
    ``drug_aliases.alias`` has a GLOBAL unique constraint, naively inserting a
    new alias with the same name for a freshly-created drug produces a
    ``psycopg2.errors.UniqueViolation``. The ingest must detect the pre-existing
    alias and skip it instead of blowing up the whole run.
    """
    # Seed the DB with an ORPHAN alias — same name as a drug we're about to
    # ingest, but linked to a placeholder drug (so the alias exists but the
    # generic-name drug row does not).
    with SessionLocal() as db:
        placeholder = Drug(generic_name="placeholder_drug", brand_name=None)
        db.add(placeholder)
        db.commit()
        db.add(DrugAlias(drug_id=placeholder.id, alias="sodium phosphate, monobasic"))
        db.commit()

    # Now ingest a CSV that would want to create the same alias for a brand
    # new "Sodium phosphate, monobasic" drug.
    stream = _csv(
        [
            (
                "Sodium phosphate, monobasic",
                "Warfarin",
                "The risk of adverse effects can be increased when Warfarin is combined with Sodium phosphate, monobasic.",
            ),
        ]
    )
    with SessionLocal() as db:
        stats = ingest_ddii_csv_stream(db, stream)

    # Interaction must have been inserted — the orphan alias must not block it.
    assert stats["inserted"] == 1, stats
    assert stats["failed"] == 0

    with SessionLocal() as db:
        # Only one alias row per unique alias name (the orphan is preserved).
        aliases = [a.alias.lower() for a in db.query(DrugAlias).all()]
        assert aliases.count("sodium phosphate, monobasic") == 1
        # Drug + interaction present.
        assert db.query(Drug).filter(Drug.generic_name == "sodium phosphate, monobasic").count() == 1
        assert db.query(DrugInteraction).count() == 1
