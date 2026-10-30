"""Check the documented platform contract without importing optional dependencies."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.platforms import require_supported_platform


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-unsupported", action="store_true")
    args = parser.parse_args()
    try:
        require_supported_platform()
    except RuntimeError as exc:
        assert args.expect_unsupported and "Windows is unsupported" in str(exc)
        print(str(exc))
    else:
        assert not args.expect_unsupported, "Unsupported platform was accepted"
        print("POSIX execution supported")


if __name__ == "__main__":
    main()
