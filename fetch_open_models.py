"""Download pinned, hash-verified CPU runtime and free model weights (about 2.2 GB)."""
import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import tarfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', type=pathlib.Path, default=ROOT.parent/'open_model_cache')
    args = ap.parse_args(); args.cache.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT/'data/open_models_manifest.json').read_text())
    entries = [dict(manifest['runtime'], filename=manifest['runtime']['url'].split('/')[-1])]
    entries += [dict(m, url=f"https://huggingface.co/{m['repo']}/resolve/{m['revision']}/{m['filename']}")
                for m in manifest['models']]
    def fetch(item):
        target = args.cache/item['filename']
        if not target.exists():
            partial = target.with_suffix(target.suffix+'.part')
            request = urllib.request.Request(item['url'], headers={'User-Agent':'MedCalc-Research-Pilot/0.2'})
            with urllib.request.urlopen(request, timeout=120) as source, partial.open('wb') as dest:
                while chunk := source.read(4*1024*1024):
                    dest.write(chunk)
            partial.rename(target)
        with target.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if digest != item['sha256'] or target.stat().st_size != item['size']:
            raise ValueError('Integrity check failed for '+target.name)
        if target.name.endswith('.tar.gz'):
            dest = args.cache/'runtime'; dest.mkdir(exist_ok=True)
            with tarfile.open(target) as archive:
                archive.extractall(dest, filter='data')
        result = {'file': target.name, 'sha256': digest, 'bytes': target.stat().st_size}
        print(json.dumps(result), flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(fetch, entries))
    (ROOT/'data/open_models_download_verification.json').write_text(json.dumps(results,indent=2)+'\n')

if __name__ == '__main__': main()
