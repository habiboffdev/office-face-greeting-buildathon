from database import get_connection
from config import ORG_NAME

DEFAULT_TITLE = "Salom, {ism}!"
DEFAULT_SUBTITLE = "Rocusga xush kelibsiz!"
DEFAULT_BIRTHDAY_TITLE = "Tug'ilgan kuningiz bilan, {ism}!"
DEFAULT_BIRTHDAY_SUBTITLE = "{tashkilot} jamoasi sizni tabriklaydi!"
DEFAULT_VIP_TITLE = "Hurmatli mehmon, {ism}!"
DEFAULT_VIP_SUBTITLE = "{tashkilot} jamoasi sizni qutlaydi — xush kelibsiz!"


def _migrate_columns(conn) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(greeting_settings)").fetchall()}
    if "birthday_title_template" not in cols:
        conn.execute(
            "ALTER TABLE greeting_settings ADD COLUMN birthday_title_template TEXT"
        )
    if "birthday_subtitle_template" not in cols:
        conn.execute(
            "ALTER TABLE greeting_settings ADD COLUMN birthday_subtitle_template TEXT"
        )
    if "vip_title_template" not in cols:
        conn.execute("ALTER TABLE greeting_settings ADD COLUMN vip_title_template TEXT")
    if "vip_subtitle_template" not in cols:
        conn.execute("ALTER TABLE greeting_settings ADD COLUMN vip_subtitle_template TEXT")
    if "vip_title_repeat_template" not in cols:
        conn.execute(
            "ALTER TABLE greeting_settings ADD COLUMN vip_title_repeat_template TEXT"
        )
    if "vip_subtitle_repeat_template" not in cols:
        conn.execute(
            "ALTER TABLE greeting_settings ADD COLUMN vip_subtitle_repeat_template TEXT"
        )


def _ensure_row(conn) -> None:
    row = conn.execute("SELECT id FROM greeting_settings WHERE id = 1").fetchone()
    if not row:
        conn.execute(
            """
            INSERT INTO greeting_settings (
                id, title_template, subtitle_template, use_smart_rules,
                birthday_title_template, birthday_subtitle_template,
                vip_title_template, vip_subtitle_template,
                vip_title_repeat_template, vip_subtitle_repeat_template
            )
            VALUES (1, ?, ?, 0, ?, ?, ?, ?, '', '')
            """,
            (
                DEFAULT_TITLE,
                DEFAULT_SUBTITLE,
                DEFAULT_BIRTHDAY_TITLE,
                DEFAULT_BIRTHDAY_SUBTITLE,
                DEFAULT_VIP_TITLE,
                DEFAULT_VIP_SUBTITLE,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE greeting_settings
            SET birthday_title_template = COALESCE(birthday_title_template, ?),
                birthday_subtitle_template = COALESCE(birthday_subtitle_template, ?),
                vip_title_template = COALESCE(
                    NULLIF(TRIM(COALESCE(vip_title_template, '')), ''), ?
                ),
                vip_subtitle_template = COALESCE(
                    NULLIF(TRIM(COALESCE(vip_subtitle_template, '')), ''), ?
                )
            WHERE id = 1
            """,
            (
                DEFAULT_BIRTHDAY_TITLE,
                DEFAULT_BIRTHDAY_SUBTITLE,
                DEFAULT_VIP_TITLE,
                DEFAULT_VIP_SUBTITLE,
            ),
        )


def get_greeting_settings() -> dict:
    with get_connection() as conn:
        _migrate_columns(conn)
        _ensure_row(conn)
        row = conn.execute(
            """
            SELECT title_template, subtitle_template, use_smart_rules,
                   birthday_title_template, birthday_subtitle_template,
                   vip_title_template, vip_subtitle_template,
                   vip_title_repeat_template, vip_subtitle_repeat_template
            FROM greeting_settings WHERE id = 1
            """
        ).fetchone()
    return {
        "title_template": row["title_template"],
        "subtitle_template": row["subtitle_template"],
        "use_smart_rules": bool(row["use_smart_rules"]),
        "birthday_title_template": row["birthday_title_template"] or DEFAULT_BIRTHDAY_TITLE,
        "birthday_subtitle_template": row["birthday_subtitle_template"]
        or DEFAULT_BIRTHDAY_SUBTITLE,
        "vip_title_template": row["vip_title_template"] or DEFAULT_VIP_TITLE,
        "vip_subtitle_template": row["vip_subtitle_template"] or DEFAULT_VIP_SUBTITLE,
        "vip_title_repeat_template": (row["vip_title_repeat_template"] or "").strip(),
        "vip_subtitle_repeat_template": (row["vip_subtitle_repeat_template"] or "").strip(),
    }


def save_greeting_settings(
    title_template: str,
    subtitle_template: str,
    use_smart_rules: bool = False,
    birthday_title_template: str | None = None,
    birthday_subtitle_template: str | None = None,
    vip_title_template: str | None = None,
    vip_subtitle_template: str | None = None,
    vip_title_repeat_template: str | None = None,
    vip_subtitle_repeat_template: str | None = None,
) -> dict:
    title_template = title_template.strip() or DEFAULT_TITLE
    subtitle_template = subtitle_template.strip() or DEFAULT_SUBTITLE
    b_title = (birthday_title_template or "").strip() or DEFAULT_BIRTHDAY_TITLE
    b_sub = (birthday_subtitle_template or "").strip() or DEFAULT_BIRTHDAY_SUBTITLE
    v_title = (vip_title_template or "").strip() or DEFAULT_VIP_TITLE
    v_sub = (vip_subtitle_template or "").strip() or DEFAULT_VIP_SUBTITLE
    v_tr = (vip_title_repeat_template or "").strip()
    v_sr = (vip_subtitle_repeat_template or "").strip()
    with get_connection() as conn:
        _migrate_columns(conn)
        _ensure_row(conn)
        conn.execute(
            """
            UPDATE greeting_settings
            SET title_template = ?, subtitle_template = ?, use_smart_rules = ?,
                birthday_title_template = ?, birthday_subtitle_template = ?,
                vip_title_template = ?, vip_subtitle_template = ?,
                vip_title_repeat_template = ?, vip_subtitle_repeat_template = ?
            WHERE id = 1
            """,
            (
                title_template,
                subtitle_template,
                int(use_smart_rules),
                b_title,
                b_sub,
                v_title,
                v_sub,
                v_tr,
                v_sr,
            ),
        )
    return get_greeting_settings()


def _apply_placeholders(text: str, full_name: str) -> str:
    first = full_name.strip().split()[0] if full_name.strip() else full_name
    replacements = {
        "{ism}": full_name,
        "{name}": full_name,
        "{full_name}": full_name,
        "{ism_qisqa}": first,
        "{first_name}": first,
        "{tashkilot}": ORG_NAME,
        "{org}": ORG_NAME,
    }
    for key, val in replacements.items():
        text = text.replace(key, val)
    return text


def apply_templates(full_name: str) -> dict[str, str]:
    settings = get_greeting_settings()
    return {
        "title": _apply_placeholders(settings["title_template"], full_name),
        "subtitle": _apply_placeholders(settings["subtitle_template"], full_name),
    }


def apply_birthday_templates(full_name: str) -> dict[str, str]:
    settings = get_greeting_settings()
    return {
        "title": _apply_placeholders(settings["birthday_title_template"], full_name),
        "subtitle": _apply_placeholders(settings["birthday_subtitle_template"], full_name),
    }


def apply_vip_greeting(full_name: str, visits_today: int) -> dict[str, str]:
    """visits_today: shu kun (UTC) ichidagi tashriflar soni, 1 = birinchi, 2+ = qayta."""
    settings = get_greeting_settings()
    is_repeat = visits_today > 1
    if is_repeat:
        raw_t = settings["vip_title_repeat_template"]
        raw_s = settings["vip_subtitle_repeat_template"]
        t = raw_t or settings["vip_title_template"]
        s = raw_s or settings["vip_subtitle_template"]
    else:
        t = settings["vip_title_template"]
        s = settings["vip_subtitle_template"]
    return {
        "title": _apply_placeholders(t, full_name),
        "subtitle": _apply_placeholders(s, full_name),
    }
