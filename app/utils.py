"""Dates, fuseau horaire et formatage à la française."""
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context
from markupsafe import Markup, escape

from .constants import MONTHS_FR, WEEKDAYS_FR

DEFAULT_TZ = "Africa/Casablanca"


def get_tz() -> ZoneInfo:
    name = current_app.config.get("TIMEZONE", DEFAULT_TZ) if has_app_context() else DEFAULT_TZ
    return ZoneInfo(name)


def utcnow() -> datetime:
    """Horodatage technique : UTC naïf (created_at, updated_at…)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def now_local() -> datetime:
    """Heure locale marocaine (naïve)."""
    return datetime.now(get_tz()).replace(tzinfo=None)


def today_local() -> date:
    return now_local().date()


def utc_to_local(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(get_tz()).replace(tzinfo=None)


def parse_date(value) -> date | None:
    """Accepte JJ/MM/AAAA, AAAA-MM-JJ ou un objet date ; renvoie None si invalide."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(value) -> time | None:
    if value is None:
        return None
    if isinstance(value, time):
        return value
    text = str(value).strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%Hh%M", "%Hh"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def parse_decimal(value) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def safe_next(target: str | None, fallback: str) -> str:
    """N'accepte que des chemins locaux comme cible de redirection."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return fallback


# --- Filtres Jinja -----------------------------------------------------------

def fr_date(value, default="—") -> str:
    if isinstance(value, str):
        value = parse_date(value)
    if not value:
        return default
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d/%m/%Y")


def fr_time(value) -> str:
    if not value:
        return ""
    return value.strftime("%H:%M")


def fr_datetime(value, default="—") -> str:
    if not value:
        return default
    return value.strftime("%d/%m/%Y %H:%M")


def fr_timestamp(value, default="—") -> str:
    """Horodatage UTC stocké → heure locale affichée."""
    return fr_datetime(utc_to_local(value), default)


def fr_long_date(value) -> str:
    if not value:
        return ""
    return f"{WEEKDAYS_FR[value.weekday()]} {value.day} {MONTHS_FR[value.month - 1]} {value.year}"


def fr_number(value, decimals=0) -> str:
    if value is None:
        return "—"
    formatted = f"{float(value):,.{decimals}f}"
    # séparateur de milliers : espace fine insécable ; décimales : virgule
    return formatted.replace(",", " ").replace(".", ",")


def money(value, currency="MAD") -> str:
    if value is None:
        return "—"
    label = {"MAD": "MAD", "EUR": "€"}.get(currency or "MAD", currency or "")
    decimals = 0 if Decimal(value) == Decimal(value).to_integral_value() else 2
    return f"{fr_number(value, decimals)}\xa0{label}".strip()


def file_size(value) -> str:
    if not value:
        return "—"
    if value < 1024:
        return f"{value} o"
    if value < 1024 * 1024:
        return f"{fr_number(value / 1024, 0)} Ko"
    return f"{fr_number(value / (1024 * 1024), 1)} Mo"


def nl2br(value) -> Markup:
    if not value:
        return Markup("")
    return Markup("<br>".join(escape(line) for line in str(value).splitlines()))


def register_template_filters(app):
    app.add_template_filter(fr_date, "fr_date")
    app.add_template_filter(fr_time, "fr_time")
    app.add_template_filter(fr_datetime, "fr_datetime")
    app.add_template_filter(fr_timestamp, "fr_timestamp")
    app.add_template_filter(fr_long_date, "fr_long_date")
    app.add_template_filter(fr_number, "fr_number")
    app.add_template_filter(money, "money")
    app.add_template_filter(file_size, "file_size")
    app.add_template_filter(nl2br, "nl2br")
