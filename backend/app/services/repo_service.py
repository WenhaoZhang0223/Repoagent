import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


GITHUB_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+/?$")

IGNORED_DIRS = {
    ".git",
    ".github",
    ".next",
    ".nuxt",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "venv",
}

IGNORED_EXTENSIONS = {
    ".7z",
    ".bmp",
    ".db",
    ".dll",
    ".exe",
    ".gif",
    ".ico",
    ".jpg",
    ".jpeg",
    ".lock",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pyc",
    ".rar",
    ".so",
    ".sqlite",
    ".webp",
    ".zip",
}

KEY_FILENAMES = {
    "readme.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "dockerfile",
    "docker-compose.yml",
    "compose.yml",
    "go.mod",
    "cargo.toml",
    "pom.xml",
    "build.gradle",
    "vite.config.ts",
    "next.config.js",
    "next.config.mjs",
}


@dataclass
class RepoSnapshot:
    repo_name: str
    root: Path
    tree: str
    files: dict[str, str]


def validate_github_url(repo_url: str) -> str:
    normalized = str(repo_url).rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError("请输入 https://github.com/owner/repo 格式的公开 GitHub 地址。")
    if not GITHUB_RE.match(normalized):
        raise ValueError("GitHub repo 地址格式不合法，请使用 https://github.com/owner/repo。")
    return normalized


def clone_repo(repo_url: str) -> Path:
    clone_root = Path(__file__).resolve().parents[3] / ".runtime" / "repo_clones"
    clone_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="repoagent_", dir=clone_root))
    target = temp_dir / "repo"
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(target)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"clone 失败：{detail[:500]}") from exc
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError("clone 超时，请换一个更小的公开 repo 再试。") from exc
    return target


def cleanup_repo(repo_root: Path) -> None:
    shutil.rmtree(repo_root.parent, ignore_errors=True)


def should_skip(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    if parts & IGNORED_DIRS:
        return True
    return path.suffix.lower() in IGNORED_EXTENSIONS


def build_snapshot(repo_root: Path, max_file_bytes: int, max_total_chars: int) -> RepoSnapshot:
    all_files = [
        path
        for path in repo_root.rglob("*")
        if path.is_file() and not should_skip(path.relative_to(repo_root))
    ]
    all_files.sort(key=lambda item: (0 if item.name.lower() in KEY_FILENAMES else 1, len(item.parts), str(item)))

    tree_lines: list[str] = []
    selected: dict[str, str] = {}
    total_chars = 0

    for path in all_files[:300]:
        rel = path.relative_to(repo_root).as_posix()
        tree_lines.append(rel)

    for path in all_files:
        rel = path.relative_to(repo_root).as_posix()
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue

        if not content:
            continue

        is_key = path.name.lower() in KEY_FILENAMES or len(selected) < 24
        if not is_key:
            continue

        snippet = content[:6_000]
        if total_chars + len(snippet) > max_total_chars:
            break
        selected[rel] = snippet
        total_chars += len(snippet)

    return RepoSnapshot(
        repo_name=repo_root.name,
        root=repo_root,
        tree="\n".join(tree_lines),
        files=selected,
    )
