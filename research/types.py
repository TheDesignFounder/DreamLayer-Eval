"""Shared types for extensible schema-1 JSON records and local file locators.

JSON objects allow additional versioned fields; runtime contracts and the packaged
JSON Schemas validate their required structure. Third-party model/transport objects
remain typed at adapter boundaries without importing optional ML libraries.
"""

from pathlib import Path
from typing import Any, TypeAlias

JsonObject: TypeAlias = dict[str, Any]
PathLike: TypeAlias = str | Path
