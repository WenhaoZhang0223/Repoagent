from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


load_dotenv()


class Settings(BaseSettings):
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    use_mock_llm: bool = Field(default=False, alias="USE_MOCK_LLM")
    frontend_origin: str = Field(default="http://localhost:3000", alias="FRONTEND_ORIGIN")
    generated_docs_dir: str = Field(default="../generated_docs", alias="GENERATED_DOCS_DIR")
    max_file_bytes: int = Field(default=80_000, alias="MAX_FILE_BYTES")
    max_total_chars: int = Field(default=120_000, alias="MAX_TOTAL_CHARS")

    @property
    def docs_path(self) -> Path:
        path = Path(self.generated_docs_dir)
        if path.is_absolute():
            return path
        backend_dir = Path(__file__).resolve().parents[1]
        return (backend_dir / path).resolve()


settings = Settings()
