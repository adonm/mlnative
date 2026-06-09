"""Shared style allowlist for example servers."""

from mlnative import MlnativeError

STYLES = {
    "liberty": "https://tiles.openfreemap.org/styles/liberty",
    "positron": "https://tiles.openfreemap.org/styles/positron",
    "dark": "https://tiles.openfreemap.org/styles/dark-matter",
}

DEFAULT_STYLE_ID = "liberty"


def resolve_style(style_id: str) -> str:
    """Return a known style URL for a public example style ID."""
    try:
        return STYLES[style_id]
    except KeyError as e:
        allowed = ", ".join(sorted(STYLES))
        raise MlnativeError(f"Unknown style '{style_id}'. Allowed styles: {allowed}") from e
