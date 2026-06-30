from enum import Enum
from typing import Literal

from pydantic import BaseModel, HttpUrl


class JobStatus(str, Enum):
    queued = "queued"
    cloning = "cloning"
    analyzing = "analyzing"
    generating = "generating"
    completed = "completed"
    failed = "failed"


class GenerateRequest(BaseModel):
    repo_url: HttpUrl
    goal: str | None = None
    language: Literal["zh", "en"] = "zh"


class GenerateResponse(BaseModel):
    job_id: str
    status: JobStatus


class DocumentPayload(BaseModel):
    name: Literal["learning_guide", "daily_plan", "interview_questions", "agent_trace"]
    title: str
    filename: str
    content: str
    download_url: str


class JobResponse(BaseModel):
    job_id: str
    repo_url: str
    status: JobStatus
    message: str
    error: str | None = None
    documents: list[DocumentPayload] = []


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    messages: list[ChatMessage] = []
    document_title: str | None = None
    document_content: str | None = None
    language: Literal["zh", "en"] = "zh"


class ChatResponse(BaseModel):
    answer: str
