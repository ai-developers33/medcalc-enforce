"""Read a research question, note and optional calculator call from JSON on stdin."""
import argparse
import json
import sys

from medcalc.live import strict_json
from medcalc.release_policy import execute_reviewed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        request = strict_json(sys.stdin.read())
        decision = execute_reviewed(request["question"], request["note"], request.get("call"))
    except (ValueError, KeyError) as exc:
        parser.exit(2, f"Invalid JSON request: {exc}\n")
    print(json.dumps(decision, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
