"""SQLite persistence for CuraNex patient management."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("CURANEX_DB_PATH", str(DATA_DIR / "curanex.db")))


class DuplicateEmailError(ValueError):
    """Raised when a supplied email is already assigned to a patient."""


def get_connection() -> sqlite3.Connection:
    """Return a short-lived connection configured to return dictionary-like rows."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def connection_scope():
    """Commit successful work and always release SQLite's file handle."""
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _add_missing_columns(connection: sqlite3.Connection) -> None:
    """Safely upgrade databases created by the original project scaffold."""
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(patients)").fetchall()
    }
    if "updated_at" not in existing_columns:
        connection.execute("ALTER TABLE patients ADD COLUMN updated_at TIMESTAMP")
        connection.execute(
            "UPDATE patients SET updated_at = created_at WHERE updated_at IS NULL"
        )
    if "is_active" not in existing_columns:
        connection.execute(
            "ALTER TABLE patients ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
        )


def initialize_database() -> None:
    """Create or upgrade the local patient database."""
    with connection_scope() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                age INTEGER NOT NULL CHECK(age BETWEEN 0 AND 130),
                gender TEXT NOT NULL,
                email TEXT UNIQUE,
                phone TEXT,
                concern TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _add_missing_columns(connection)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(full_name)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_patients_active ON patients(is_active)"
        )


def create_patient(
    *,
    full_name: str,
    age: int,
    gender: str,
    email: str | None = None,
    phone: str | None = None,
    concern: str | None = None,
) -> dict[str, Any]:
    """Persist a new patient and return the created record."""
    try:
        with connection_scope() as connection:
            cursor = connection.execute(
                """
                INSERT INTO patients (full_name, age, gender, email, phone, concern)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (full_name, age, gender, email or None, phone or None, concern or None),
            )
            row = connection.execute(
                "SELECT * FROM patients WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return _as_dict(row) or {}
    except sqlite3.IntegrityError as error:
        if "email" in str(error).lower():
            raise DuplicateEmailError("This email is already registered.") from error
        raise


def list_patients(
    *,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    """Return a paginated, newest-first patient list."""
    clauses: list[str] = []
    parameters: list[Any] = []
    if not include_inactive:
        clauses.append("is_active = 1")
    if search:
        clauses.append("(full_name LIKE ? OR email LIKE ? OR phone LIKE ?)")
        search_term = f"%{search.strip()}%"
        parameters.extend([search_term, search_term, search_term])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.extend([limit, offset])
    query = f"""
        SELECT * FROM patients
        {where}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
    """
    with connection_scope() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def get_patient(patient_id: int, *, include_inactive: bool = False) -> dict[str, Any] | None:
    query = "SELECT * FROM patients WHERE id = ?"
    parameters: list[Any] = [patient_id]
    if not include_inactive:
        query += " AND is_active = 1"
    with connection_scope() as connection:
        return _as_dict(connection.execute(query, parameters).fetchone())


def update_patient(patient_id: int, changes: dict[str, Any]) -> dict[str, Any] | None:
    """Apply supplied field changes to an active patient."""
    allowed_fields = {"full_name", "age", "gender", "email", "phone", "concern"}
    fields = {key: value for key, value in changes.items() if key in allowed_fields}
    if not fields:
        return get_patient(patient_id)

    assignments = [f"{field} = ?" for field in fields]
    values = list(fields.values())
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(patient_id)
    try:
        with connection_scope() as connection:
            cursor = connection.execute(
                f"UPDATE patients SET {', '.join(assignments)} "
                "WHERE id = ? AND is_active = 1",
                values,
            )
            if cursor.rowcount == 0:
                return None
            return _as_dict(
                connection.execute(
                    "SELECT * FROM patients WHERE id = ?", (patient_id,)
                ).fetchone()
            )
    except sqlite3.IntegrityError as error:
        if "email" in str(error).lower():
            raise DuplicateEmailError("This email is already registered.") from error
        raise


def deactivate_patient(patient_id: int) -> bool:
    """Soft-delete a patient to preserve medical-record history."""
    with connection_scope() as connection:
        cursor = connection.execute(
            """
            UPDATE patients
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 1
            """,
            (patient_id,),
        )
    return cursor.rowcount > 0


def restore_patient(patient_id: int) -> dict[str, Any] | None:
    with connection_scope() as connection:
        cursor = connection.execute(
            """
            UPDATE patients
            SET is_active = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 0
            """,
            (patient_id,),
        )
        if cursor.rowcount == 0:
            return None
        return _as_dict(
            connection.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        )


def get_patient_count(*, include_inactive: bool = False) -> int:
    query = "SELECT COUNT(*) FROM patients"
    if not include_inactive:
        query += " WHERE is_active = 1"
    with connection_scope() as connection:
        return int(connection.execute(query).fetchone()[0])
