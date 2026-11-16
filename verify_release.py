"""Verify the distributed v0.5 archive, replay all locked v0.4 transcripts/audits,
and verify v0.5 discourse, extended CLI stress checks, and BDCC summary invariants."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(folder: Path, *arguments: str) -> None:
    subprocess.run([sys.executable, *arguments], cwd=folder, check=True, stdout=subprocess.DEVNULL)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checksums-only", action="store_true")
    args = parser.parse_args()

    manifest = ROOT / "SHA256SUMS.txt"
    checked = 0
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        checksum, path = line.split("  ", 1)
        if digest(ROOT / path) != checksum:
            raise ValueError(f"Archive entry differs: {path}")
        checked += 1
    print(f"Verified {checked} checksums.", flush=True)
    if args.checksums_only:
        return

    with tempfile.TemporaryDirectory() as temp:
        copy_dir = Path(temp) / "medcalc_enforce_pilot"
        shutil.copytree(ROOT, copy_dir, ignore=shutil.ignore_patterns("__pycache__", ".git", "build", "*.egg-info", "raw"))

        # 1. Run full unit test suite (70 tests covering v0.1-v0.5)
        run(copy_dir, "-m", "unittest", "discover", "-s", "tests", "-q")

        # 2. Replay all frozen v0.4 model summaries and lockfile audits
        planned = json.loads((copy_dir / "data/official_lock.json").read_text())["planned_models"]
        larger = json.loads((copy_dir / "data/official_larger_model_lock.json").read_text())["model"]
        for item in [*planned, larger]:
            model = item["id"]
            run(copy_dir, "summarize_official_policies.py", "--model", model)
            for path in (copy_dir / "results/final_evaluation" / model).rglob("*"):
                if path.is_file() and digest(path) != digest(ROOT / path.relative_to(copy_dir)):
                    raise ValueError(f"Replayed candidate output differs: {path.name}")
            if item in planned:
                run(copy_dir, "audit_official_study.py", "--model", model)
                run(copy_dir, "official_extension.py", "audit", "--model", model)
            else:
                run(copy_dir, "official_larger_model.py", "audit")

        # 3. Verify cross-Python deterministic ablation summary
        run(copy_dir, "analyze_official_ablations.py")
        comparison = Path("results/official_ablations/summary.json")
        if digest(copy_dir / comparison) != digest(ROOT / comparison):
            raise ValueError("Ablation summary differs")

        # 4. Verify v0.5 unified_calculator passes all 8 smoke + 4 extended cross-sentence CLI checks
        run(copy_dir, "results/code_review/replay.py", "--entry", "unified_calculator.py", "--cases", "results/code_review/cases.json", "--require-all")
        run(copy_dir, "results/code_review/replay.py", "--entry", "unified_calculator.py", "--cases", "results/code_review/extended_cases.json", "--require-all")

        # 5. Verify v0.5 BDCC benchmark summary invariants
        bdcc = json.loads((copy_dir / "results/v0_5_bdcc/summary.json").read_text())
        assert bdcc["experiment_1_official_and_stats"]["reference_entity_audit"]["v05_reconstructed"] == 124
        assert bdcc["experiment_3_paraphrase_and_distractors"]["cross_sentence_traps_48"]["v05_false_releases"] == 0
        sem = bdcc["experiment_6_sqlite_commit_concurrency"]["policies"]["semantic_field_commit_v05"]
        assert sem["wrong_or_unsafe_value_published"] == 0 and sem["benign_false_withholds"] == 0

        print("Verified all 70 unit tests, locked transcripts, ablation digests, 12/12 CLI stress checks, and v0.5 BDCC invariants.")


if __name__ == "__main__":
    main()
