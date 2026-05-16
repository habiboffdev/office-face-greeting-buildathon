from datetime import datetime, timezone

from config import (
    GREETING_ABSENCE_MONTH_DAYS,
    GREETING_ABSENCE_WEEK_DAYS,
    ORG_NAME,
    ORG_TAGLINE,
)
from greeting_settings import (
    apply_birthday_templates,
    apply_templates,
    apply_vip_greeting,
    get_greeting_settings,
)


def _first_name(full_name: str) -> str:
    return full_name.strip().split()[0] if full_name.strip() else full_name


def expand_placeholders(text: str, full_name: str) -> str:
    """Asoschilar / admin shablonlari: {ism}, {ism_qisqa}, {tashkilot}, ..."""
    first = _first_name(full_name)
    return (
        text.replace("{ism}", full_name)
        .replace("{ism_qisqa}", first)
        .replace("{tashkilot}", ORG_NAME)
        .replace("{name}", full_name)
        .replace("{first_name}", first)
        .replace("{org}", ORG_NAME)
    )


def _expand_tpl(text: str, full_name: str) -> str:
    return expand_placeholders(text, full_name)


# Uzoq yo‘qlik (hafta / oy) — standart matnlar; keyin admin shabloniga chiqarish mumkin
_MONTH_TITLE = "Salom, {ism}! Biz sizni bir oyga yaqin ko'rmagan edik."
_MONTH_SUB = "{tashkilot}ga qaytganingizdan juda xursandmiz — xush kelibsiz!"
_WEEK_TITLE = "Salom, {ism_qisqa}! Bir haftadan beri sizni bu yerda ko'rmagan edik."
_WEEK_SUB = "Sizni sog'indik. {tashkilot} jamoasi sizni kutgan edi."


def _parse_birthday_md(birthday: str | None) -> tuple[int, int] | None:
    """Qaytaradi (oy, kun) yoki None."""
    if not birthday or not birthday.strip():
        return None
    raw = birthday.strip()[:10]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(raw, fmt).date()
            return d.month, d.day
        except ValueError:
            continue
    if len(raw) >= 10 and raw[4] == "-":
        try:
            parts = raw.split("-")
            return int(parts[1]), int(parts[2])
        except (ValueError, IndexError):
            pass
    return None


def _is_birthday_today(birthday: str | None) -> bool:
    md = _parse_birthday_md(birthday)
    if not md:
        return False
    today = datetime.now(timezone.utc).date()
    return md == (today.month, today.day)


def _is_first_visit_today(last_seen_at: str | None) -> bool:
    """Bugun ofisga birinchi marta kirish (oldingi tashrif boshqa kun bo'lgan yoki umuman yo'q)."""
    today = datetime.now(timezone.utc).date()
    if not last_seen_at:
        return True
    try:
        last = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return last.date() < today
    except ValueError:
        return True


def _parse_last_seen(last_seen_at: str | None) -> datetime | None:
    if not last_seen_at:
        return None
    try:
        last = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
        if last.tzinfo is None:
            return last.replace(tzinfo=timezone.utc)
        return last
    except ValueError:
        return None


def _days_since_last_visit(last_seen_at: str | None, now: datetime) -> int | None:
    """Oxirgi tashrifdan to'liq kunlar (bugungi kirish OLDINGI tashrif vaqti bo'yicha)."""
    last = _parse_last_seen(last_seen_at)
    if not last:
        return None
    return (now - last).days


def _time_based_greeting(full_name: str, subtitle: str) -> dict[str, str]:
    """Soat bo'yicha: tong / kun / kech / tun."""
    now = datetime.now(timezone.utc)
    h = now.hour
    if 5 <= h < 12:
        return {"title": _expand_tpl("Xayrli tong, {ism_qisqa}!", full_name), "subtitle": subtitle}
    if 12 <= h < 17:
        return {"title": _expand_tpl("Xayrli kun, {ism_qisqa}!", full_name), "subtitle": subtitle}
    if 17 <= h < 22:
        return {"title": _expand_tpl("Xayrli kech, {ism_qisqa}!", full_name), "subtitle": subtitle}
    if h >= 22 or h < 5:
        return {"title": _expand_tpl("Xayrli tun, {ism_qisqa}!", full_name), "subtitle": subtitle}
    return {"title": f"Salom, {full_name}!", "subtitle": subtitle}


def _smart_greeting(
    full_name: str,
    total_visits: int,
    last_seen_at: str | None,
) -> dict[str, str]:
    """
    Oxirgi tashrif (person_id bo'yicha DB dagi oldingi last_seen) asosida.
    Ko'p tashriflar: hafta / oy yo'qlik + soat bo'yicha salom.
    VIP alohida build_greeting da qayta ishlanadi.
    """
    now = datetime.now(timezone.utc)
    first = _first_name(full_name)
    subtitle = ORG_TAGLINE

    if total_visits <= 1:
        return {"title": f"Salom, {full_name}!", "subtitle": subtitle}

    days_away = _days_since_last_visit(last_seen_at, now)
    last = _parse_last_seen(last_seen_at)

    # Bir oy / bir hafta yo'qlik (shu tashrifdan OLDINGI tashrifga qarab)
    if days_away is not None:
        if days_away >= GREETING_ABSENCE_MONTH_DAYS:
            return {
                "title": _expand_tpl(_MONTH_TITLE, full_name),
                "subtitle": _expand_tpl(_MONTH_SUB, full_name),
            }
        if days_away >= GREETING_ABSENCE_WEEK_DAYS:
            return {
                "title": _expand_tpl(_WEEK_TITLE, full_name),
                "subtitle": _expand_tpl(_WEEK_SUB, full_name),
            }

    if last and last.date() == now.date() and total_visits > 1:
        return {"title": f"Salom yana, {first}!", "subtitle": subtitle}

    if total_visits >= 20:
        return {
            "title": f"Salom, {first}!",
            "subtitle": f"Yana {ORG_NAME}da ko'rishganimizdan xursandmiz!",
        }

    return _time_based_greeting(full_name, subtitle)


def build_greeting(
    full_name: str,
    total_visits: int,
    last_seen_at: str | None,
    is_vip: bool = False,
    birthday: str | None = None,
    visits_today: int | None = None,
) -> dict[str, str | bool]:
    if _is_birthday_today(birthday) and _is_first_visit_today(last_seen_at):
        return {**apply_birthday_templates(full_name), "is_birthday": True}

    if is_vip:
        vt = visits_today if visits_today is not None else 1
        return {**apply_vip_greeting(full_name, vt), "is_birthday": False}

    settings = get_greeting_settings()
    if settings.get("use_smart_rules"):
        out = _smart_greeting(full_name, total_visits, last_seen_at)
    else:
        out = apply_templates(full_name)
    return {**out, "is_birthday": False}
