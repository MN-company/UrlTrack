import os
from typing import Any

_client: Any | None = None


def get_supabase():
    global _client
    if _client is None:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "") or os.environ.get(
            "SUPABASE_SERVICE_ROLE_KEY", ""
        )
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set "
                "(SUPABASE_SERVICE_ROLE_KEY is accepted for server-only deployments)"
            )
        _client = create_client(url, key)
    return _client


def supabase_enabled() -> bool:
    return bool(
        os.environ.get("SUPABASE_URL")
        and (
            os.environ.get("SUPABASE_ANON_KEY")
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        )
    )
