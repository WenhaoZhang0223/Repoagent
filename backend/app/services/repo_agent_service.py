import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.config import settings
from app.services.analyzer_service import ProjectSummary


DOC_SPECS = {
    "learning_guide": {
        "filename": "learning_guide.md",
        "goal": "Generate a project introduction, tech stack explanation, learning order, key module notes, and terminology.",
    },
    "daily_plan": {
        "filename": "daily_plan.md",
        "goal": "Generate a 5-10 day learning plan with goals, reading focus, exercises, and deliverables.",
    },
    "interview_questions": {
        "filename": "interview_questions.md",
        "goal": "Generate project interview questions, reference answers, and follow-up directions.",
    },
}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_repo_overview",
            "description": "Read the repository name, inferred tech stack, and top-level file tree.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_available_files",
            "description": "List files that were selected as useful context for the model.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_repo_file",
            "description": "Read one selected repository file by path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Repository-relative file path."}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_finding",
            "description": "Record a concrete finding from inspected repository material.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "finding": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["topic", "finding", "evidence"],
                "additionalProperties": False,
            },
        },
    },
]


SYSTEM_PROMPT = """
You are Repo Learning Agent.
Your job is to inspect a GitHub repository through tools, decide what information is needed,
record concrete findings, and then generate Chinese Markdown learning documents.

Rules:
- Use tools before writing the final answer.
- Base conclusions on repository material and explicit inference.
- Do not invent files, APIs, commands, or behavior.
- Prefer specific module-level observations over generic advice.
- Final output must be a JSON object with keys: learning_guide, daily_plan, interview_questions.
""".strip()


@dataclass
class AgentRun:
    goal: str
    findings: list[dict[str, str]]
    trace: list[str]


def _create_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("The backend is missing OPENAI_API_KEY. Configure backend/.env or set USE_MOCK_LLM=true.")

    client_kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**client_kwargs)


def _selected_files(summary: ProjectSummary) -> dict[str, str]:
    files: dict[str, str] = {}
    current_path: str | None = None
    current_lines: list[str] = []

    for line in summary.file_summaries.splitlines():
        if line.startswith("## "):
            if current_path and current_lines:
                files[current_path] = "\n".join(current_lines).strip("`\n ")
            current_path = line.removeprefix("## ").strip()
            current_lines = []
            continue

        if current_path and line.strip() != "```text":
            current_lines.append(line)

    if current_path and current_lines:
        files[current_path] = "\n".join(current_lines).strip("`\n ")

    return files


def _tool_result(summary: ProjectSummary, files: dict[str, str], findings: list[dict[str, str]], name: str, args: dict[str, Any]) -> str:
    if name == "inspect_repo_overview":
        return json.dumps(
            {
                "repo_name": summary.repo_name,
                "tech_stack": summary.tech_stack,
                "file_tree": summary.file_tree[:12000],
            },
            ensure_ascii=False,
        )

    if name == "list_available_files":
        return json.dumps({"files": list(files.keys())}, ensure_ascii=False)

    if name == "read_repo_file":
        path = str(args.get("path", "")).strip()
        content = files.get(path)
        if content is None:
            return json.dumps({"error": f"File is not available: {path}", "available_files": list(files.keys())}, ensure_ascii=False)
        return json.dumps({"path": path, "content": content[:12000]}, ensure_ascii=False)

    if name == "record_finding":
        finding = {
            "topic": str(args.get("topic", "")).strip(),
            "finding": str(args.get("finding", "")).strip(),
            "evidence": str(args.get("evidence", "")).strip(),
        }
        findings.append(finding)
        return json.dumps({"recorded": finding}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)


def _run_agent(client: OpenAI, summary: ProjectSummary, repo_url: str, goal: str) -> AgentRun:
    files = _selected_files(summary)
    findings: list[dict[str, str]] = []
    trace: list[str] = []
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Repository: {repo_url}\n"
                f"User goal: {goal}\n"
                "First decide what to inspect, call tools, record findings, then return JSON."
            ),
        },
    ]

    for _ in range(8):
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            break

        for call in message.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            trace.append(f"{call.function.name}({json.dumps(args, ensure_ascii=False)})")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": _tool_result(summary, files, findings, call.function.name, args),
                }
            )

    return AgentRun(goal=goal, findings=findings, trace=trace)


def _agent_context(summary: ProjectSummary, run: AgentRun) -> str:
    return json.dumps(
        {
            "repo_name": summary.repo_name,
            "user_goal": run.goal,
            "tech_stack": summary.tech_stack,
            "file_tree": summary.file_tree[:12000],
            "findings": run.findings,
            "tool_trace": run.trace,
            "fallback_excerpts": summary.file_summaries[:30000],
        },
        ensure_ascii=False,
    )


def _generate_final_documents(client: OpenAI, summary: ProjectSummary, repo_url: str, run: AgentRun) -> dict[str, str]:
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"GitHub repo: {repo_url}\n\n"
                    f"User goal: {run.goal}\n\n"
                    "Use this agent context to generate final Chinese Markdown documents tailored to the user goal.\n"
                    f"Document specs: {json.dumps(DOC_SPECS, ensure_ascii=False)}\n\n"
                    f"Agent context:\n{_agent_context(summary, run)}"
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    raw = response.choices[0].message.content or "{}"
    parsed = json.loads(raw)
    return {name: str(parsed.get(name, "")).strip() for name in DOC_SPECS}


def _agent_trace_document(run: AgentRun) -> str:
    finding_lines = [
        f"- **{item.get('topic', 'Finding')}**: {item.get('finding', '')}\n  - Evidence: {item.get('evidence', '')}"
        for item in run.findings
    ]
    trace_lines = [f"{index}. `{item}`" for index, item in enumerate(run.trace, start=1)]
    return "\n".join(
        [
            "# Agent 执行轨迹",
            "",
            f"用户目标：{run.goal}",
            "",
            "这份文档记录模型为了完成目标自主选择并调用的工具。",
            "",
            "## 工具调用",
            "",
            "\n".join(trace_lines) if trace_lines else "- 未记录工具调用。",
            "",
            "## 关键发现",
            "",
            "\n".join(finding_lines) if finding_lines else "- 未记录关键发现。",
        ]
    )


def generate_documents(summary: ProjectSummary, repo_url: str, goal: str | None = None) -> dict[str, str]:
    resolved_goal = (goal or "").strip() or "生成适合学习、复习和面试准备的项目文档。"
    if settings.use_mock_llm:
        return _mock_documents(summary, repo_url, resolved_goal)

    client = _create_client()
    run = _run_agent(client, summary, repo_url, resolved_goal)
    documents = _generate_final_documents(client, summary, repo_url, run)
    documents["agent_trace"] = _agent_trace_document(run)
    return documents


def _mock_documents(summary: ProjectSummary, repo_url: str, goal: str) -> dict[str, str]:
    tech = ", ".join(summary.tech_stack)
    run = AgentRun(
        goal=goal,
        findings=[
            {
                "topic": "Project purpose",
                "finding": "Mock mode simulates an agent finding from the repository snapshot.",
                "evidence": "USE_MOCK_LLM=true",
            }
        ],
        trace=[
            "inspect_repo_overview({})",
            "list_available_files({})",
            'record_finding({"topic":"Project purpose","finding":"Mock mode simulates an agent finding.","evidence":"USE_MOCK_LLM=true"})',
        ],
    )
    return {
        "learning_guide": f"""# 项目学习指南

Repo: {repo_url}

## 项目介绍

这是 mock 模式下生成的演示文档。当前识别到的技术栈：{tech}。

## Agent 化说明

当前生成流程已经按 agent 方式组织：先围绕目标选择工具读取仓库信息，再记录发现，最后生成文档。
""",
        "daily_plan": """# 每日学习计划

## Day 1

阅读 README、依赖配置和入口文件，确认项目目标。

## Day 2

跟踪核心模块，把输入、处理和输出串起来。
""",
        "interview_questions": """# 项目面试题

## 1. 这个项目为什么算 Agent-style 应用？

参考答案：模型会围绕目标选择工具读取仓库材料、记录发现，并基于中间结果生成输出。
""",
        "agent_trace": _agent_trace_document(run),
    }
