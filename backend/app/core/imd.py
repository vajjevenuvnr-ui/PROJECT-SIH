"""IMD terminology shared by the API: rainfall categories, alert thresholds, source labels."""

from __future__ import annotations

from dataclasses import dataclass

# IMD daily rainfall categories (mm/day). Lower bound inclusive.
RAIN_CATEGORIES: list[tuple[float, str, str]] = [
    (0.0, "no_rain", "No rain"),
    (0.1, "very_light", "Very light rain"),
    (2.5, "light", "Light rain"),
    (15.6, "moderate", "Moderate rain"),
    (64.5, "heavy", "Heavy rain"),
    (115.6, "very_heavy", "Very heavy rain"),
    (204.5, "extremely_heavy", "Extremely heavy rain"),
]


def rain_category(mm: float | None) -> dict:
    """IMD category for a daily rainfall amount."""
    mm = mm or 0.0
    key, label = RAIN_CATEGORIES[0][1], RAIN_CATEGORIES[0][2]
    for lower, k, lbl in RAIN_CATEGORIES:
        if mm >= lower:
            key, label = k, lbl
    return {"key": key, "label": label}


# Alert thresholds used for panchayat banners.
RAIN_PROB_ALERT = 0.60  # P(rain > 10 mm) that triggers a watch
HEAVY_RAIN_MM = 64.5  # IMD "heavy rain"
HEAT_WATCH_C = 40.0  # plains; departure-from-normal criteria need climatology (Phase 7)
HEAT_WARNING_C = 45.0
WIND_WATCH_KMH = 30.0
WIND_WARNING_KMH = 40.0


@dataclass
class Alert:
    type: str  # rain | heat | wind
    severity: str  # watch | warning
    day: int
    date: str
    title: str
    detail: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def alerts_for_day(row: dict) -> list[Alert]:
    """Agronomic 'watch' for one panchayat-day: rain above 10 mm likely (affects spraying/sowing).

    Heavy rain, heat and wind are covered by the IMD colour-coded warnings in
    app/services/warnings.py (Yellow/Orange/Red), so they are not repeated here.
    """
    out: list[Alert] = []
    day, date = row["day"], row["date"]
    rain, p10 = row.get("rain_mm") or 0.0, row.get("rain_prob_10mm") or 0.0
    if rain < HEAVY_RAIN_MM and p10 >= RAIN_PROB_ALERT:
        out.append(Alert("rain", "watch", day, date, "Rain above 10 mm likely",
                         f"{round(p10 * 100)}% chance of >10 mm; about {rain:g} mm expected"))
    return out


SOURCE_LABELS = {
    "openmeteo-imd-format": "Source: Open-Meteo (IMD-format demo feed)",
    "imd": "Source: IMD block forecast",
    "replay": "Replay of a past event (archived forecast)",
    "seed": "Synthetic demo data",
    "simulated": "Simulated extreme event (demo, not a real forecast)",
}


def source_label(source: str | None) -> str:
    return SOURCE_LABELS.get(source or "", source or "Unknown source")


# Map API variable names to forecast columns and units.
VARIABLES: dict[str, dict] = {
    "rain": {"column": "rain_mm", "block_column": "rain_mm", "unit": "mm", "label": "Rain"},
    "tmax": {"column": "tmax", "block_column": "tmax", "unit": "°C", "label": "Tmax"},
    "tmin": {"column": "tmin", "block_column": "tmin", "unit": "°C", "label": "Tmin"},
    "rh": {"column": "rh", "block_column": None, "unit": "%", "label": "RH"},
    "wind": {"column": "wind_kmh", "block_column": "wind_kmh", "unit": "km/h", "label": "Wind"},
}


def block_value(block_row: dict, var: str) -> float | None:
    """Block value for a variable. RH is the mean of the bulletin's RH max/min."""
    if var == "rh":
        if block_row.get("rh_max") is None or block_row.get("rh_min") is None:
            return None
        return round((block_row["rh_max"] + block_row["rh_min"]) / 2, 1)
    return block_row.get(VARIABLES[var]["block_column"])
