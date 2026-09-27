"""CAP 1.2 (Common Alerting Protocol) export, the format used by NDMA's SACHET for IMD warnings.

Simulated demo alerts are marked <status>Exercise</status>, never Actual.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
IST = timezone(timedelta(hours=5, minutes=30))
CAP_LANG = {"en": "en-IN", "te": "te-IN", "hi": "hi-IN"}
EVENT_EN = {"rain": "Rainfall", "heat": "Heat wave", "wind": "Strong wind"}


def _ring_to_cap(geom: dict | None, max_points: int = 100) -> str | None:
    """CAP polygon: 'lat,lon lat,lon ...', closed, from a GeoJSON (Multi)Polygon's largest outer ring."""
    if not geom:
        return None
    coords = geom["coordinates"]
    rings = [poly[0] for poly in coords] if geom["type"] == "MultiPolygon" else [coords[0]]
    ring = max(rings, key=len)
    step = max(1, len(ring) // max_points)
    pts = ring[::step]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return " ".join(f"{lat:.5f},{lon:.5f}" for lon, lat in pts)


def build_cap(warning: dict, run: dict, panchayat: dict, block: dict, district: dict | None, state_name: str) -> str:
    ET.register_namespace("", CAP_NS)
    q = lambda tag: f"{{{CAP_NS}}}{tag}"  # noqa: E731
    alert = ET.Element(q("alert"))
    sent = datetime.now(IST).replace(microsecond=0).isoformat()

    def sub(parent, tag, text):
        el = ET.SubElement(parent, q(tag))
        el.text = text
        return el

    sub(alert, "identifier", f"KSHETRA-{warning['id']}")
    sub(alert, "sender", "kshetra@demo.local")
    sub(alert, "sent", sent)
    sub(alert, "status", "Exercise" if warning.get("simulated") else "Actual")
    sub(alert, "msgType", "Alert")
    sub(alert, "scope", "Public")
    if warning.get("simulated"):
        sub(alert, "note", "Demo Mode simulated extreme event - not a real warning.")

    onset = datetime.fromisoformat(f"{warning['date']}T00:00:00").replace(tzinfo=IST)
    area_desc = ", ".join(x for x in [f"{panchayat['name']} GP", f"{block['name']} block",
                                      district["name"] if district else None, state_name] if x)
    polygon = _ring_to_cap(panchayat.get("geom"))

    for lang in ("en", "te", "hi"):
        info = ET.SubElement(alert, q("info"))
        sub(info, "language", CAP_LANG[lang])
        sub(info, "category", "Met")
        sub(info, "event", EVENT_EN[warning["hazard"]])
        sub(info, "responseType", "Prepare")
        sub(info, "urgency", "Expected")
        sub(info, "severity", warning["cap"]["severity"])
        sub(info, "certainty", warning["cap"]["certainty"])
        sub(info, "effective", sent)
        sub(info, "onset", onset.isoformat())
        sub(info, "expires", (onset + timedelta(days=1)).isoformat())
        sub(info, "senderName", "Kshetra (downscaled from the IMD block forecast)")
        sub(info, "headline", warning["title"][lang])
        sub(info, "description", warning["body"][lang])
        sub(info, "instruction", " ".join(f"{i}. {a}." for i, a in enumerate(warning["actions"][lang], start=1)))
        for name, value in (("colour_code", warning["level"].upper()), ("value", f"{warning['value']} {warning['unit']}"),
                            ("confidence", warning["confidence"]), ("run_id", str(run["id"]))):
            p = ET.SubElement(info, q("parameter"))
            sub(p, "valueName", name)
            sub(p, "value", value)
        area = ET.SubElement(info, q("area"))
        sub(area, "areaDesc", area_desc)
        if polygon:
            sub(area, "polygon", polygon)
        if panchayat.get("lgd_code"):
            g = ET.SubElement(area, q("geocode"))
            sub(g, "valueName", "LGD")
            sub(g, "value", panchayat["lgd_code"])

    ET.indent(alert)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(alert, encoding="unicode")
