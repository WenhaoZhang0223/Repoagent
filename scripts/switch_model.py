import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
ENV_EXAMPLE_PATH = ROOT / "backend" / ".env.example"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    ordered_keys = [
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_BASE_URL",
        "USE_MOCK_LLM",
        "FRONTEND_ORIGIN",
        "GENERATED_DOCS_DIR",
        "MAX_FILE_BYTES",
        "MAX_TOTAL_CHARS",
    ]
    lines = []
    for key in ordered_keys:
        if key in values:
            lines.append(f"{key}={values[key]}")
    for key in sorted(set(values) - set(ordered_keys)):
        lines.append(f"{key}={values[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Switch backend LLM model/API settings.")
    parser.add_argument("--model", required=True, help="Model name, for example gpt-4o-mini.")
    parser.add_argument("--api-key", help="API key. If omitted, the existing value is kept.")
    parser.add_argument(
        "--base-url",
        default=None,
        help="OpenAI-compatible API base URL. Use an empty string for official OpenAI.",
    )
    parser.add_argument(
        "--mock",
        choices=["true", "false"],
        help="Set USE_MOCK_LLM. Use true for local demos without model calls.",
    )
    args = parser.parse_args()

    values = read_env(ENV_EXAMPLE_PATH)
    values.update(read_env(ENV_PATH))
    values["OPENAI_MODEL"] = args.model
    if args.api_key is not None:
        values["OPENAI_API_KEY"] = args.api_key
    if args.base_url is not None:
        values["OPENAI_BASE_URL"] = args.base_url
    if args.mock is not None:
        values["USE_MOCK_LLM"] = args.mock

    write_env(ENV_PATH, values)

    print(f"Updated {ENV_PATH}")
    print(f"OPENAI_MODEL={values.get('OPENAI_MODEL', '')}")
    print(f"OPENAI_BASE_URL={values.get('OPENAI_BASE_URL', '')}")
    print(f"USE_MOCK_LLM={values.get('USE_MOCK_LLM', '')}")


if __name__ == "__main__":
    main()
