"""Download immutable public data only; verify every file before replacing it."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent

def main():
    manifest=json.loads((ROOT/"data/download_manifest.json").read_text())
    for item in manifest:
        dest=ROOT/item["local_path"]
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()==item["sha256"]:
            print("verified existing",item["local_path"])
            continue
        with urlopen(item["url"],timeout=60) as response:
            data=response.read()
        digest=hashlib.sha256(data).hexdigest()
        if digest!=item["sha256"]:
            raise RuntimeError(f"Hash mismatch for {item['file']}; expected pinned bytes. Do not silently use newer data.")
        dest.parent.mkdir(parents=True,exist_ok=True)
        temp=dest.with_suffix(dest.suffix+".download")
        temp.write_bytes(data)
        temp.replace(dest)
        print("downloaded and verified",item["local_path"],len(data))

if __name__=="__main__":main()
