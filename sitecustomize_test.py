# sitecustomize_test.py
"""
Self-test for our sitecustomize shim that maps cached_download(url=...) -> hf_hub_download(...)
Run with: python -m sitecustomize_test
This will SKIP (exit 0) if offline and the target file isn't cached.
"""
import os, sys, pathlib
from importlib import import_module

def _is_offline():
    return os.getenv("HF_HUB_OFFLINE") == "1"

def _p(msg): print(f"[sitecustomize_test] {msg}")

def main():
    try:
        import_module("sitecustomize")
    except Exception as e:
        _p(f"Import failed: {e}")
        sys.exit(1)

    try:
        from huggingface_hub import cached_download
    except Exception as e:
        _p(f"Could not import huggingface_hub.cached_download: {e}")
        sys.exit(1)

    url = "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/config.json"
    kwargs = {"url": url}
    if _is_offline():
        _p("HF_HUB_OFFLINE=1 detected; cache-only mode")
        kwargs["local_files_only"] = True

    try:
        path = cached_download(**kwargs)
        p = pathlib.Path(path)
        if p.exists():
            _p(f"OK: resolved to {p}")
            sys.exit(0)
        _p(f"FAIL: returned path not found: {p}")
        sys.exit(1)
    except Exception as e:
        if _is_offline():
            _p(f"OFFLINE and not cached -> SKIP: {e}")
            sys.exit(0)
        _p(f"FAIL: cached_download raised: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()