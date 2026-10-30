"""Platform support for the POSIX experiment execution lock."""

from __future__ import annotations

import os


def require_supported_platform() -> None:
    """Reject unsupported execution before creating a job or submitting work."""
    if os.name != "posix":
        raise RuntimeError(
            "Research execution requires POSIX file locking (Linux or macOS); "
            "Windows is unsupported. Use WSL2 or a Linux environment."
        )
