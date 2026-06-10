from __future__ import annotations

import re
from collections.abc import Iterable

_CODE_SPLIT_RE = re.compile(r"[,\n;|]+")


def normalize_code_list(raw: str | None) -> list[str]:
    """Split a raw field into unique uppercase codes, preserving order."""
    if not raw:
        return []
    tokens: list[str] = []
    for chunk in _CODE_SPLIT_RE.split(str(raw).upper()):
        value = chunk.strip()
        if value:
            tokens.append(value)
    return _dedupe(tokens)


def split_primary_and_alternates(primary_raw: str | None, alt_raw: str | None = None) -> tuple[str, str]:
    """Keep the first code as the main reference and store the rest as alternates."""
    primary_tokens = normalize_code_list(primary_raw)
    primary = primary_tokens[0] if primary_tokens else ""
    alternates: list[str] = []
    seen = {primary} if primary else set()

    for token in primary_tokens[1:] + normalize_code_list(alt_raw):
        if token and token not in seen:
            seen.add(token)
            alternates.append(token)
    return primary, ", ".join(alternates)


def join_codes(codes: Iterable[str]) -> str:
    """Render a normalized, readable alternate-code list for the UI."""
    return ", ".join(_dedupe(code.strip().upper() for code in codes if code))


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output
