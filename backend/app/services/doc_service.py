from pathlib import Path

from app.config import settings


DOC_TITLES = {
    "learning_guide": "学习路线",
    "daily_plan": "每日学习计划",
    "interview_questions": "面试问题",
    "agent_trace": "Agent 执行轨迹",
}


def save_documents(job_id: str, documents: dict[str, str]) -> dict[str, Path]:
    output_dir = settings.docs_path / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = {}
    for name, content in documents.items():
        path = output_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        saved[name] = path
    return saved


def read_documents(job_id: str) -> list[dict[str, str]]:
    output_dir = settings.docs_path / job_id
    result = []
    for name, title in DOC_TITLES.items():
        path = output_dir / f"{name}.md"
        if path.exists():
            result.append(
                {
                    "name": name,
                    "title": title,
                    "filename": path.name,
                    "content": path.read_text(encoding="utf-8"),
                    "download_url": f"/api/docs/{job_id}/{name}/download",
                }
            )
    return result


def get_document_path(job_id: str, doc_type: str) -> Path:
    if doc_type not in DOC_TITLES:
        raise ValueError("未知文档类型。")
    return settings.docs_path / job_id / f"{doc_type}.md"
