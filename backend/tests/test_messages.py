"""Farmer message builder and message endpoint."""

from fastapi.testclient import TestClient

from app.core.datasource import demo_source
from app.main import app
from app.services.messages import sms_info

client = TestClient(app, headers={"X-Demo-Mode": "1"})
AHMADIPUR = next(p["id"] for p in demo_source().list_panchayats(1) if p["name"] == "Ahmadipur")


def test_gsm7_single_and_multi_segment():
    assert sms_info("a" * 160) == {"encoding": "GSM-7", "chars": 160, "units": 160, "segments": 1, "per_segment": 160}
    two = sms_info("a" * 161)
    assert (two["segments"], two["per_segment"]) == (2, 153)
    assert sms_info("{}")["units"] == 4  # extension chars count double


def test_telugu_forces_ucs2():
    info = sms_info("పత్తి" * 20)
    assert info["encoding"] == "UCS-2" and info["segments"] == 2 and info["per_segment"] == 67


def _approved_advisory() -> int:
    adv = client.post("/api/advisory/generate",
                      json={"panchayat_id": AHMADIPUR, "crop": "cotton", "stage": "square_formation"}).json()
    client.post(f"/api/advisory/{adv['id']}/approve")
    return adv["id"]


def test_sms_in_telugu_has_top3_and_link():
    adv_id = _approved_advisory()
    body = client.get(f"/api/advisory/{adv_id}/message",
                      params={"lang": "te", "channel": "sms", "base_url": "http://192.168.1.5:3000"}).json()
    text = body["text"]
    assert text.startswith("Kshetra | అహ్మదీపూర్")
    assert "1. గురువారం వరకు పురుగుమందు పిచికారీ వాయిదా వేయండి" in text
    assert "4." not in text  # SMS keeps the top 3
    assert body["link"] == f"http://192.168.1.5:3000/f/{AHMADIPUR}?lang=te"
    assert body["sms"]["encoding"] == "UCS-2" and body["sms"]["segments"] >= 2
    assert body["panchayat"]["registered_farmers"] == 312


def test_whatsapp_is_rich_and_english_sms_is_gsm7():
    adv_id = _approved_advisory()
    wa = client.get(f"/api/advisory/{adv_id}/message", params={"lang": "en", "channel": "whatsapp"}).json()["text"]
    assert "*Postpone pesticide spray until Thursday*" in wa and "⛔" in wa and "_because 72%" in wa
    sms = client.get(f"/api/advisory/{adv_id}/message", params={"lang": "en", "channel": "sms"}).json()
    assert sms["sms"]["encoding"] == "GSM-7"


def test_bad_base_url_falls_back():
    adv_id = _approved_advisory()
    body = client.get(f"/api/advisory/{adv_id}/message", params={"base_url": "javascript:alert(1)"}).json()
    assert body["link"].startswith("http://localhost:3000/f/")


def test_public_payload_has_fields_for_farmer_page():
    body = client.get(f"/api/public/panchayat/{AHMADIPUR}", params={"lang": "te"}).json()
    assert body["panchayat"]["block"] == "గజ్వేల్"
    assert {"rain_prob_2_5mm", "rh", "wind_kmh"} <= set(body["days"][0])


def test_health_reports_lan_ip_key():
    assert "lan_ip" in client.get("/health").json()
