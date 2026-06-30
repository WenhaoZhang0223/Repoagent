from pathlib import Path

from app.config import settings


DOC_TITLES = {
    "zh": {
        "learning_guide": "学习路线",
        "daily_plan": "每日学习计划",
        "interview_questions": "面试问题",
        "agent_trace": "Agent 执行轨迹",
    },
    "en": {
        "learning_guide": "Learning Guide",
        "daily_plan": "Daily Study Plan",
        "interview_questions": "Interview Questions",
        "agent_trace": "Agent Trace",
    },
}

DOC_TYPES = set(DOC_TITLES["zh"])


def save_documents(job_id: str, documents: dict[str, str]) -> dict[str, Path]:
    output_dir = settings.docs_path / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = {}
    for name, content in documents.items():
        path = output_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        saved[name] = path
    return saved


def read_documents(job_id: str, language: str = "zh") -> list[dict[str, str]]:
    output_dir = settings.docs_path / job_id
    result = []
    titles = DOC_TITLES.get(language, DOC_TITLES["zh"])
    for name, title in titles.items():
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
    if doc_type not in DOC_TYPES:
        raise ValueError("未知文档类型。")
    return settings.docs_path / job_id / f"{doc_type}.md"
