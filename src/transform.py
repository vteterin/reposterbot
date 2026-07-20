"""Wholesale → retail text transformation.

Given a wholesale post from the source channel, produce the retail post text
(HTML-formatted for aiogram parse_mode='HTML') with:

  - price recalculated by formula, RUB with thin-space thousands separator
  - retail suffix block appended (with inline links)
  - original body preserved otherwise
"""
import re
from html import escape

from . import config

# Match "40 $" / "$40" / "40$" / "40 USD" / "40usd" — capture the number
_PRICE_RE = re.compile(
    r"""
    (?P<full>
        (?:\$\s*(?P<pre>\d+(?:[.,]\d+)?))       # $40  |  $40.5
        |
        (?:(?P<post>\d+(?:[.,]\d+)?)\s*(?:\$|USD|usd|\$USD))  # 40$ | 40 USD
    )
    """,
    re.VERBOSE,
)


def parse_wholesale_price(text: str) -> float | None:
    """Return the wholesale price in USD, or None if not found."""
    m = _PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group("pre") or m.group("post")
    return float(raw.replace(",", "."))


def detect_brand(text: str) -> str | None:
    """First non-empty line is treated as the brand line."""
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s
    return None


def is_exception_brand(brand: str | None) -> bool:
    if not brand:
        return False
    upper = brand.upper()
    return any(exc in upper for exc in config.EXCEPTION_BRANDS)


def calc_retail_rub(usd_price: float, usd_rub: float, exception: bool) -> int:
    """Apply the pricing formula and return rubles rounded to the nearest 100.

    Default:   X * 2 * rate * 1.1  +  (X * 0.2) * rate * 1.1
    Exception: X * 2 * rate * 1.1

    Uses half-up rounding (7 550 → 7 600, 7 549 → 7 500).
    """
    base = usd_price * 2 * usd_rub * 1.1
    if exception:
        total = base
    else:
        total = base + (usd_price * 0.2) * usd_rub * 1.1
    # Half-up rounding to nearest 100
    return int((total + 50) // 100) * 100


def format_rub(amount: int) -> str:
    """Format integer rubles with a thin-space (U+2009) thousands separator, ' ₽' suffix."""
    return f"{amount:,}".replace(",", " ") + " ₽"


def replace_price_in_text(text: str, rub_display: str) -> str:
    """Replace the first found USD price occurrence with the ruble display string.

    Keeps everything else (SALE❗️, description, materials, etc.) intact.
    """
    m = _PRICE_RE.search(text)
    if not m:
        return text
    return text[: m.start()] + rub_display + text[m.end():]


def build_retail_suffix_html() -> str:
    """Retail block appended to every crosspost. HTML-formatted."""
    lines = []
    for label, url in config.RETAIL_SUFFIX_LINES:
        if url:
            lines.append(f'<a href="{escape(url, quote=True)}">{escape(label)}</a>')
        else:
            lines.append(escape(label))
    lines.append("")  # blank line before footer
    lines.append(escape(config.RETAIL_SUFFIX_FOOTER))
    return "\n".join(lines)


def transform_text(wholesale_text: str, usd_rub: float) -> tuple[str, dict]:
    """Return (retail_html, meta).

    meta contains: brand, usd_price, rub_price, exception, transformed (bool)
    """
    brand = detect_brand(wholesale_text)
    usd_price = parse_wholesale_price(wholesale_text)
    exception = is_exception_brand(brand)

    if usd_price is None:
        # No price found — return original text + retail suffix unchanged
        html_body = escape(wholesale_text)
        html = html_body + "\n\n" + build_retail_suffix_html()
        return html, {
            "brand": brand, "usd_price": None, "rub_price": None,
            "exception": exception, "transformed": False,
        }

    rub_price = calc_retail_rub(usd_price, usd_rub, exception)
    rub_display = format_rub(rub_price)
    new_body = replace_price_in_text(wholesale_text, rub_display)
    html = escape(new_body) + "\n\n" + build_retail_suffix_html()
    return html, {
        "brand": brand, "usd_price": usd_price, "rub_price": rub_price,
        "exception": exception, "transformed": True,
    }
