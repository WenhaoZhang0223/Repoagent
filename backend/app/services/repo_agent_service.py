import json
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI

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

LANGUAGE_INSTRUCTIONS = {
    "zh": "Write all final Markdown documents in Simplified Chinese.",
    "en": "Write all final Markdown documents in clear, natural English.",
}

SYSTEM_PROMPT = """
You are Repo Learning Agent.
Your job is to inspect a GitHub repository through tools, decide what information is needed,
record concrete findings, and then generate Markdown learning documents.

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


def _build_llm(temperature: float) -> ChatOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("The backend is missing OPENAI_API_KEY. Configure backend/.env or set USE_MOCK_LLM=true.")

    client_kwargs = {
        "api_key": settings.openai_api_key,
        "model": settings.openai_model,
        "temperature": temperature,
    }
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**client_kwargs)


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


def _build_tools(summary: ProjectSummary, files: dict[str, str], findings: list[dict[str, str]]) -> list[BaseTool]:
    @tool
    def inspect_repo_overview() -> str:
        """Read the repository name, inferred tech stack, and top-level file tree."""
        return json.dumps(
            {
                "repo_name": summary.repo_name,
                "tech_stack": summary.tech_stack,
                "file_tree": summary.file_tree[:12000],
            },
            ensure_ascii=False,
        )

    @tool
    def list_available_files() -> str:
        """List files that were selected as useful context for the model."""
        return json.dumps({"files": list(files.keys())}, ensure_ascii=False)

    @tool
    def read_repo_file(path: str) -> str:
        """Read one selected repository file by repository-relative path."""
        path = path.strip()
        content = files.get(path)
        if content is None:
            return json.dumps({"error": f"File is not available: {path}", "available_files": list(files.keys())}, ensure_ascii=False)
        return json.dumps({"path": path, "content": content[:12000]}, ensure_ascii=False)

    @tool
    def record_finding(topic: str, finding: str, evidence: str) -> str:
        """Record a concrete finding from inspected repository material."""
        finding = {
            "topic": topic.strip(),
            "finding": finding.strip(),
            "evidence": evidence.strip(),
        }
        findings.append(finding)
        return json.dumps({"recorded": finding}, ensure_ascii=False)

    return [inspect_repo_overview, list_available_files, read_repo_file, record_finding]


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)
    return str(content)


def _event_text(language: str, zh: str, en: str) -> str:
    return en if language == "en" else zh


def _describe_tool_call(tool_name: str, args: dict[str, Any], language: str) -> str:
    if tool_name == "inspect_repo_overview":
        return _event_text(language, "查看仓库概览和技术栈。", "Inspecting the repository overview and tech stack.")
    if tool_name == "list_available_files":
        return _event_text(language, "列出可读取的关键文件。", "Listing key files available to inspect.")
    if tool_name == "read_repo_file":
        path = str(args.get("path", "")).strip() or "unknown"
        return _event_text(language, f"读取文件：{path}", f"Reading file: {path}")
    if tool_name == "record_finding":
        topic = str(args.get("topic", "")).strip() or "finding"
        return _event_text(language, f"记录关键发现：{topic}", f"Recording key finding: {topic}")
    return _event_text(language, f"调用工具：{tool_name}", f"Calling tool: {tool_name}")


def _run_agent(
    llm: ChatOpenAI,
    summary: ProjectSummary,
    repo_url: str,
    goal: str,
    language: str,
    event_callback: Callable[[str], None] | None = None,
) -> AgentRun:
    files = _selected_files(summary)
    findings: list[dict[str, str]] = []
    trace: list[str] = []
    tools = _build_tools(summary, files, findings)
    tool_map = {item.name: item for item in tools}
    tool_calling_llm = llm.bind_tools(tools)
    language_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["zh"])
    messages: list[BaseMessage] = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Repository: {repo_url}\n"
                f"User goal: {goal}\n"
                f"Output language: {language_instruction}\n"
                "First decide what to inspect, call tools, record findings, then return JSON."
            ),
        ),
    ]

    if event_callback:
        event_callback(_event_text(language, "Agent 开始根据目标选择需要查看的仓库材料。", "The agent is choosing which repository materials to inspect."))

    for _ in range(8):
        message = tool_calling_llm.invoke(messages)
        messages.append(message)

        if not isinstance(message, AIMessage) or not message.tool_calls:
            break

        for call in message.tool_calls:
            tool_name = call["name"]
            args = call.get("args") or {}
            trace.append(f"{tool_name}({json.dumps(args, ensure_ascii=False)})")
            if event_callback:
                event_callback(_describe_tool_call(tool_name, args, language))
            selected_tool = tool_map.get(tool_name)
            if selected_tool is None:
                result = json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
            else:
                result = selected_tool.invoke(args)
            messages.append(
                ToolMessage(
                    content=_content_to_text(result),
                    tool_call_id=call["id"],
                    name=tool_name,
                )
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


def _generate_final_documents(llm: ChatOpenAI, summary: ProjectSummary, repo_url: str, run: AgentRun, language: str) -> dict[str, str]:
    language_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["zh"])
    response = llm.bind(response_format={"type": "json_object"}).invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"GitHub repo: {repo_url}\n\n"
                    f"User goal: {run.goal}\n\n"
                    f"{language_instruction}\n"
                    "Use this agent context to generate final Markdown documents tailored to the user goal.\n"
                    f"Document specs: {json.dumps(DOC_SPECS, ensure_ascii=False)}\n\n"
                    f"Agent context:\n{_agent_context(summary, run)}"
                ),
            ),
        ],
    )
    raw = _content_to_text(response.content) or "{}"
    parsed = json.loads(raw)
    return {name: str(parsed.get(name, "")).strip() for name in DOC_SPECS}


def _agent_trace_document(run: AgentRun, language: str) -> str:
    finding_lines = [
        f"- **{item.get('topic', 'Finding')}**: {item.get('finding', '')}\n  - Evidence: {item.get('evidence', '')}"
        for item in run.findings
    ]
    trace_lines = [f"{index}. `{item}`" for index, item in enumerate(run.trace, start=1)]

    if language == "en":
        return "\n".join(
            [
                "# Agent Trace",
                "",
                f"User goal: {run.goal}",
                "",
                "This document records the tools selected and called by the model while completing the goal.",
                "",
                "## Tool Calls",
                "",
                "\n".join(trace_lines) if trace_lines else "- No tool calls were recorded.",
                "",
                "## Key Findings",
                "",
                "\n".join(finding_lines) if finding_lines else "- No key findings were recorded.",
            ]
        )

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


def generate_documents(
    summary: ProjectSummary,
    repo_url: str,
    goal: str | None = None,
    language: str = "zh",
    event_callback: Callable[[str], None] | None = None,
) -> dict[str, str]:
    normalized_language = language if language in LANGUAGE_INSTRUCTIONS else "zh"
    default_goal = (
        "Generate project documents for learning, review, resume preparation, and interview practice."
        if normalized_language == "en"
        else "生成适合学习、复习和面试准备的项目文档。"
    )
    resolved_goal = (goal or "").strip() or default_goal

    if settings.use_mock_llm:
        if event_callback:
            event_callback(_event_text(normalized_language, "mock 模式：使用演示数据生成文档。", "Mock mode: generating documents from demo data."))
        return _mock_documents(summary, repo_url, resolved_goal, normalized_language)

    agent_llm = _build_llm(temperature=0.2)
    document_llm = _build_llm(temperature=0.4)
    run = _run_agent(agent_llm, summary, repo_url, resolved_goal, normalized_language, event_callback)
    if event_callback:
        event_callback(_event_text(normalized_language, "整理工具结果，生成三份 Markdown 文档。", "Organizing tool results and generating three Markdown documents."))
    documents = _generate_final_documents(document_llm, summary, repo_url, run, normalized_language)
    documents["agent_trace"] = _agent_trace_document(run, normalized_language)
    return documents


def _mock_documents(summary: ProjectSummary, repo_url: str, goal: str, language: str) -> dict[str, str]:
    tech = ", ".join(summary.tech_stack) or "unknown"
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

    if language == "en":
        return {
            "learning_guide": f"""# Project Learning Guide

Repo: {repo_url}

## Project Overview

This is a mock-mode learning document generated from the repository snapshot. Detected tech stack: {tech}.

## Suggested Learning Order

1. Read the README and dependency configuration to understand the project goal, setup flow, and runtime requirements.
2. Find the entry points and trace how requests, pages, commands, or background tasks begin.
3. Follow the core modules and record data structures, module boundaries, and important decisions.
4. Run tests or examples to validate your understanding of the main code paths.
""",
            "daily_plan": f"""# Daily Study Plan

## Day 1

Read the README, install dependencies, and run the project.

## Day 2

Map the directory structure and mark the entry files and core modules.

## Day 3

Trace the main workflow from input to output.

## Day 4

Pick one feature and write down the responsibilities of its key functions.

## Day 5

Review weak spots in the detected stack: {tech}.
""",
            "interview_questions": """# Project Interview Questions

## 1. What is the core purpose of this project?

Reference answer: Infer the project purpose from repository structure, configuration, and key source files, then explain how the stack supports that purpose.

Follow-up: How would you handle a large repository without sending irrelevant files to the model?

## 2. How does the project identify its tech stack?

Reference answer: It can combine dependency files, file extensions, framework config files, and entry-point code.

Follow-up: What fallback would you add when stack detection is wrong?
""",
            "agent_trace": _agent_trace_document(run, language),
        }

    return {
        "learning_guide": f"""# 项目学习指南

Repo: {repo_url}

## 项目介绍

这是 mock 模式下生成的演示文档。当前识别到的技术栈：{tech}。

## 建议学习顺序

1. 阅读 README 和配置文件，理解项目目标、启动方式和依赖。
2. 查看入口文件，确认请求、页面或命令行流程从哪里开始。
3. 沿着核心模块阅读业务代码，记录数据结构和模块边界。
4. 运行测试或示例，验证自己对代码路径的理解。
""",
        "daily_plan": f"""# 每日学习计划

## Day 1

阅读 README、安装依赖、跑通项目。

## Day 2

梳理目录结构，标记入口文件和核心模块。

## Day 3

阅读主要业务流程，画出输入到输出的链路。

## Day 4

挑选一个功能做代码级跟踪，并写下关键函数职责。

## Day 5

整理技术栈 {tech} 的薄弱点，补齐相关基础知识。
""",
        "interview_questions": """# 项目面试题

## 1. 这个项目的核心功能是什么？

参考答案：根据仓库结构、配置和关键源码推断项目目标，并围绕技术栈生成学习资料。

追问方向：如何处理大型仓库？如何避免把无关文件塞进模型？

## 2. 项目如何识别技术栈？

参考答案：可以从依赖配置、文件扩展名、框架配置文件和入口代码综合判断。

追问方向：识别错误时如何兜底？如何支持更多语言？
""",
        "agent_trace": _agent_trace_document(run, language),
    }
