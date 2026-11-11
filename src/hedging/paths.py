"""Locate a research checkout without depending on its folder name or the course."""

import os
from pathlib import Path
import tomllib


_PROJECT_NAME = "extreme-observation-hedging"


def _find_root(start: Path) -> Path | None:
    start = start.expanduser().resolve()
    if start.is_file():
        start = start.parent
    for candidate in (start, *start.parents):
        marker = candidate / "pyproject.toml"
        if not marker.is_file():
            continue
        try:
            with marker.open("rb") as stream:
                metadata = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if metadata.get("project", {}).get("name") == _PROJECT_NAME:
            return candidate
    return None


def project_root(start: str | Path | None = None) -> Path:
    """Find the checkout by project metadata, not a hard-coded directory name.

    With no explicit start, search the working directory and then this module's
    source location. The latter supports an editable install used from outside
    the research folder. An explicit start never falls back to another checkout.
    """
    roots = (Path(start),) if start is not None else (Path.cwd(), Path(__file__))
    for location in roots:
        found = _find_root(location)
        if found is not None:
            return found
    raise FileNotFoundError(
        "Cannot locate the extreme-observation-hedging checkout. "
        "Run from its directory or install it in editable mode."
    )


def data_root(start: str | Path | None = None) -> Path:
    """Return the data location without creating it or reading credentials.

    HEDGE_DATA_DIR may select an absolute external data directory. Relative
    overrides are rejected so notebook working directories cannot change the
    meaning of a configured data path.
    """
    override = os.environ.get("HEDGE_DATA_DIR")
    if override:
        location = Path(override).expanduser()
        if not location.is_absolute():
            raise ValueError("HEDGE_DATA_DIR must be an absolute path.")
        return location.resolve()
    return project_root(start) / "data"
