"""Farmer message builder: SMS (short, segment-aware) and WhatsApp (rich) in te / hi / en.

SMS length rules: plain Latin text uses GSM-7 (160 chars, or 153 per part when split).
Any Telugu/Hindi character or emoji forces UCS-2 (70 chars, or 67 per part), so Indian-language
SMS are counted in segments and kept to the top 3 actions.
"""

from __future__ import annotations

import math
from datetime import date as date_cls

from app.services.advisory import WEEKDAYS

GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXT = set("^{}\\[~]|€")  # count as 2 units

CONFIDENCE_WORDS = {  # Telugu/Hindi need native-speaker review
    "en": {"label": "Forecast confidence", "high": "High", "medium": "Medium", "low": "Low"},
    "te": {"label": "అంచనా నమ్మకం", "high": "ఎక్కువ", "medium": "మధ్యస్థం", "low": "తక్కువ"},
    "hi": {"label": "पूर्वानुमान विश्वसनीयता", "high": "उच्च", "medium": "मध्यम", "low": "कम"},
}

MORE = {"en": "Details", "te": "వివరాలు", "hi": "विवरण"}
OUTLOOK = {"en": "Next 3 days", "te": "రాబోయే 3 రోజులు", "hi": "अगले 3 दिन"}
TAG_EMOJI = {"avoid": "⛔", "prepare": "⚠️", "do_now": "✅"}


def sms_info(text: str) -> dict:
    """Encoding, length units and SMS segment count for a message."""
    if all(c in GSM7_BASIC or c in GSM7_EXT for c in text):
        units = sum(2 if c in GSM7_EXT else 1 for c in text)
        encoding, single, multi = "GSM-7", 160, 153
    else:
        units = len(text.encode("utf-16-le")) // 2  # UCS-2 code units (emoji = 2)
        encoding, single, multi = "UCS-2", 70, 67
    segments = 1 if units <= single else math.ceil(units / multi)
    return {"encoding": encoding, "chars": len(text), "units": units, "segments": segments,
            "per_segment": single if segments == 1 else multi}


def _short_weekday(iso: str, lang: str) -> str:
    name = WEEKDAYS[lang][date_cls.fromisoformat(iso).weekday()]
    return name[:3] if lang == "en" else name.replace("వారం", "").replace("वार", "")


def _num(v) -> str:
    r = round(float(v or 0), 1)
    return str(int(r)) if r == int(r) else str(r)


def build_message(*, advisory: dict, forecast: dict, lang: str, channel: str, link: str) -> str:
    gp = forecast["panchayat"]
    name = (gp.get(f"name_{lang}") if lang != "en" else None) or gp["name"]
    items = advisory.get("items") or []
    words = CONFIDENCE_WORDS[lang]
    conf = f"{words['label']}: {words[gp['confidence']]}"

    if channel == "sms":
        lines = [f"Kshetra | {name}"]
        lines += [f"{i}. {it['title'][lang]}" for i, it in enumerate(items[:3], start=1)]
        lines += [conf, f"{MORE[lang]}: {link}"]
        return "\n".join(lines)

    # WhatsApp: rich text (*bold*, _italic_), reasons and a short outlook.
    parts = [f"*Kshetra* | *{name}*", ""]
    for it in items[:4]:
        parts.append(f"{TAG_EMOJI.get(it['tag'], '•')} *{it['title'][lang]}*")
        parts.append(f"_{it['reason'][lang]}_")
        parts.append("")
    outlook = " · ".join(
        f"{_short_weekday(d['date'], lang)} {_num(d['rain_mm'])} mm, {_num(d['tmax'])}°" for d in forecast["days"][:3]
    )
    parts += [f"🌦️ {OUTLOOK[lang]}: {outlook}", f"📊 {conf}", f"👉 {link}"]
    return "\n".join(parts)
