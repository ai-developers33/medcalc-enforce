"""Reproduce the MedCalc-Enforce v0.6.0 CPU analyses in a temporary directory."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
RELEASE_URL = (
    "https://github.com/ai-developers33/medcalc-enforce/releases/download/"
    "v0.6.0/MedCalc_Enforce_Experiments_v0_6.3.zip"
)
RELEASE_SHA256 = "c3121032ea6eaf6f25d31cb230d67c2eb37e5030e8026d28d9000a9e06e6e6cb"
MANIFEST_SHA256 = "4d0f4fe980ecac0a68537c37db1a02a4b988d6aac398efb147aaf4ce3586277c"
REPLAY_URL = (
    "https://raw.githubusercontent.com/ai-developers33/medcalc-enforce/"
    "f4f9cc6cd1b5c4cd605ddedf02f5646c8d2a07ea/replay_experiment8.py"
)
REPLAY_SHA256 = "6db81243dfac05b41147868c0ae2896ab016be69a78fe0fbac100c27e2430715"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_digest(path, expected):
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(f"SHA-256 mismatch for {path.name}: expected {expected}, got {actual}")


def download_verified(url, path, expected):
    print(f"Downloading {url}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "MedCalc-Enforce-Reviewer/0.6"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as output:
        shutil.copyfileobj(response, output)
    check_digest(path, expected)
    print(f"Verified {path.name} SHA-256: {expected}", flush=True)


def prepare_release(directory, download):
    work = directory / "medcalc_enforce_pilot"
    manifest = HERE / "SHA256SUMS.txt"
    if download or not manifest.is_file():
        archive = directory / "MedCalc_Enforce_Experiments_v0_6.3.zip"
        download_verified(RELEASE_URL, archive, RELEASE_SHA256)
        with zipfile.ZipFile(archive) as package:
            package.extractall(directory)
    else:
        # Copy only files listed in the published manifest. The checkout stays read-only.
        check_digest(manifest, MANIFEST_SHA256)
        work.mkdir()
        shutil.copyfile(manifest, work / manifest.name)
        for line in manifest.read_text(encoding="utf-8").splitlines():
            _, relative = line.split("  ", 1)
            destination = work / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(HERE / relative, destination)
    return work


def run_step(work, label, *args):
    print(f"\n{label}", flush=True)
    subprocess.run([sys.executable, "-B", *args], cwd=work, check=True)


def benchmark_workloads(summary):
    cells = summary["experiment_7_bdcc_scalability_matrix"]["cells"]
    return [(cell["ledger_notes"], cell["workers"], cell["operations"]) for cell in cells]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download-release-zip",
        action="store_true",
        help="use the SHA-256-verified GitHub release archive instead of the checkout",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="medcalc_repro_v06_") as tmp:
        work = prepare_release(Path(tmp), args.download_release_zip)
        run_step(work, "1/4  Release checksums and unit tests", "verify_release.py")

        # Experiment 8 must be checked before the archived reports are regenerated.
        helper = HERE / "replay_experiment8.py"
        if helper.is_file():
            shutil.copyfile(helper, work / helper.name)
        else:
            download_verified(REPLAY_URL, work / helper.name, REPLAY_SHA256)
        run_step(work, "2/4  Experiment 8: 240 archived distractor workflows", helper.name, "--check")

        reports = work / "results" / "v0_5_bdcc"
        outputs = [
            work / "data" / "oov_discourse_transfer_64.jsonl",
            reports / "reviewer_fixes_v06.json",
        ]
        expected = {path: sha256(path) for path in outputs}
        for path in outputs:
            path.unlink()
        run_step(
            work, "3/4  Attribution, 64-case transfer suite and clustered intervals",
            "run_reviewer_fixes_v06.py",
        )
        for path, digest in expected.items():
            check_digest(path, digest)
        print("Both regenerated reviewer files match the release byte-for-byte.", flush=True)

        summary_path = reports / "summary.json"
        published = json.loads(summary_path.read_text(encoding="utf-8"))
        summary_path.unlink()
        (reports / "BDCC_STRENGTHENED_RESULTS.md").unlink()
        run_step(
            work, "4/4  Experiments 1–7: 620 official workflows and 324 SQLite WAL trials",
            "run_bdcc_v05_suite.py",
        )
        regenerated = json.loads(summary_path.read_text(encoding="utf-8"))
        # Experiment 7 is a machine-dependent timing benchmark.
        fixed_sections = tuple(f"experiment_{n}_" for n in range(1, 7))
        for section, result in published.items():
            if section.startswith(fixed_sections) and regenerated.get(section) != result:
                raise SystemExit(f"Regenerated results differ from the release: {section}")
        if benchmark_workloads(regenerated) != benchmark_workloads(published):
            raise SystemExit("Regenerated scalability workloads differ from the release.")
        print("Experiments 1–6 match the release. All Experiment 7 workloads ran.", flush=True)
    print("\nAll four MedCalc-Enforce v0.6.0 reproduction checks passed.")


if __name__ == "__main__":
    main()
