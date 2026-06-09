"""ASTM E1394 record parsing helpers (backend).

The gateway forwards a raw ASTM message as newline-joined record lines. This
module splits those lines into fields/components so device profiles can map
them onto the shared :class:`~lab_analyzer_device.hl7.extractor.ORUData`.
"""

from __future__ import annotations

# Default E1394 delimiters: field '|', repeat '\', component '^', escape '&'.
DEFAULT_FIELD = "|"
DEFAULT_REPEAT = "\\"
DEFAULT_COMPONENT = "^"
DEFAULT_ESCAPE = "&"


def record_type(line: str) -> str:
    """Return the single-letter record type (H, P, O, R, C, L, Q, …)."""
    return line[:1].upper() if line else ""


def split_lines(raw_message: str) -> list[str]:
    """Split a raw ASTM message into non-empty record lines.

    Accepts ``\\r``, ``\\n`` or ``\\r\\n`` separators (the gateway normalises
    to ``\\n``) and strips any residual framing whitespace.
    """
    normalized = raw_message.replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in normalized.split("\n") if line.strip()]


def detect_delimiters(header_line: str) -> tuple[str, str, str, str]:
    """Extract ``(field, repeat, component, escape)`` from a header (``H``) record."""
    if len(header_line) < 2 or record_type(header_line) != "H":
        return (DEFAULT_FIELD, DEFAULT_REPEAT, DEFAULT_COMPONENT, DEFAULT_ESCAPE)
    field_delim = header_line[1]
    parts = header_line.split(field_delim)
    if len(parts) > 1 and len(parts[1]) >= 3:
        return (field_delim, parts[1][0], parts[1][1], parts[1][2])
    return (field_delim, DEFAULT_REPEAT, DEFAULT_COMPONENT, DEFAULT_ESCAPE)


def fields(line: str, field_delim: str = DEFAULT_FIELD) -> list[str]:
    """Split a record line into its top-level fields."""
    return line.split(field_delim)


def field_at(parts: list[str], index: int) -> str:
    """Return ``parts[index]`` stripped, or an empty string when out of range."""
    if 0 <= index < len(parts):
        return parts[index].strip()
    return ""


def components(value: str, component_delim: str = DEFAULT_COMPONENT) -> list[str]:
    """Split a field value into components."""
    return value.split(component_delim)


def component_at(value: str, index: int, component_delim: str = DEFAULT_COMPONENT) -> str:
    """Return the *index*-th component of *value*, or an empty string."""
    comps = components(value, component_delim)
    if 0 <= index < len(comps):
        return comps[index].strip()
    return ""
