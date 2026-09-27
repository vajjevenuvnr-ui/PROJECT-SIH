"""Farmer contacts: upload (CSV / Excel), masking, block scoping, self-registration with consent."""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.api.farmers import mask, normalize_mobile
from app.core.datasource import demo_source
from app.main import app

client = TestClient(app, headers={"X-Demo-Mode": "1"})


@pytest.fixture(autouse=True)
def _clean():
    demo_source()._farmers.clear()
    yield
    demo_source()._farmers.clear()


def test_normalize_and_mask():
    assert normalize_mobile("+91 98765-43210") == "9876543210"
    assert normalize_mobile("09876543210") == "9876543210"
    assert normalize_mobile(9876543210.0) == "9876543210"
    assert normalize_mobile("12345") is None and normalize_mobile("5876543210") is None
    assert mask("9876543210") == "98xxxxxx10"


def test_csv_upload_and_masked_list():
    csv = ("name,mobile,panchayat,crop,language\nRamesh,9876543210,Ahmadipur,cotton,te\n"
           "Sita,+91 91234 56789,7,paddy,Telugu\nBad,123,Ahmadipur,cotton,te\nX,9000000000,Nowhere,,\n"
           "Ramesh again,9876543210,Ahmadipur,cotton,te\n")
    r = client.post("/api/farmers/upload?block_id=1", files={"file": ("f.csv", csv, "text/csv")}).json()
    assert r["added"] == 2 and r["error_count"] == 2 and r["duplicates"] == 1
    assert {e["reason"] for e in r["errors"]} == {"invalid_mobile", "unknown_panchayat"}
    lst = client.get("/api/farmers?block_id=1").json()
    assert lst["total"] == 2 and all("x" in f["mobile_masked"] for f in lst["farmers"])
    assert "9876543210" not in str(lst)


def test_excel_upload():
    wb = Workbook(); ws = wb.active
    ws.append(["Name", "Mobile", "Panchayat", "Crop", "Language"])
    ws.append(["Ravi", 9123456780, "Ahmadipur", "maize", "hi"])
    buf = io.BytesIO(); wb.save(buf)
    r = client.post("/api/farmers/upload", files={"file": ("f.xlsx", buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert r["added"] == 1


def test_subscribe_needs_consent_and_counts_in_share():
    assert client.post("/api/farmers/subscribe", json={"panchayat_id": 7, "mobile": "9876543210", "consent": False}).status_code == 422
    assert client.post("/api/farmers/subscribe", json={"panchayat_id": 7, "mobile": "12", "consent": True}).status_code == 422
    r = client.post("/api/farmers/subscribe", json={"panchayat_id": 7, "mobile": "9876543210", "consent": True, "language": "te"})
    assert r.status_code == 201 and r.json()["mobile_masked"] == "98xxxxxx10"
    f = client.get("/api/farmers?block_id=1").json()
    assert f["self_registered"] == 1 and f["per_panchayat"]["7"] == 1
    client.post("/api/farmers/unsubscribe", json={"panchayat_id": 7, "mobile": "9876543210"})
    assert client.get("/api/farmers?block_id=1").json()["total"] == 0


def test_template():
    r = client.get("/api/farmers/template.csv")
    assert r.status_code == 200 and r.text.startswith("name,mobile,panchayat")
