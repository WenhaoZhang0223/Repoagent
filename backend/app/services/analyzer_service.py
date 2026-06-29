from dataclasses import dataclass

from app.services.repo_service import RepoSnapshot


TECH_HINTS = {
    "Next.js": ["next.config", "next/", "app/page", "pages/"],
    "React": ["react", "jsx", "tsx"],
    "Vue": ["vue", "vite.config"],
    "FastAPI": ["fastapi", "uvicorn"],
    "Django": ["django", "manage.py"],
    "Flask": ["flask"],
    "Python": ["requirements.txt", "pyproject.toml", ".py"],
    "Node.js": ["package.json", "node"],
    "TypeScript": ["tsconfig", ".ts", ".tsx"],
    "Docker": ["dockerfile", "docker-compose"],
    "Go": ["go.mod", ".go"],
    "Rust": ["cargo.toml", ".rs"],
}


@dataclass
class ProjectSummary:
    repo_name: str
    tech_stack: list[str]
    file_tree: str
    file_summaries: str


def infer_tech_stack(snapshot: RepoSnapshot) -> list[str]:
    haystack = "\n".join([snapshot.tree, *snapshot.files.keys(), *snapshot.files.values()]).lower()
    found = []
    for tech, hints in TECH_HINTS.items():
        if any(hint.lower() in haystack for hint in hints):
            found.append(tech)
    return found or ["暂未明确识别"]


def summarize_files(snapshot: RepoSnapshot) -> str:
    chunks = []
    for path, content in snapshot.files.items():
        excerpt = content[:2_000]
        chunks.append(f"## {path}\n```text\n{excerpt}\n```")
    return "\n\n".join(chunks)


def analyze_snapshot(snapshot: RepoSnapshot) -> ProjectSummary:
    return ProjectSummary(
        repo_name=snapshot.repo_name,
        tech_stack=infer_tech_stack(snapshot),
        file_tree=snapshot.tree,
        file_summaries=summarize_files(snapshot),
    )

