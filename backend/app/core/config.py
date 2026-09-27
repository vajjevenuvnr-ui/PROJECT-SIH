from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Kshetra API"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    # Direct Postgres connection (Supabase > Project Settings > Database), used by scripts only
    database_url: str = ""
    demo_mode: bool = False
    # Address of the frontend used in farmer links when the caller doesn't send one.
    public_app_url: str = "http://localhost:3000"
    # Officer accounts may only use these email domains (subdomains allowed). Empty = any domain.
    officer_email_domains: str = "gov.in,nic.in,panchayatcast.in"
    # Web Push (VAPID) for farmer alerts. Generate with: python -m scripts.gen_vapid
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:alerts@kshetra.example"
    # Downscaling pipeline: run daily at 06:00 IST inside the API process (off by default in dev)
    pipeline_schedule: bool = False
    pipeline_publish_demo: bool = False
    cors_origins: str = "http://localhost:3000"
    # Also allow any local dev port (Next.js moves to 3001, 3002... when 3000 is busy).
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
