"""Wholesale → retail text transformation.

Given a wholesale post from the source channel (already HTML-formatted with
Telegram entities like <s>, <b>, <a>), produce the retail post text with:

  - every USD price recalculated by formula, in rubles with a thin-space
    thousands separator (including struck-through prices — the <s> tags stay)
  - retail suffix block appended (with inline links)
  - all other formatting preserved verbatim
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
    """Return the FIRST wholesale price in USD found in text, or None. Retained for backwards compat."""
    m = _PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group("pre") or m.group("post")
    return float(raw.replace(",", "."))


def find_all_prices(text: str) -> list[float]:
    """Return all USD prices found in text, in order of appearance."""
    out = []
    for m in _PRICE_RE.finditer(text):
        raw = m.group("pre") or m.group("post")
        out.append(float(raw.replace(",", ".")))
    return out


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
    return int((total + 50) // 100) * 100


def format_rub(amount: int) -> str:
    """Format integer rubles with a thin-space (U+2009) thousands separator, ' ₽' suffix."""
    return f"{amount:,}".replace(",", " ") + " ₽"


def replace_all_prices(text: str, usd_rub: float, exception: bool) -> tuple[str, list[tuple[float, int]]]:
    """Replace every USD price in text with the recalculated ruble display.

    Returns (new_text, list_of_(usd, rub)_pairs).
    """
    conversions: list[tuple[float, int]] = []

    def _repl(m: re.Match) -> str:
        raw = m.group("pre") or m.group("post")
        usd = float(raw.replace(",", "."))
        rub = calc_retail_rub(usd, usd_rub, exception)
        conversions.append((usd, rub))
        return format_rub(rub)

    new_text = _PRICE_RE.sub(_repl, text)
    return new_text, conversions


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


def transform_text(wholesale_html: str, usd_rub: float) -> tuple[str, dict]:
    """Transform a wholesale post (as HTML text with Telegram entities) into retail HTML.

    Returns (retail_html, meta).
    meta contains: brand, usd_prices, rub_prices, exception, transformed (bool)
    """
    brand = detect_brand(wholesale_html)
    exception = is_exception_brand(brand)

    new_body, conversions = replace_all_prices(wholesale_html, usd_rub, exception)
    html = new_body + "\n\n" + build_retail_suffix_html()

    return html, {
        "brand": brand,
        "usd_prices": [c[0] for c in conversions],
        "rub_prices": [c[1] for c in conversions],
        "exception": exception,
        "transformed": bool(conversions),
    }
