"""Additional local Qwen2.5-7B comparison on the original locked official cohort."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

import official_study as study
import audit_official_study as audit

REPO = "Qwen/Qwen2.5-7B-Instruct-GGUF"
REVISION = "bb5d59e06d9551d752d08b292a50eb208b07ab1f"
SHARDS = [
    {"filename":"qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", "size":3993201344,
     "sha256":"dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db"},
    {"filename":"qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf", "size":689872288,
     "sha256":"539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a"},
]
MODEL = dict(id="qwen2.5_7b_q4km", repo=REPO, revision=REVISION, license="Apache-2.0",
             shards=SHARDS, **SHARDS[0])
LOCK = study.DATA/"official_larger_model_lock.json"


def lock():
    original=study.validate_lock()
    payload={"study":"Additional model on the original official primary cohort", "model":MODEL,
             "original_lock_sha256":study.digest(study.LOCK), "input_sha256":original["input_sha256"],
             "reference_sha256":original["reference_sha256"], "runner_sha256":original["runner_sha256"],
             "wrapper_sha256":study.digest(Path(__file__)), "code_hashes":original["code_hashes"],
             "selected":original["selected"], "primary_outcomes":original["primary_outcomes"],
             "planned_model_calls":"Same official-study planner and schema-constrained extractor, same public cases, same seed, same token caps and scoring.",
             "choice":"Larger publisher-weight model using the same instruction family and Q4_K_M quantization as the smaller Qwen. Chosen and locked before inspecting official scores."}
    if LOCK.exists():
        previous=json.loads(LOCK.read_text())
        previous.pop("locked_utc")
        if previous!=payload:
            raise ValueError("Larger-model lock differs from current code or inputs")
    else:
        if (study.RESULTS/MODEL["id"]/"cases.jsonl").exists():
            raise ValueError("Cannot create study lock after cases have been run")
        payload["locked_utc"]=study.utc()
        LOCK.write_text(json.dumps(payload,indent=2)+"\n")


def verify(file, shard):
    if file.stat().st_size!=shard["size"] or study.digest(file)!=shard["sha256"]:
        raise ValueError(f"Publisher checksum or size mismatch for {file}")


def download(cache):
    cache.mkdir(parents=True,exist_ok=True)
    for shard in SHARDS:
        file=cache/shard["filename"]
        if not file.exists():
            partial=cache/(file.name+".download")
            url=f"https://huggingface.co/{REPO}/resolve/{REVISION}/{file.name}"
            request=urllib.request.Request(url,headers={"User-Agent":"MedCalc Research Experiment"})
            with urllib.request.urlopen(request,timeout=120) as response, partial.open("wb") as out:
                while block:=response.read(4*1024*1024):
                    out.write(block)
            verify(partial,shard)
            partial.replace(file)
        else:
            verify(file,shard)
        print("Verified",file.name,file.stat().st_size,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["lock","fetch","infer","score","audit"])
    parser.add_argument("--cache",type=Path,default=study.ROOT.parent/"open_model_cache")
    parser.add_argument("--threads",type=int,default=8)
    parser.add_argument("--slots",type=int,default=3)
    parser.add_argument("--port",type=int,default=18737)
    args=parser.parse_args()
    lock()
    if args.action=="fetch":
        download(args.cache)
    elif args.action=="infer":
        cache=args.cache.resolve()
        for shard in SHARDS:
            verify(cache/shard["filename"],shard)
        study.run_model(MODEL,cache,args.threads,args.slots,args.port)
    elif args.action=="score":
        study.score(MODEL)
    elif args.action=="audit":
        audit.audit_model(MODEL["id"])


if __name__=="__main__":
    main()
