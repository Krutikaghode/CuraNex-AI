import io

import pymupdf
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.reports.extraction import ocr_available

needs_ocr = pytest.mark.skipif(not ocr_available(), reason="Tesseract binary not installed")

REPORT_TEXT = "Fasting glucose 126 mg/dL. HbA1c 6.8 percent."


def text_pdf(text: str = REPORT_TEXT) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    return document.tobytes()


def text_image(text: str = "Fasting Glucose 126") -> bytes:
    image = Image.new("RGB", (1200, 200), "white")
    ImageDraw.Draw(image).text((40, 60), text, fill="black", font=ImageFont.load_default(56))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def scanned_pdf() -> bytes:
    """A PDF whose only page is an image, like scanner output."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_image(page.rect, stream=text_image())
    return document.tobytes()


def make_patient(client) -> int:
    payload = {"full_name": "Asha Sharma", "age": 40, "gender": "Female"}
    return client.post("/patients", json=payload).json()["id"]


def upload(client, patient_id, name, data, content_type="application/octet-stream"):
    return client.post(
        f"/patients/{patient_id}/reports", files={"file": (name, data, content_type)}
    )


def test_pdf_with_text_layer(client):
    patient_id = make_patient(client)
    response = upload(client, patient_id, "labs.pdf", text_pdf())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "processed"
    assert body["extraction_method"] == "text"
    assert body["page_count"] == 1
    assert "HbA1c 6.8" in body["text"]

    listed = client.get(f"/patients/{patient_id}/reports").json()
    assert [r["id"] for r in listed] == [body["id"]]
    assert "text" not in listed[0]
    assert client.get(f"/reports/{body['id']}").json()["text"] == body["text"]
    assert client.get("/reports/count").json() == {"count": 1}

    downloaded = client.get(f"/reports/{body['id']}/file")
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-")


@needs_ocr
def test_image_is_ocrd(client):
    body = upload(client, make_patient(client), "scan.png", text_image()).json()
    assert body["status"] == "processed"
    assert body["extraction_method"] == "ocr"
    assert "Glucose 126" in body["text"]


@needs_ocr
def test_scanned_pdf_falls_back_to_ocr(client):
    body = upload(client, make_patient(client), "scan.pdf", scanned_pdf()).json()
    assert body["extraction_method"] == "ocr"
    assert "Glucose 126" in body["text"]


def test_type_is_checked_by_content_not_name(client):
    patient_id = make_patient(client)
    response = upload(client, patient_id, "evil.pdf", b"#!/bin/sh\necho hi\n")
    assert response.status_code == 415


def test_corrupt_pdf_is_recorded_as_failed(client):
    body = upload(client, make_patient(client), "broken.pdf", b"%PDF-1.7 garbage").json()
    assert body["status"] == "failed"
    assert body["error"]
    assert client.get("/reports/count").json() == {"count": 0}


def test_upload_limits_and_missing_patient(client, monkeypatch):
    from app.services import reports

    patient_id = make_patient(client)
    assert upload(client, patient_id, "empty.pdf", b"").status_code == 422
    assert upload(client, 999, "labs.pdf", text_pdf()).status_code == 404

    monkeypatch.setattr(reports, "MAX_UPLOAD_BYTES", 100)
    assert upload(client, patient_id, "labs.pdf", text_pdf()).status_code == 413


def test_filename_is_not_used_on_disk(client):
    body = upload(client, make_patient(client), "../../etc/passwd.pdf", text_pdf()).json()
    assert body["filename"] == "passwd.pdf"
    assert client.get("/reports/999").status_code == 404
