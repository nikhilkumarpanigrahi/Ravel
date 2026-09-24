"""RAVEL configuration. All secrets come from environment variables only."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "HHGOA_IEEE"
DEFAULT_OUTPUT_DIR = ROOT / "cases"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_prefix="RAVEL_", extra="ignore")

    app_name: str = "RAVEL"
    env: Literal["development", "test", "benchmark", "demo", "production"] = "development"
    log_level: str = "INFO"

    # --- Dataset -----------------------------------------------------------------
    data_dir: Path = DEFAULT_DATA_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR

    # --- Persistence (case state) ------------------------------------------------
    state_db_url: str = "sqlite:///data/ravel.db"

    # --- Graph (Savanna / TigerGraph) ---------------------------------------------
    graph_adapter: Literal["tigergraph", "mock"] = "mock"
    tg_host: str = ""
    tg_graphname: str = "ravel"
    tg_username: str = ""
    tg_password: str = ""
    tg_use_token: bool = False
    tg_token: str = ""
    tg_secret: str = ""
    tg_query_timeout: int = 30
    tg_mock_rebuild: bool = True

    # --- LLM (OpenAI-compatible / Ollama / Local chat endpoint) ------------------
    llm_provider: Literal["none", "openai_compatible", "ollama"] = "none"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_s: float = 45.0

    # --- MCP ----------------------------------------------------------------------
    mcp_transport: Literal["stdio", "sse", "none"] = "none"
    mcp_command: list[str] = []
    mcp_url: str = ""

    # --- Orchestration & Agent ---------------------------------------------------
    workflow_orchestrator: Literal["langgraph", "state_machine"] = "langgraph"
    agent_max_steps: int = 24
    agent_request_timeout_s: float = 12.0
    req_high_risk_threshold: float = 0.7
    req_low_risk_threshold: float = 0.15
    evidence_sufficient_threshold: float = 0.85
    evidence_insufficient_threshold: float = 0.15

    # --- Security & CORS ----------------------------------------------------------
    auth_enabled: bool = False
    analyst_api_key: str = "ravel-secret-key"
    cors_origins: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # --- Vector Search & Embeddings -----------------------------------------------
    vector_search_enabled: bool = True

    # --- Simulation controls (benchmark/demo determinism) ---------------------------
    simulate_customer_response: bool = True
    sim_seed: int = 42

    @property
    def state_db_path(self) -> Path:
        if self.state_db_url.startswith("sqlite:///"):
            p = self.state_db_url.removeprefix("sqlite:///")
            if p != ":memory:":
                path = Path(p)
                if not path.is_absolute():
                    path = ROOT / path
                path.parent.mkdir(parents=True, exist_ok=True)
            return Path(p)
        return Path("")

    @property
    def tg_conn(self) -> dict:
        return {
            "host": self.tg_host,
            "graphname": self.tg_graphname,
            "username": self.tg_username,
            "password": self.tg_password,
            "useToken": self.tg_use_token,
            "token": self.tg_token,
            "apiToken": self.tg_secret,
        }


settings = Settings()
