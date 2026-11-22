"""Database-level tests for audit.record / verify_chain (needs SQLAlchemy; runs in CI and on your machine).

The pure hash logic is in test_audit_chain.py. These tests cover what it cannot: sequence numbers assigned from real rows,
the unique (incident_id, seq) index, and the retry when two writers pick the same number.
For a true two-connection race, set TEST_POSTGRES_URL to an empty scratch database; that test is skipped otherwise.
"""
import os
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (register every table)
from app.db.session import Base
from app.models.automation import AuditEvent
from app.models.incident import Incident
from app.models.user import User
from app.services import audit, audit_chain


def _make(engine):
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()
    u = User(email="a@b.c", hashed_password="x")
    db.add(u); db.commit()
    inc = Incident(owner_id=u.id, title="t")
    db.add(inc); db.commit()
    return Session, db, u, inc


@pytest.fixture()
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session, db, u, inc = _make(engine)
    yield Session, db, u, inc
    db.close()


def test_record_then_verify_chain_is_ok_and_head_matches(env):
    _, db, u, inc = env
    for i in range(5):
        audit.record(db, inc.id, u, "report_generated", details={"n": i})
    res = audit.verify_chain(db, inc.id)
    assert res["ok"] is True and res["checked"] == 5 and res["head_seq"] == 5
    assert [e["seq"] for e in audit.export_chain(db, inc.id)] == [1, 2, 3, 4, 5]
    a = audit.anchor(db, inc.id)
    assert a["chain_ok"] and a["head_hash"] == res["head"]
    assert audit_chain.verify(audit.export_chain(db, inc.id))["ok"] is True      # offline re-check agrees


def test_editing_a_row_in_the_database_is_detected(env):
    _, db, u, inc = env
    for _ in range(3):
        audit.record(db, inc.id, u, "report_generated")
    row = db.query(AuditEvent).filter(AuditEvent.incident_id == inc.id, AuditEvent.seq == 2).one()
    row.action = "evidence_deleted"
    db.commit()
    res = audit.verify_chain(db, inc.id)
    assert res["ok"] is False and res["first_break_seq"] == 2


def test_unique_index_refuses_a_duplicate_seq_but_allows_many_legacy_nulls(env):
    _, db, u, inc = env
    audit.record(db, inc.id, u, "report_generated")                       # seq 1
    db.add(AuditEvent(incident_id=inc.id, action="report_generated", seq=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(AuditEvent(incident_id=inc.id, action="report_generated"))     # legacy, no seq
    db.add(AuditEvent(incident_id=inc.id, action="report_generated"))
    db.commit()                                                           # two NULL seq values are fine
    res = audit.verify_chain(db, inc.id)
    assert res["ok"] is True and res["legacy_unchained"] == 2


def test_two_writers_picking_the_same_seq_do_not_fork_the_chain(env, monkeypatch):
    """Simulate the race: the first attempt is built from a stale read of the head (it reuses seq 1)."""
    Session, db, u, inc = env
    audit.record(db, inc.id, u, "report_generated")                       # head is seq 1
    real = audit._next_event
    calls = {"n": 0}

    def stale_first(*a, **kw):
        ev = real(*a, **kw)
        calls["n"] += 1
        if calls["n"] == 1:
            ev.seq, ev.prev_hash = 1, audit_chain.GENESIS                 # what a writer that read before the commit would build
            ev.event_hash = audit_chain.event_hash(audit.chain_fields(ev), ev.prev_hash)
        return ev

    monkeypatch.setattr(audit, "_next_event", stale_first)
    audit.record(db, inc.id, u, "report_generated")
    monkeypatch.setattr(audit, "_next_event", real)
    assert calls["n"] == 2                                                # one conflict, one retry
    res = audit.verify_chain(db, inc.id)
    assert res["ok"] is True and res["checked"] == 2 and res["head_seq"] == 2


def test_record_gives_up_with_a_clear_error_after_repeated_conflicts(env, monkeypatch):
    _, db, u, inc = env
    audit.record(db, inc.id, u, "report_generated")
    real = audit._next_event

    def always_stale(*a, **kw):
        ev = real(*a, **kw)
        ev.seq, ev.prev_hash = 1, audit_chain.GENESIS
        ev.event_hash = audit_chain.event_hash(audit.chain_fields(ev), ev.prev_hash)
        return ev

    monkeypatch.setattr(audit, "_next_event", always_stale)
    with pytest.raises(RuntimeError, match="audit chain"):
        audit.record(db, inc.id, u, "report_generated")


def test_commit_false_events_chain_inside_one_transaction(env):
    _, db, u, inc = env
    audit.record(db, inc.id, u, "report_generated", commit=False)
    audit.record(db, inc.id, u, "report_generated", commit=False)
    db.commit()
    assert audit.verify_chain(db, inc.id)["checked"] == 2


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="needs a scratch PostgreSQL database in TEST_POSTGRES_URL")
def test_parallel_writers_on_postgres_never_duplicate_a_seq():
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    Base.metadata.drop_all(engine)
    Session, db, u, inc = _make(engine)
    errors = []

    def worker():
        s = Session()
        try:
            for _ in range(10):
                audit.record(s, inc.id, u, "report_generated")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    res = audit.verify_chain(db, inc.id)
    assert res["ok"] is True and res["checked"] == 60
    db.close()
    Base.metadata.drop_all(engine)
