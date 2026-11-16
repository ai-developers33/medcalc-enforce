"""Unified v0.5 CLI entry point (`medcalc-enforce`) reading JSON from stdin.

Supports all 16 calculators, stateful paragraph/section discourse checks,
output-unit normalization, optional `--note-only` mode, and chained multi-tool tokens.
"""
import argparse
import json
import sys

from medcalc.discourse_guard import execute_v05
from medcalc.live import strict_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note-only", action="store_true", help="Ignore model proposal and use discourse-clean named measurements only")
    args = parser.parse_args()
    try:
        request = strict_json(sys.stdin.read())
        decision = execute_v05(
            request["question"],
            request["note"],
            request.get("call"),
            use_proposal=not args.note_only,
            chained_tokens=request.get("chained_tokens"),
        )
    except (ValueError, KeyError) as exc:
        parser.exit(2, f"Invalid JSON request: {exc}\n")
    print(json.dumps(decision, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
