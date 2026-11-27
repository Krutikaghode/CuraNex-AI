"""Store uploaded reports on disk and their extracted text in the database."""

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MedicalReport, Patient
from app.reports.extraction import extract_text, sniff_content_type

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
EXTENSIONS = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


class UploadTooLargeError(ValueError):
    pass


def reports_root() -> Path:
    return Path(get_settings().data_dir) / "reports"


def save_report(db: Session, patient: Patient, filename: str, data: bytes) -> MedicalReport:
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadTooLargeError(f"Files are limited to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    content_type = sniff_content_type(data)  # raises UnsupportedFileError

    # Stored under a random name: user-supplied filenames never touch the filesystem.
    relative = Path(str(patient.id)) / f"{uuid.uuid4().hex}{EXTENSIONS[content_type]}"
    destination = reports_root() / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)

    report = MedicalReport(
        patient_id=patient.id,
        filename=Path(filename or "upload").name[:255],
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_path=str(relative),
    )
    try:
        result = extract_text(data, content_type)
        report.text = result.text
        report.extraction_method = result.method
        report.page_count = result.page_count
        report.error = "; ".join(result.warnings) or None
        report.status = "processed" if result.text.strip() else "failed"
        if report.status == "failed" and not report.error:
            report.error = "No text could be extracted."
    except Exception as error:  # corrupt files must not lose the upload record
        report.text, report.extraction_method, report.page_count = "", "none", 0
        report.status, report.error = "failed", f"Extraction failed: {error}"

    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_for_patient(db: Session, patient_id: int) -> list[MedicalReport]:
    query = (
        select(MedicalReport)
        .where(MedicalReport.patient_id == patient_id)
        .order_by(MedicalReport.created_at.desc(), MedicalReport.id.desc())
    )
    return list(db.scalars(query))


def get_report(db: Session, report_id: int) -> MedicalReport | None:
    return db.get(MedicalReport, report_id)


def file_path(report: MedicalReport) -> Path:
    return reports_root() / report.storage_path


def count_reports(db: Session, *, processed_only: bool = True) -> int:
    query = select(func.count()).select_from(MedicalReport)
    if processed_only:
        query = query.where(MedicalReport.status == "processed")
    return int(db.scalar(query) or 0)
