"""Contextual greeting text builder."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Optional

TIME_BAND_TEMPLATES = {
    "en": {
        "morning": "Good morning, {name}!",
        "afternoon": "Good afternoon, {name}!",
        "evening": "Good evening, {name}!",
        "late": "Still here, {name}?",
    },
    "uz": {
        "morning": "Xayrli tong, {name}!",
        "afternoon": "Xayrli kun, {name}!",
        "evening": "Xayrli kech, {name}!",
        "late": "Xush kelibsiz, {name}!",
    },
    "ru": {
        "morning": "Dobroye utro, {name}!",
        "afternoon": "Dobryy den, {name}!",
        "evening": "Dobryy vecher, {name}!",
        "late": "Dobro pozhalovat, {name}!",
    },
}

BIRTHDAY_TEMPLATES = {
    "en": "Happy birthday, {name}!",
    "uz": "Tug'ilgan kuningiz muborak, {name}!",
    "ru": "S dnem rozhdeniya, {name}!",
}

DEFAULT_FALLBACKS = {
    "en": "Welcome, {name}!",
    "uz": "Xush kelibsiz, {name}!",
    "ru": "Dobro pozhalovat, {name}!",
}
DEFAULT_FALLBACK = DEFAULT_FALLBACKS["en"]


def band_for_hour(hour: int) -> str:
    """Return the time-of-day band for an hour in 0..23."""
    if hour >= 22 or hour < 5:
        return "late"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    return "evening"


def holiday_for_date(date_iso: str, holidays: dict[str, str] | None) -> Optional[str]:
    """Match the MM-DD portion of date_iso against holidays."""
    if not holidays or len(date_iso) < 10:
        return None
    return holidays.get(date_iso[5:10])


def birthday_for_date(date_iso: str, birthday: str | None) -> bool:
    """Return True if birthday (MM-DD) matches date_iso."""
    return bool(birthday and len(date_iso) >= 10 and date_iso[5:10] == birthday)


def _normalize_language(language: str | None) -> str:
    value = (language or "en").strip().lower()
    return value if value in TIME_BAND_TEMPLATES else "en"


def _apply_flavor(line: str, flavor: str) -> str:
    if "{name}" in flavor:
        return f"{line} {flavor}"
    return f"{line} - {flavor}"


def build_greeting(
    name: str,
    *,
    now: datetime | None = None,
    holidays: dict[str, str] | None = None,
    flavors: list[str] | None = None,
    language: str | None = None,
    birthday: str | None = None,
    custom_message: str | None = None,
    rng: random.Random | None = None,
) -> str:
    """Return the overlay line for name."""
    safe_name = name or "friend"
    when = now if now is not None else datetime.now()
    when_iso = when.isoformat()
    lang = _normalize_language(language)

    headline_template: Optional[str] = None
    if birthday_for_date(when_iso, birthday):
        headline_template = BIRTHDAY_TEMPLATES.get(lang, BIRTHDAY_TEMPLATES["en"])

    holiday = holiday_for_date(when_iso, holidays)
    if headline_template is None and holiday:
        headline_template = holiday + ", {name}!" if "{name}" not in holiday else holiday

    if headline_template is None:
        headline_template = TIME_BAND_TEMPLATES.get(lang, TIME_BAND_TEMPLATES["en"]).get(
            band_for_hour(when.hour),
            DEFAULT_FALLBACKS.get(lang, DEFAULT_FALLBACK),
        )

    line = headline_template.format(name=safe_name)

    if custom_message:
        if "{name}" in custom_message:
            return f"{line} {custom_message.format(name=safe_name)}"
        return _apply_flavor(line, custom_message)

    if flavors:
        picker = rng if rng is not None else random.Random()
        flavor = picker.choice(list(flavors))
        if flavor:
            if "{name}" in flavor:
                line = f"{line} {flavor.format(name=safe_name)}"
            else:
                line = _apply_flavor(line, flavor)

    return line
