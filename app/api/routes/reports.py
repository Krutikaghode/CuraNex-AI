"""Medical report upload and retrieval."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.models import MedicalReport
from app.db.session import get_db
from app.reports.extraction import UnsupportedFileError
from app.schemas.report import ReportCount, ReportDetail, ReportSummary
from app.services import patients as patient_service
from app.services import reports as service

router = APIRouter(tags=["reports"])


def _report_or_404(db: Session, report_id: int) -> MedicalReport:
    report = service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} was not found.")
    return report


@router.post(
    "/patients/{patient_id}/reports",
    response_model=ReportDetail,
    status_code=status.HTTP_201_CREATED,
)
async def upload_report(
    patient_id: int, file: UploadFile, db: Session = Depends(get_db)
) -> MedicalReport:
    patient = patient_service.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} was not found.")
    data = await file.read(service.MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    try:
        return service.save_report(db, patient, file.filename or "upload", data)
    except service.UploadTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except UnsupportedFileError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error


@router.get("/patients/{patient_id}/reports", response_model=list[ReportSummary])
def patient_reports(patient_id: int, db: Session = Depends(get_db)) -> list[MedicalReport]:
    if patient_service.get_patient(db, patient_id, include_inactive=True) is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} was not found.")
    return service.list_for_patient(db, patient_id)


@router.get("/reports/count", response_model=ReportCount)
def report_count(db: Session = Depends(get_db)) -> dict:
    return {"count": service.count_reports(db)}


@router.get("/reports/{report_id}", response_model=ReportDetail)
def report_detail(report_id: int, db: Session = Depends(get_db)) -> MedicalReport:
    return _report_or_404(db, report_id)


@router.get("/reports/{report_id}/file")
def report_file(report_id: int, db: Session = Depends(get_db)) -> FileResponse:
    report = _report_or_404(db, report_id)
    path = service.file_path(report)
    if not path.exists():
        raise HTTPException(status_code=410, detail="The stored file is no longer available.")
    return FileResponse(path, media_type=report.content_type, filename=report.filename)
