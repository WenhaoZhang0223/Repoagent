from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.models import ChatRequest, ChatResponse, GenerateRequest, GenerateResponse, JobResponse, JobStatus
from app.services.analyzer_service import analyze_snapshot
from app.services.chat_service import answer_question
from app.services.doc_service import get_document_path, read_documents, save_documents
from app.services.repo_agent_service import generate_documents
from app.services.repo_service import build_snapshot, cleanup_repo, clone_repo, validate_github_url


@dataclass
class JobState:
    job_id: str
    repo_url: str
    goal: str
    language: str
    status: JobStatus
    message: str
    error: str | None = None


app = FastAPI(title="Repo Learning Agent API")
executor = ThreadPoolExecutor(max_workers=2)
jobs: dict[str, JobState] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def localized(language: str, zh: str, en: str) -> str:
    return en if language == "en" else zh


@app.on_event("startup")
def ensure_docs_dir() -> None:
    settings.docs_path.mkdir(parents=True, exist_ok=True)


@app.post("/api/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    try:
        repo_url = validate_github_url(str(request.repo_url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = uuid4().hex
    jobs[job_id] = JobState(
        job_id=job_id,
        repo_url=repo_url,
        goal=(request.goal or "").strip()
        or localized(
            request.language,
            "生成适合学习、复习和面试准备的项目文档。",
            "Generate project documents for learning, review, resume preparation, and interview practice.",
        ),
        language=request.language,
        status=JobStatus.queued,
        message=localized(request.language, "任务已创建，等待处理。", "Task created and waiting to run."),
    )
    executor.submit(run_job, job_id)
    return GenerateResponse(job_id=job_id, status=JobStatus.queued)


@app.get("/api/status/{job_id}", response_model=JobResponse)
def status(job_id: str) -> JobResponse:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return JobResponse(
        job_id=job.job_id,
        repo_url=job.repo_url,
        status=job.status,
        message=job.message,
        error=job.error,
        documents=read_documents(job_id, job.language) if job.status == JobStatus.completed else [],
    )


@app.get("/api/docs/{job_id}/{doc_type}/download")
def download_doc(job_id: str, doc_type: str) -> FileResponse:
    path = get_document_path(job_id, doc_type)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文档不存在。")
    return FileResponse(Path(path), filename=path.name, media_type="text/markdown; charset=utf-8")


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空。")

    try:
        answer = answer_question(
            question=question,
            messages=request.messages,
            document_title=request.document_title,
            document_content=request.document_content,
            language=request.language,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(answer=answer)


def update_job(job_id: str, status_value: JobStatus, message: str, error: str | None = None) -> None:
    job = jobs[job_id]
    job.status = status_value
    job.message = message
    job.error = error


def run_job(job_id: str) -> None:
    repo_root: Path | None = None
    job = jobs[job_id]
    try:
        update_job(job_id, JobStatus.cloning, localized(job.language, "正在 clone GitHub repo。", "Cloning the GitHub repository."))
        repo_root = clone_repo(job.repo_url)

        update_job(
            job_id,
            JobStatus.analyzing,
            localized(job.language, "正在扫描 README、目录结构、配置文件和关键源码。", "Scanning the README, file tree, config files, and key source code."),
        )
        snapshot = build_snapshot(repo_root, settings.max_file_bytes, settings.max_total_chars)
        summary = analyze_snapshot(snapshot)

        update_job(
            job_id,
            JobStatus.generating,
            localized(job.language, "Agent 正在根据目标选择工具并生成 Markdown 文档。", "The agent is selecting tools and generating Markdown documents for your goal."),
        )
        documents = generate_documents(summary, job.repo_url, job.goal, job.language)
        save_documents(job_id, documents)

        update_job(job_id, JobStatus.completed, localized(job.language, "文档已生成。", "Documents generated."))
    except Exception as exc:
        update_job(job_id, JobStatus.failed, localized(job.language, "生成失败。", "Generation failed."), str(exc))
    finally:
        if repo_root is not None:
            cleanup_repo(repo_root)
