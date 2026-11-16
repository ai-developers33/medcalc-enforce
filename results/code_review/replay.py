"""Run independent synthetic input checks through the frozen public CLI."""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def command_line_reply(payload, entry):
    proc = subprocess.run(
        [sys.executable, str(PROJECT / entry)],
        cwd=PROJECT,
        input=payload,
        text=True,
        capture_output=True,
        check=True,
        timeout=20,
    )
    return proc.stdout


def inspect(case, entry):
    payload = json.dumps({k: case[k] for k in ("question", "note")})
    raw = command_line_reply(payload, entry)
    if command_line_reply(payload, entry) != raw:
        raise AssertionError(f"{case['id']}: disagreement between two CLI runs")
    answer = json.loads(raw)
    accepts = case["expect"] == "return"
    matches = answer["released"] == accepts
    if answer["released"] and accepts:
        matches = matches and math.isclose(answer["result"], case["reference"], rel_tol=1e-8)
    if answer["released"]:
        assert answer["note_sha256"] == hashlib.sha256(case["note"].encode()).hexdigest()
        for observation in answer["evidence"].values():
            assert observation["source"] == case["note"][observation["start"]:observation["end"]]
    return {
        "id": case["id"],
        "expected": case["expect"],
        "released": answer["released"],
        "result": answer.get("result"),
        "reason": answer.get("reason"),
        "route": answer.get("route"),
        "meets_expected_behavior": matches,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--entry", choices=["research_calculator.py", "checked_calculator.py", "unified_calculator.py"], default="research_calculator.py")
    parser.add_argument("--cases", type=Path, default=HERE / "cases.json")
    parser.add_argument("--require-all", action="store_true", help="Require specified behavior for every case")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    results = [inspect(case, args.entry) for case in cases]
    output = {"cli": args.entry, "route": "no proposed model call", "cases": results,
              "repeat_and_span_checks": "passed"}
    text = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.write_text(text)
    return int(args.require_all and not all(r["meets_expected_behavior"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
