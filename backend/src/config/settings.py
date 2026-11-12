"""集中配置：全部来自环境变量，默认值与 .env.example 保持一致。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # 数据库（MySQL 8.0）
    db_host: str = "db"
    db_port: int = 3306
    db_name: str = "paritycheck"
    db_user: str = "paritycheck"
    db_password: str = "paritycheck_pw_2026"

    # 安全
    jwt_secret: str = "paritycheck-jwt-secret-change-me-2026"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120
    refresh_token_days: int = 7

    # 运行时
    redis_url: str = "redis://redis:6379/0"
    seed_demo: bool = True
    demo_password: str = "Demo@2026"

    # 限流 / 配额
    rate_limit_per_minute: int = 120
    quota_admin_daily: int = 4000
    quota_analyst_daily: int = 2000
    quota_viewer_daily: int = 800

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
