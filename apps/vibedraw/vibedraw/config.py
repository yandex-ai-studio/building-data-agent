from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    folder_id: str = Field(min_length=1)
    api_key: SecretStr
    base_url: str = "https://ai.api.cloud.yandex.net/v1"
    threshold: float = 98.0
    max_iterations: int = 5
    image_size: str = "1536x1024"

    @property
    def text_model(self) -> str:
        return f"gpt://{self.folder_id}/qwen3-235b-a22b-fp8/latest"

    @property
    def vision_model(self) -> str:
        return f"gpt://{self.folder_id}/qwen3.6-35b-a3b/latest"

    @property
    def image_model(self) -> str:
        return f"art://{self.folder_id}/aliceai-image-art-3.0/latest"


def find_env_file(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        env_path = candidate / ".env"
        if env_path.is_file():
            return env_path
    raise FileNotFoundError("Could not find a .env file in the app or its parent directories.")


def load_config(start: Path | None = None) -> AppConfig:
    env_path = find_env_file(start)
    load_dotenv(env_path, override=False)
    folder_id = os.environ.get("folder_id", "").strip()
    api_key = os.environ.get("api_key", "").strip()
    if not folder_id or not api_key:
        raise RuntimeError(f"{env_path} must define both folder_id and api_key.")
    return AppConfig(folder_id=folder_id, api_key=api_key)

