"""SQLite persistence boundary for Atlas11 proposal-review coordination records."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.schemas import (
        Approval,
        AuditEvent,
        ClashReport,
        Proposal,
        ReviewCreated,
        Role,
    )

_SECRET_PATTERN = re.compile(
    r"(?i)(aws_access_key_id|aws_secret_access_key|aws_session_token|"
    r"authorization|token|secret|password)\s*[:=]\s*[^\s,;]+"
)


class StoreError(Exception):
    """Base exception for expected SQLite repository failures."""


class StoreNotFoundError(StoreError):
    """Raised when a requested durable record does not exist."""


class StoreConflictError(StoreError):
    """Raised when a lifecycle operation cannot use the current durable state."""


class SQLiteStore:
    """Persist validated proposal, review, approval, and immutable audit contracts."""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        """Create the local schema and indexes if they do not yet exist."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    city_id TEXT NOT NULL,
                    district_id TEXT,
                    sector TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    submitted_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL REFERENCES proposals(proposal_id),
                    report_json TEXT,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    review_id TEXT NOT NULL REFERENCES reviews(review_id),
                    proposal_id TEXT NOT NULL REFERENCES proposals(proposal_id),
                    decision TEXT NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED')),
                    actor TEXT NOT NULL,
                    role TEXT NOT NULL,
                    reason TEXT,
                    decided_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    proposal_id TEXT,
                    review_id TEXT,
                    project_id TEXT,
                    approval_id TEXT,
                    actor TEXT,
                    role TEXT,
                    timestamp TEXT NOT NULL,
                    payload_summary TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_reviews_proposal_id
                    ON reviews(proposal_id);
                CREATE INDEX IF NOT EXISTS idx_approvals_proposal_id
                    ON approvals(proposal_id);
                CREATE INDEX IF NOT EXISTS idx_audit_proposal_id
                    ON audit_events(proposal_id);
                CREATE INDEX IF NOT EXISTS idx_audit_review_id
                    ON audit_events(review_id);
                """
            )

    def create_proposal(self, proposal: Proposal, audit_event: AuditEvent) -> Proposal:
        """Insert a submitted proposal and its intake audit event atomically."""
        payload = self._dump(proposal)
        with self._transaction() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO proposals(
                        proposal_id, status, city_id, district_id, sector, payload_json, submitted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["proposal_id"],
                        self._enum_value(payload["status"]),
                        payload["city_id"],
                        payload.get("district_id"),
                        payload["sector"],
                        self._json(payload),
                        payload["submitted_at"],
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise StoreConflictError("Proposal already exists.") from error
            self._insert_audit(connection, audit_event)
        return proposal

    def get_proposal(self, proposal_id: str) -> Proposal:
        """Return one validated persisted proposal by its canonical ID."""
        row = self._fetchone(
            "SELECT status, payload_json FROM proposals WHERE proposal_id = ?",
            (proposal_id,),
        )
        if row is None:
            raise StoreNotFoundError("Proposal not found.")
        payload = json.loads(row["payload_json"])
        payload["status"] = row["status"]
        return self._model("Proposal").model_validate(payload)

    def create_review(
        self,
        review_id: str,
        proposal_id: str,
        source: str,
        created_at: str,
        audit_event: AuditEvent,
    ) -> ReviewCreated:
        """Create one pending review and audit event for a submitted proposal atomically."""
        with self._transaction() as connection:
            proposal = connection.execute(
                "SELECT status FROM proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
            if proposal is None:
                raise StoreNotFoundError("Proposal not found.")
            if proposal["status"] != "SUBMITTED":
                raise StoreConflictError("Proposal is not available for review.")
            try:
                connection.execute(
                    """
                    INSERT INTO reviews(review_id, proposal_id, source, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (review_id, proposal_id, source, created_at),
                )
            except sqlite3.IntegrityError as error:
                raise StoreConflictError("Review already exists.") from error
            self._insert_audit(connection, audit_event)
        return self._model("ReviewCreated").model_validate({"review_id": review_id})

    def complete_review(
        self,
        review_id: str,
        report: ClashReport,
        completed_at: str,
        audit_events: Sequence[AuditEvent],
    ) -> ClashReport:
        """Persist a validated report, mark its proposal reviewed, and append audits atomically."""
        report_payload = self._dump(report)
        with self._transaction() as connection:
            review = connection.execute(
                "SELECT proposal_id FROM reviews WHERE review_id = ?", (review_id,)
            ).fetchone()
            if review is None:
                raise StoreNotFoundError("Review not found.")
            if review["proposal_id"] != report_payload["proposal_id"]:
                raise StoreConflictError("Report proposal does not match review.")
            updated_review = connection.execute(
                """
                UPDATE reviews SET report_json = ?, completed_at = ?
                WHERE review_id = ? AND report_json IS NULL
                """,
                (self._json(report_payload), completed_at, review_id),
            )
            if updated_review.rowcount != 1:
                raise StoreConflictError("Review has already completed.")
            updated_proposal = connection.execute(
                "UPDATE proposals SET status = 'REVIEWED' WHERE proposal_id = ? AND status = 'SUBMITTED'",
                (report_payload["proposal_id"],),
            )
            if updated_proposal.rowcount != 1:
                raise StoreConflictError("Proposal is not in submitted state.")
            for audit_event in audit_events:
                self._insert_audit(connection, audit_event)
        return report

    def get_completed_report(self, review_id: str) -> ClashReport:
        """Return only a completed, schema-valid review report."""
        row = self._fetchone(
            "SELECT report_json FROM reviews WHERE review_id = ?", (review_id,)
        )
        if row is None:
            raise StoreNotFoundError("Review not found.")
        if row["report_json"] is None:
            raise StoreConflictError("Review is not complete.")
        return self._model("ClashReport").model_validate_json(row["report_json"])

    def record_approval(
        self, approval: Approval, role: Role, audit_event: AuditEvent
    ) -> Approval:
        """Persist one approver decision, terminal proposal state, and audit event atomically."""
        payload = self._dump(approval)
        with self._transaction() as connection:
            review = connection.execute(
                "SELECT proposal_id, report_json FROM reviews WHERE review_id = ?",
                (payload["review_id"],),
            ).fetchone()
            if review is None:
                raise StoreNotFoundError("Review not found.")
            if (
                review["proposal_id"] != payload["proposal_id"]
                or review["report_json"] is None
            ):
                raise StoreConflictError(
                    "Approval does not reference a completed proposal review."
                )
            updated = connection.execute(
                """
                UPDATE proposals SET status = ?
                WHERE proposal_id = ? AND status = 'REVIEWED'
                """,
                (payload["decision"], payload["proposal_id"]),
            )
            if updated.rowcount != 1:
                raise StoreConflictError("Proposal is not in reviewed state.")
            try:
                connection.execute(
                    """
                    INSERT INTO approvals(
                        approval_id, review_id, proposal_id, decision, actor, role, reason, decided_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["approval_id"],
                        payload["review_id"],
                        payload["proposal_id"],
                        payload["decision"],
                        payload["actor"],
                        self._enum_value(role),
                        payload.get("reason"),
                        payload["decided_at"],
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise StoreConflictError("Approval already exists.") from error
            self._insert_audit(connection, audit_event)
        return approval

    def append_audit(self, audit_event: AuditEvent) -> AuditEvent:
        """Append one immutable sanitized audit event without modifying prior entries."""
        with self._transaction() as connection:
            self._insert_audit(connection, audit_event)
        return audit_event

    def list_audit(
        self, proposal_id: str | None = None, review_id: str | None = None
    ) -> list[AuditEvent]:
        """Return audit events matching every supplied canonical ID filter."""
        clauses: list[str] = []
        values: list[str] = []
        if proposal_id is not None:
            clauses.append("proposal_id = ?")
            values.append(proposal_id)
        if review_id is not None:
            clauses.append("review_id = ?")
            values.append(review_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM audit_events{where} ORDER BY timestamp, event_id",
                values,
            ).fetchall()
        audit_model = self._model("AuditEvent")
        return [audit_model.model_validate(dict(row)) for row in rows]

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _fetchone(self, statement: str, values: tuple[str, ...]) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(statement, values).fetchone()

    def _insert_audit(
        self, connection: sqlite3.Connection, audit_event: AuditEvent
    ) -> None:
        payload = self._dump(audit_event)
        summary = self._sanitize_summary(str(payload["payload_summary"]))
        try:
            connection.execute(
                """
                INSERT INTO audit_events(
                    event_id, event_type, proposal_id, review_id, project_id, approval_id,
                    actor, role, timestamp, payload_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["event_id"],
                    payload["event_type"],
                    payload.get("proposal_id"),
                    payload.get("review_id"),
                    payload.get("project_id"),
                    payload.get("approval_id"),
                    payload.get("actor"),
                    self._enum_value(payload.get("role")),
                    payload["timestamp"],
                    summary,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise StoreConflictError("Audit event already exists.") from error

    @staticmethod
    def _sanitize_summary(summary: str) -> str:
        cleaned = _SECRET_PATTERN.sub("[REDACTED]", summary).strip()
        if not cleaned:
            raise StoreError("Audit payload summary must not be empty.")
        return cleaned[:500]

    @staticmethod
    def _dump(model: Any) -> dict[str, Any]:
        return model.model_dump(mode="json")

    @staticmethod
    def _json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _enum_value(value: Any) -> Any:
        return getattr(value, "value", value)

    @staticmethod
    def _model(name: str) -> Any:
        from agent import schemas

        try:
            return getattr(schemas, name)
        except AttributeError as error:
            raise StoreError(
                f"agent.schemas.{name} is required before using the SQLite store."
            ) from error
