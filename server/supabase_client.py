import os
from typing import Any


_client: Any | None = None


def get_supabase() -> Any:
    global _client
    if _client is None:
        try:
            from supabase import create_client
        except ImportError as exc:
            raise RuntimeError("Install server requirements to enable Supabase Auth") from exc

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _client = create_client(url, key)
    return _client
