from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="StockGo", alias="APP_NAME")
    env: Literal["dev", "test", "prod"] = Field(default="dev", alias="ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    mysql_host: str = Field(default="127.0.0.1", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_db: str = Field(default="stockgo", alias="MYSQL_DB")
    mysql_user: str = Field(default="stockgo", alias="MYSQL_USER")
    mysql_password: str = Field(default="stockgo", alias="MYSQL_PASSWORD")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")

    scheduler_enabled: bool = Field(default=False, alias="SCHEDULER_ENABLED")
    watchlist: str = Field(default="TSLA,AAPL,MSFT", alias="WATCHLIST")
    market_update_minutes: int = Field(default=30, alias="MARKET_UPDATE_MINUTES")
    news_update_minutes: int = Field(default=30, alias="NEWS_UPDATE_MINUTES")
    report_lookback_days: int = Field(default=365, alias="REPORT_LOOKBACK_DAYS")

    jwt_secret: str = Field(default="change_me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60 * 24, alias="JWT_EXPIRE_MINUTES")

    # SEC EDGAR (required: identify your app; use your email or company)
    sec_user_agent: str = Field(
        default="StockGo contact@example.com",
        alias="SEC_USER_AGENT",
    )

    # Alpha Vantage (used for stock quotes on homepage and elsewhere)
    alpha_vantage_api_key: str | None = Field(default=None, alias="ALPHA_VANTAGE_API_KEY")

    def watchlist_tickers(self) -> list[str]:
        return [t.strip().upper() for t in (self.watchlist or "").split(",") if t.strip()]

    @property
    def mysql_url(self) -> str:
        # SQLAlchemy URL form: mysql+pymysql://user:pass@host:port/db?charset=utf8mb4
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url or self.mysql_url


@lru_cache
def get_settings() -> Settings:
    return Settings()

