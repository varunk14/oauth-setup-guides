"""Runtime settings, read from environment variables.

Locally, set ENV_FILE to a dotenv file; its values take priority over variables
already exported in the shell (a stale shell variable must never win). When
hosted, the platform's environment variables are used directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    gemini_api_key: str
    gemini_model: str
    tavily_api_key: str
    max_searches: int
    run_timeout_s: float
    runs_per_ip_per_hour: int
    runs_per_day: int
    generated_dir: Path
    redis_url: str = ""
    redis_token: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.openai_api_key or (self.gemini_api_key and self.tavily_api_key))


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def load_settings() -> Settings:
    env_file = os.environ.get("ENV_FILE")
    if env_file:
        load_dotenv(env_file, override=True)
    return Settings(
        openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-6-luna").strip(),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        # The fast model is also used for writing: on the free tier the larger
        # model was measured at minutes per call, which breaks the run timeout.
        gemini_model=os.environ.get("GEMINI_MODEL_FAST", "gemini-3.5-flash-lite").strip(),
        tavily_api_key=os.environ.get("TAVILY_API_KEY", "").strip(),
        max_searches=_int("AGENT_MAX_SEARCHES", 8),
        run_timeout_s=float(_int("AGENT_RUN_TIMEOUT_S", 240)),
        runs_per_ip_per_hour=_int("AGENT_RUNS_PER_IP_PER_HOUR", 3),
        runs_per_day=_int("AGENT_RUNS_PER_DAY", 25),
        generated_dir=Path(os.environ.get("GENERATED_DIR") or default_generated_dir()),
        # Upstash's own names, or the names Vercel's Upstash integration sets.
        redis_url=(
            os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL") or ""
        ).strip(),
        redis_token=(
            os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or ""
        ).strip(),
    )


def default_generated_dir() -> Path:
    # On Vercel only /tmp is writable (and it is not shared between instances).
    if os.environ.get("VERCEL"):
        return Path("/tmp/generated")
    return REPO_ROOT / "data" / "generated"
