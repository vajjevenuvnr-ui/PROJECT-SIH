"""Supabase client helpers.

The backend uses the service-role key (bypasses RLS) for server-side reads and writes.
Never send the service-role key to the browser.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


class SupabaseNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    s = get_settings()
    return bool(s.supabase_url and s.supabase_service_role_key) and "your-project" not in s.supabase_url


@lru_cache
def get_supabase() -> Client:
    """Service-role client. Raises SupabaseNotConfigured if keys are missing."""
    if not is_configured():
        raise SupabaseNotConfigured("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env")
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)
