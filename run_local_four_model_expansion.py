"""Turnkey local runner to complete Qwen2.5-7B on the 80 extension cases and add
a 4th open-weight model family (Phi-3.5-mini-3.8B MIT or Llama-3.1-8B) across all 124 cases.

Works on Linux x86-64 (auto-downloads pinned llama.cpp server), macOS (Apple Silicon / Intel
via `brew install llama.cpp`), and Windows (`winget install llama.cpp` or WSL2).

Usage:
  1. python3 run_local_four_model_expansion.py fetch --fourth-model phi3.5_mini_q4km
  2. python3 run_local_four_model_expansion.py infer --fourth-model phi3.5_mini_q4km
  3. python3 run_local_four_model_expansion.py finalize
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request

from medcalc.live import (
    evaluate_gates,
    extraction_schema,
    extractor_messages,
    generate,
    make_call,
    parse_generation,
    planner_messages,
)
from medcalc.registry import SPECS
from run_source_repair import apply_repair

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

QWEN_7B_SHARDS = [
    {
        "filename": "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/bb5d59e06d9551d752d08b292a50eb208b07ab1f/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
        "sha256": "dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db",
    },
    {
        "filename": "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/bb5d59e06d9551d752d08b292a50eb208b07ab1f/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf",
        "sha256": "539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a",
    },
]

EXPANSION_MODELS = {
    "qwen2.5_7b_q4km": {
        "id": "qwen2.5_7b_q4km",
        "family": "Qwen2.5-7B-Instruct",
        "license": "Apache-2.0",
        "filename": QWEN_7B_SHARDS[0]["filename"],
        "files": QWEN_7B_SHARDS,
        "cohorts": ["extension"],  # Initial 44 already completed in results/official/qwen2.5_7b_q4km
    },
    "phi3.5_mini_q4km": {
        "id": "phi3.5_mini_q4km",
        "family": "Phi-3.5-mini-instruct (3.8B)",
        "license": "MIT",
        "filename": "Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "files": [
            {
                "filename": "Phi-3.5-mini-instruct-Q4_K_M.gguf",
                "url": "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf",
                "sha256": "e4165e3a71af97f1b4820da61079826d8752a2088e313af0c7d346796c38eff5",
            }
        ],
        "cohorts": ["first", "extension"],
    },
    "llama3.1_8b_q4km": {
        "id": "llama3.1_8b_q4km",
        "family": "Meta-Llama-3.1-8B-Instruct",
        "license": "llama3.1",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "files": [
            {
                "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
                "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
                "sha256": "7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c",
            }
        ],
        "cohorts": ["first", "extension"],
    },
}

COHORT_PATHS = {
    "first": (DATA / "official_locked_inputs.jsonl", ROOT / "results/official"),
    "extension": (DATA / "official_extension/inputs.jsonl", ROOT / "results/official_extension"),
}


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def download_verified(url: str, dest: Path, expected_sha256: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        actual = sha256_file(dest)
        if actual == expected_sha256:
            print(f"[OK] Cached & SHA-256 verified: {dest.name}", flush=True)
            return
        print(f"[WARN] Checksum mismatch on existing {dest.name}; re-downloading...", flush=True)
        dest.unlink()

    part = dest.with_suffix(dest.suffix + ".download")
    headers = {"User-Agent": "MedCalc-Enforce-Research/0.5"}
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token and "huggingface.co" in url:
        headers["Authorization"] = f"Bearer {hf_token}"

    print(f"[DOWNLOAD] {dest.name} <- {url}", flush=True)
    req = urllib.request.Request(url, headers=headers)
    downloaded = 0
    last_report = 0
    with urllib.request.urlopen(req, timeout=180) as resp, part.open("wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        while chunk := resp.read(8 * 1024 * 1024):
            out.write(chunk)
            downloaded += len(chunk)
            if downloaded - last_report >= 128 * 1024 * 1024:
                pct = f" ({downloaded * 100 / total:.1f}%)" if total else ""
                print(f"  ... {downloaded / (1024**3):.2f} GB{pct}", flush=True)
                last_report = downloaded

    actual = sha256_file(part)
    if actual != expected_sha256:
        part.unlink(missing_ok=True)
        raise ValueError(f"SHA-256 mismatch for {dest.name}: expected {expected_sha256}, got {actual}")
    part.replace(dest)
    print(f"[VERIFIED] {dest.name} ({dest.stat().st_size / (1024**3):.2f} GB, sha256={actual[:16]}...)", flush=True)


def resolve_llama_server(cache: Path, explicit_bin: Path | None, allow_download: bool = False) -> Path:
    if explicit_bin is not None:
        if not explicit_bin.exists():
            raise FileNotFoundError(f"Specified --llama-server not found: {explicit_bin}")
        return explicit_bin.resolve()

    manifest = json.loads((DATA / "open_models_manifest.json").read_text(encoding="utf-8"))
    rt = manifest["runtime"]
    pinned_bin = cache / "runtime" / f"llama-{rt['release']}" / "llama-server"

    is_linux_x64 = platform.system() == "Linux" and platform.machine() in ("x86_64", "AMD64")
    if is_linux_x64:
        if not pinned_bin.exists() and allow_download:
            archive = cache / rt["url"].split("/")[-1]
            download_verified(rt["url"], archive, rt["sha256"])
            dest_dir = cache / "runtime"
            dest_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive) as tar:
                tar.extractall(dest_dir, filter="data")
        if pinned_bin.exists():
            return pinned_bin.resolve()

    which_bin = shutil.which("llama-server")
    if which_bin:
        return Path(which_bin).resolve()
    if pinned_bin.exists():
        return pinned_bin.resolve()

    raise FileNotFoundError(
        "Could not locate `llama-server`. On macOS run `brew install llama.cpp`, "
        "on Windows run `winget install llama.cpp` (or use WSL2), or pass `--llama-server /path/to/llama-server`."
    )


def selected_model_ids(fourth_choice: str, skip_qwen7b: bool) -> list[str]:
    ids = [] if skip_qwen7b else ["qwen2.5_7b_q4km"]
    if fourth_choice == "both":
        ids.extend(["phi3.5_mini_q4km", "llama3.1_8b_q4km"])
    elif fourth_choice != "none":
        ids.append(fourth_choice)
    return ids


@contextlib.contextmanager
def launch_server(
    binary: Path,
    weights: Path,
    folder: Path,
    port: int,
    threads: int,
    slots: int,
    gpu_layers: int,
    model_meta: dict,
    input_sha256: str,
):
    base = f"http://127.0.0.1:{port}"
    cmd = list(
        map(
            str,
            [
                binary,
                "-m",
                weights,
                "-c",
                8192 * slots,
                "-np",
                slots,
                "-t",
                threads,
                "-tb",
                threads,
                "-b",
                512,
                "-ub",
                512,
                "-ngl",
                gpu_layers,
                "--host",
                "127.0.0.1",
                "--port",
                port,
            ],
        )
    )
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "server.log").open("a", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(180):
                if proc.poll() is not None:
                    raise RuntimeError(f"llama-server exited early; inspect {folder / 'server.log'}")
                try:
                    with urllib.request.urlopen(base + "/health", timeout=2) as reply:
                        if json.load(reply).get("status") == "ok":
                            break
                except (OSError, urllib.error.URLError):
                    time.sleep(0.5)
            else:
                raise TimeoutError(f"llama-server startup timed out on {base}")

            meta = {
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "command": cmd,
                "model": model_meta,
                "input_sha256": input_sha256,
                "threads": threads,
                "slots": slots,
                "gpu_layers": gpu_layers,
                "model_context_per_slot": 8192,
            }
            with (folder / "invocations.jsonl").open("a", encoding="utf-8") as inv:
                inv.write(json.dumps(meta) + "\n")
            yield base
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def run_cohort_inference(
    model_meta: dict,
    cohort: str,
    cache: Path,
    binary: Path,
    threads: int,
    slots: int,
    gpu_layers: int,
    port: int,
) -> None:
    inputs_path, results_root = COHORT_PATHS[cohort]
    inputs = read_jsonl(inputs_path)
    out_dir = results_root / model_meta["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_path = out_dir / "cases.jsonl"
    requests_path = out_dir / "requests.jsonl"

    completed = {r["case_id"] for r in read_jsonl(cases_path)}
    pending = [r for r in inputs if r["case_id"] not in completed]
    if not pending:
        print(f"[SKIP] {model_meta['id']} ({cohort}): all {len(inputs)}/{len(inputs)} cases already completed.", flush=True)
        return

    for f_info in model_meta["files"]:
        w_file = cache / f_info["filename"]
        if not w_file.exists() or sha256_file(w_file) != f_info["sha256"]:
            raise ValueError(f"Missing or unverified weight file {w_file}; run `fetch` first.")

    weights_entry = cache / model_meta["filename"]
    stored_requests = {r["key"]: r for r in read_jsonl(requests_path)}
    write_lock = threading.Lock()
    print(f"[INFER] {model_meta['id']} ({cohort}): {len(pending)} remaining of {len(inputs)} cases...", flush=True)

    with launch_server(
        binary,
        weights_entry,
        out_dir,
        port,
        threads,
        slots,
        gpu_layers,
        model_meta,
        sha256_file(inputs_path),
    ) as base:

        def cached_request(key: str, messages: list[dict], cap: int, schema: dict | None = None) -> dict:
            sig = hashlib.sha256(json.dumps([messages, cap, schema], sort_keys=True).encode()).hexdigest()
            if key in stored_requests:
                if sig != stored_requests[key]["signature"]:
                    raise ValueError(f"Stored prompt signature mismatch for {key}")
                return stored_requests[key]["generation"]
            gen = generate(base, model_meta["id"], messages, cap, schema)
            entry = {"key": key, "signature": sig, "generation": gen}
            with write_lock, requests_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            return gen

        def process_row(row: dict) -> dict:
            case = {k: row[k] for k in ("case_id", "source_row", "group_id")}
            case["model_id"] = model_meta["id"]
            t0 = time.monotonic()
            try:
                plan = cached_request(row["case_id"] + "/planner", planner_messages(row["question"]), 48)
                cid = parse_generation(plan).get("calculator_id")
                case["selected_calculator_id"] = cid
                if cid not in SPECS:
                    raise ValueError("Unknown calculator")
                prop = cached_request(
                    row["case_id"] + "/baseline",
                    extractor_messages(row["question"], row["patient_note"], cid),
                    768,
                    extraction_schema(cid),
                )
                call, quotes = make_call(cid, parse_generation(prop))
                case["baseline_call"] = call
                case["baseline_quotes"] = quotes
                case["baseline_gates"] = evaluate_gates(call, quotes, row["patient_note"])
            except Exception as exc:
                case["baseline_error"] = f"{type(exc).__name__}: {exc}"
            apply_repair(case, row["patient_note"])
            case["wall_seconds"] = time.monotonic() - t0
            return case

        with concurrent.futures.ThreadPoolExecutor(max_workers=slots) as pool, cases_path.open("a", encoding="utf-8") as out_f:
            futs = [pool.submit(process_row, r) for r in pending]
            for fut in concurrent.futures.as_completed(futs):
                rec = fut.result()
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out_f.flush()
                os.fsync(out_f.fileno())
                completed.add(rec["case_id"])
                print(f"  {model_meta['id']} [{cohort}] {len(completed)}/{len(inputs)}", flush=True)


def finalize_package() -> None:
    print("[1/3] Re-computing complete BDCC v0.5 experimental & statistical suite...", flush=True)
    subprocess.run([sys.executable, "run_bdcc_v05_suite.py"], cwd=ROOT, check=True)

    print("[2/3] Refreshing SHA256SUMS.txt across all repository artifacts...", flush=True)
    entries = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS.txt" and "__pycache__" not in p.parts:
            rel = p.relative_to(ROOT).as_posix()
            entries.append(f"{sha256_file(p)}  {rel}")
    (ROOT / "SHA256SUMS.txt").write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(f"  Indexed {len(entries)} files in SHA256SUMS.txt.", flush=True)

    print("[3/3] Running full end-to-end verify_release.py check...", flush=True)
    subprocess.run([sys.executable, "verify_release.py"], cwd=ROOT, check=True)
    print("[DONE] All live multi-model traces scored, verified, and ready for BDCC submission.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["fetch", "infer", "finalize"])
    parser.add_argument(
        "--fourth-model",
        default="phi3.5_mini_q4km",
        choices=["phi3.5_mini_q4km", "llama3.1_8b_q4km", "both", "none"],
        help="Non-Qwen open-weight model family to evaluate across all 124 cases (default: phi3.5_mini_q4km)",
    )
    parser.add_argument("--skip-qwen7b-extension", action="store_true", help="Skip Qwen2.5-7B 80-case extension")
    parser.add_argument("--cache", type=Path, default=ROOT.parent / "open_model_cache", help="Directory for GGUF weights")
    parser.add_argument("--llama-server", type=Path, default=None, help="Optional path to llama-server binary")
    parser.add_argument("--threads", type=int, default=8, help="CPU inference threads (default: 8)")
    parser.add_argument("--slots", type=int, default=2, help="Concurrent llama-server slots (default: 2)")
    parser.add_argument(
        "--gpu-layers",
        type=int,
        default=0,
        help="GPU offload layers (-ngl): use 0 for pure CPU determinism, or 99 on Apple Silicon Metal / CUDA GPU",
    )
    parser.add_argument("--port", type=int, default=18739)
    args = parser.parse_args()

    if args.action == "finalize":
        finalize_package()
        return

    cache = args.cache.resolve()
    m_ids = selected_model_ids(args.fourth_model, args.skip_qwen7b_extension)

    if args.action == "fetch":
        binary = resolve_llama_server(cache, args.llama_server, allow_download=True)
        print(f"[OK] Using llama-server binary: {binary}", flush=True)
        for m_id in m_ids:
            for f_info in EXPANSION_MODELS[m_id]["files"]:
                download_verified(f_info["url"], cache / f_info["filename"], f_info["sha256"])
        print("[DONE] All requested GGUF weights downloaded and SHA-256 verified.", flush=True)
        return

    if args.action == "infer":
        binary = resolve_llama_server(cache, args.llama_server, allow_download=False)
        for idx, m_id in enumerate(m_ids):
            meta = EXPANSION_MODELS[m_id]
            for c_idx, cohort in enumerate(meta["cohorts"]):
                run_cohort_inference(
                    meta,
                    cohort,
                    cache,
                    binary,
                    args.threads,
                    args.slots,
                    args.gpu_layers,
                    args.port + idx * 2 + c_idx,
                )
        print("[DONE] Inference complete! Run `python3 run_local_four_model_expansion.py finalize` next.", flush=True)


if __name__ == "__main__":
    main()
