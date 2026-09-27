"""IMD-style colour-coded extreme-weather warnings per panchayat-day (Phase 6b).

Levels follow IMD's impact-based colour code: Yellow (be aware) < Orange (be prepared) < Red (take action).
Rain thresholds are IMD daily categories. Heat and wind thresholds are SIMPLIFIED absolute values
(IMD heatwave criteria also need departure from normal, which needs climatology - Phase 7).

The siren / push alert fires only for Orange or Red with High or Medium confidence, to avoid alarm fatigue.
Texts are in en / te / hi (Telugu and Hindi need native-speaker review).
"""

from __future__ import annotations

from datetime import date as date_cls

from app.services.advisory import WEEKDAYS

LEVELS = ("yellow", "orange", "red")
RANK = {lvl: i for i, lvl in enumerate(LEVELS)}

# (threshold, level, event) - checked highest first
RAIN = [(204.5, "red", "extremely_heavy_rain"), (115.6, "orange", "very_heavy_rain"), (64.5, "yellow", "heavy_rain")]
HEAT = [(45.0, "red", "severe_heatwave"), (43.0, "orange", "heatwave"), (40.0, "yellow", "heatwave")]
WIND = [(60.0, "red", "gale"), (40.0, "orange", "strong_wind"), (30.0, "yellow", "strong_wind")]

LEVEL_NAME = {
    "en": {"yellow": "YELLOW alert", "orange": "ORANGE alert", "red": "RED alert"},
    "te": {"yellow": "పసుపు హెచ్చరిక", "orange": "నారింజ హెచ్చరిక", "red": "ఎరుపు హెచ్చరిక"},
    "hi": {"yellow": "पीला अलर्ट", "orange": "नारंगी अलर्ट", "red": "लाल अलर्ट"},
}
EVENT_NAME = {
    "en": {"heavy_rain": "Heavy rain", "very_heavy_rain": "Very heavy rain", "extremely_heavy_rain": "Extremely heavy rain",
           "heatwave": "Heatwave", "severe_heatwave": "Severe heatwave", "strong_wind": "Strong wind", "gale": "Gale-force wind"},
    "te": {"heavy_rain": "భారీ వర్షం", "very_heavy_rain": "అతి భారీ వర్షం", "extremely_heavy_rain": "అత్యంత భారీ వర్షం",
           "heatwave": "వడగాల్పులు", "severe_heatwave": "తీవ్ర వడగాల్పులు", "strong_wind": "బలమైన గాలులు", "gale": "తుఫాను గాలులు"},
    "hi": {"heavy_rain": "भारी वर्षा", "very_heavy_rain": "बहुत भारी वर्षा", "extremely_heavy_rain": "अत्यधिक भारी वर्षा",
           "heatwave": "लू", "severe_heatwave": "गंभीर लू", "strong_wind": "तेज़ हवा", "gale": "आंधी"},
}
# Three things a farmer should do NOW, per hazard.
ACTIONS = {
    "rain": {
        "en": ["Move cattle, seed and fertilizer bags to a safe, high place",
               "Do not cross flooded streams or low bridges",
               "Stop spraying and fertilizer; open the field drains"],
        "te": ["పశువులు, విత్తనాలు, ఎరువుల సంచులను సురక్షితమైన ఎత్తైన చోటికి తరలించండి",
               "వరద వాగులు, తక్కువ వంతెనలు దాటవద్దు",
               "పిచికారీ, ఎరువులు ఆపండి; పొలం కాలువలు తెరవండి"],
        "hi": ["पशु, बीज और खाद की बोरियाँ सुरक्षित ऊँची जगह पर ले जाएँ",
               "उफनते नाले या नीचे पुल पार न करें",
               "छिड़काव और खाद रोकें; खेत की नालियाँ खोलें"],
    },
    "heat": {
        "en": ["Irrigate in the evening; avoid field work from 12 to 3 pm",
               "Keep cattle in shade with plenty of water",
               "Drink water often; watch for signs of heat stroke"],
        "te": ["సాయంత్రం నీరు పెట్టండి; మధ్యాహ్నం 12 నుండి 3 వరకు పొలం పని చేయవద్దు",
               "పశువులను నీడలో ఉంచి, నీరు ఎక్కువగా ఇవ్వండి",
               "తరచూ నీరు తాగండి; వడదెబ్బ లక్షణాలు గమనించండి"],
        "hi": ["शाम को सिंचाई करें; दोपहर 12 से 3 बजे तक खेत में काम न करें",
               "पशुओं को छाँव में रखें और भरपूर पानी दें",
               "बार-बार पानी पिएँ; लू लगने के लक्षण देखें"],
    },
    "wind": {
        "en": ["Tie down sheds and roofs; secure loose items",
               "Support tall crops; delay harvesting",
               "Stay away from trees and power lines"],
        "te": ["షెడ్లు, పైకప్పులు కట్టివేయండి; వదులైన వస్తువులు భద్రపరచండి",
               "ఎత్తైన పంటలకు ఆధారం ఇవ్వండి; కోత వాయిదా వేయండి",
               "చెట్లు, విద్యుత్ తీగలకు దూరంగా ఉండండి"],
        "hi": ["शेड और छतें बाँधें; ढीला सामान सुरक्षित करें",
               "ऊँची फसलों को सहारा दें; कटाई टालें",
               "पेड़ों और बिजली के तारों से दूर रहें"],
    },
}
EXPECTED = {
    "en": "{gp}: {value} {unit} expected on {day}.",
    "te": "{gp}: {day} నాడు {value} {unit} అంచనా.",
    "hi": "{gp}: {day} को {value} {unit} अपेक्षित।",
}
TAP = {"en": "Open for what to do.", "te": "ఏం చేయాలో చూడటానికి తెరవండి.", "hi": "क्या करें, देखने के लिए खोलें।"}

CAP_SEVERITY = {"yellow": "Moderate", "orange": "Severe", "red": "Extreme"}
CAP_CERTAINTY = {"high": "Likely", "medium": "Possible", "low": "Unknown"}


def _num(v: float) -> str:
    r = round(float(v), 1)
    return str(int(r)) if r == int(r) else str(r)


def _classify(value: float | None, table: list) -> tuple[str, str] | None:
    if value is None:
        return None
    for threshold, level, event in table:
        if value >= threshold:
            return level, event
    return None


def alert_id(run: dict, panchayat_id: int, day: int, hazard: str) -> str:
    return f"{run['id']}.{run.get('revision', 0)}-{panchayat_id}-{day}-{hazard}"


def warnings_for_day(row: dict, gp: dict, run: dict) -> list[dict]:
    """Colour-coded warnings for one panchayat-day forecast row."""
    out = []
    checks = [("rain", row.get("rain_mm"), RAIN, "mm"), ("heat", row.get("tmax"), HEAT, "°C"),
              ("wind", row.get("wind_kmh"), WIND, "km/h")]
    for hazard, value, table, unit in checks:
        hit = _classify(value, table)
        if not hit:
            continue
        level, event = hit
        conf = row.get("confidence", "low")
        names = {lang: (gp.get(f"name_{lang}") if lang != "en" else None) or gp["name"] for lang in LEVEL_NAME}
        day_name = {lang: WEEKDAYS[lang][date_cls.fromisoformat(row["date"]).weekday()] for lang in LEVEL_NAME}
        title = {lang: f"{LEVEL_NAME[lang][level]} · {EVENT_NAME[lang][event]}" for lang in LEVEL_NAME}
        body = {
            lang: f"{EXPECTED[lang].format(gp=names[lang], value=_num(value), unit=unit, day=day_name[lang])} "
                  f"{ACTIONS[hazard][lang][0]}. {TAP[lang]}"
            for lang in LEVEL_NAME
        }
        out.append({
            "id": alert_id(run, gp["id"], row["day"], hazard),
            "run_id": run["id"],
            "panchayat_id": gp["id"],
            "panchayat": {"id": gp["id"], "name": gp["name"], "name_te": gp.get("name_te"), "name_hi": gp.get("name_hi"),
                          "lgd_code": gp.get("lgd_code"), "registered_farmers": gp.get("registered_farmers") or 0},
            "day": row["day"], "date": row["date"],
            "hazard": hazard, "event": event, "level": level,
            "value": round(float(value), 1), "unit": unit,
            "probability": row.get("rain_prob_10mm") if hazard == "rain" else None,
            "confidence": conf,
            "siren": RANK[level] >= RANK["orange"] and conf in ("high", "medium"),
            "title": title, "body": body,
            "actions": {lang: ACTIONS[hazard][lang] for lang in LEVEL_NAME},
            "cap": {"severity": CAP_SEVERITY[level], "certainty": CAP_CERTAINTY.get(conf, "Unknown")},
            "simulated": run.get("source") == "simulated",
        })
    return out


def sort_key(w: dict):
    return (-RANK[w["level"]], w["day"], -w["value"])


def block_warnings(ds, block_id: int, min_level: str = "yellow") -> tuple[list[dict], dict]:
    """All warnings for a block's latest run, most severe first. Returns (warnings, run)."""
    from app.services.forecast import block_bundle

    _, run, gps, _, pfc = block_bundle(ds, block_id)
    by_id = {g["id"]: g for g in gps}
    out = []
    for row in pfc:
        gp = by_id.get(row["panchayat_id"])
        if gp:
            out += [w for w in warnings_for_day(row, gp, run) if RANK[w["level"]] >= RANK[min_level]]
    return sorted(out, key=sort_key), run
