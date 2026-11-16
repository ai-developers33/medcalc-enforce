"""Run one experimental calculation from a JSON object on stdin."""
import argparse
import json
import sys

from medcalc.live import strict_json
from medcalc.source_fallback import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note-only", action="store_true", help="Use explicit named source measurements alone")
    args = parser.parse_args()
    try:
        request = strict_json(sys.stdin.read())
        decision = execute(request["question"], request["note"], request.get("call"), use_proposal=not args.note_only)
    except (ValueError, KeyError) as exc:
        parser.exit(2, f"Invalid JSON request: {exc}\n")
    print(json.dumps(decision, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
