# services/trainer/sitecustomize.py
# Backfill huggingface_hub.cached_download for libs that still import it.
import os
import re

try:
    import huggingface_hub as _hub  # noqa
    if not hasattr(_hub, "cached_download"):
        from huggingface_hub import hf_hub_download as _hf_hub_download

        def cached_download(*args, **kwargs):
            """
            Drop-in compatibility wrapper for huggingface_hub.cached_download.
            Accepts both legacy url-based and modern repo_id/filename signatures.
            """
            # If called with positional args, delegate directly
            if args:
                return _hf_hub_download(*args, **kwargs)
            
            # Handle url-based signature
            if 'url' in kwargs:
                url = kwargs.pop('url')
                
                # Parse HuggingFace resolve URL format:
                # https://huggingface.co/{repo_id}/resolve/{revision}/{filename}
                pattern = r'https://huggingface\.co/([^/]+/[^/]+)/resolve/([^/]+)/(.+)'
                match = re.match(pattern, url)
                
                if not match:
                    raise ValueError(f"Cannot parse HuggingFace URL format: {url}")
                
                repo_id, revision, filename = match.groups()
                
                # Map to modern hf_hub_download signature
                new_kwargs = {
                    'repo_id': repo_id,
                    'filename': filename,
                    'revision': revision
                }
                
                # Pass through supported kwargs, ignore unknown ones
                supported_kwargs = {
                    'cache_dir', 'token', 'force_download', 'local_files_only', 
                    'resume_download', 'proxies', 'etag_timeout', 'user_agent'
                }
                
                for key, value in kwargs.items():
                    if key in supported_kwargs:
                        new_kwargs[key] = value
                
                return _hf_hub_download(**new_kwargs)
            else:
                # Modern signature, delegate directly
                return _hf_hub_download(**kwargs)

        _hub.cached_download = cached_download  # type: ignore[attr-defined]
        print("[sitecustomize] shimmed huggingface_hub.cached_download (url->hf_hub_download)")

    # Respect environment flags
    if os.getenv('HF_HUB_OFFLINE') == '1':
        os.environ['HF_HUB_OFFLINE'] = '1'
    if os.getenv('HF_HUB_DISABLE_TELEMETRY') == '1':
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    if 'HF_HOME' in os.environ:
        # HF_HOME is already set, respect it
        pass

except Exception as e:
    # Never break interpreter startup
    print(f"[sitecustomize] huggingface_hub shim skipped: {e}")