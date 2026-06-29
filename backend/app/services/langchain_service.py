from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import settings
from app.services.analyzer_service import ProjectSummary


DOC_SPECS = {
    "learning_guide": {
        "title": "learning_guide.md",
        "requirement": "项目介绍、技术栈、学习顺序、专业词解释。",
    },
    "daily_plan": {
        "title": "daily_plan.md",
        "requirement": "按天拆分一个 5-10 天的快速学习路线，每天要有目标、阅读重点和产出。",
    },
    "interview_questions": {
        "title": "interview_questions.md",
        "requirement": "项目相关面试题、参考答案、追问方向，覆盖架构、技术栈和代码细节。",
    },
}


SYSTEM_PROMPT = """
你是资深软件工程学习教练。你会根据 GitHub 仓库的 README、目录结构、配置文件和关键源码，
为初中级开发者生成中文学习材料。

输出要求：
- 使用 Markdown。
- 内容具体、可执行，不要泛泛而谈。
- 如果项目信息不足，请明确标注推断依据和不确定点。
- 不要编造不存在的文件、接口或功能。
""".strip()


USER_PROMPT = """
GitHub repo: {repo_url}

请生成 {doc_title}。
文档要求：{requirement}

项目名称：
{repo_name}

识别到的技术栈：
{tech_stack}

目录结构：
{file_tree}

关键文件摘录：
{file_summaries}
""".strip()


def _summary_context(summary: ProjectSummary) -> dict[str, str]:
    return {
        "repo_name": summary.repo_name,
        "tech_stack": ", ".join(summary.tech_stack),
        "file_tree": summary.file_tree[:12000],
        "file_summaries": summary.file_summaries[:60000],
    }


# Clean LangChain implementation used by the app. This block intentionally
# redefines the prompt/config above because the earlier block may display as
# mojibake in some Windows terminals.
DOC_SPECS = {
    "learning_guide": {
        "title": "learning_guide.md",
        "requirement": "项目介绍、技术栈、学习顺序、专业词解释。",
    },
    "daily_plan": {
        "title": "daily_plan.md",
        "requirement": "按天拆分一个 5-10 天的快速学习路线，每天要有目标、阅读重点和产出。",
    },
    "interview_questions": {
        "title": "interview_questions.md",
        "requirement": "项目相关面试题、参考答案、追问方向，覆盖架构、技术栈和代码细节。",
    },
}


SYSTEM_PROMPT = """
你是资深软件工程学习教练。你会根据 GitHub 仓库的 README、目录结构、配置文件和关键源码，
为初中级开发者生成中文学习材料。

输出要求：
- 使用 Markdown。
- 内容具体、可执行，不要泛泛而谈。
- 如果项目信息不足，请明确标注推断依据和不确定点。
- 不要编造不存在的文件、接口或功能。
""".strip()


USER_PROMPT = """
GitHub repo: {repo_url}

请生成 {doc_title}。
文档要求：{requirement}

项目名称：
{repo_name}

识别到的技术栈：
{tech_stack}

目录结构：
{file_tree}

关键文件摘录：
{file_summaries}
""".strip()


def _summary_context(summary: ProjectSummary) -> dict[str, str]:
    return {
        "repo_name": summary.repo_name,
        "tech_stack": ", ".join(summary.tech_stack),
        "file_tree": summary.file_tree[:12000],
        "file_summaries": summary.file_summaries[:60000],
    }


def _build_llm() -> ChatOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError(
            "后端缺少 OPENAI_API_KEY。请在 backend/.env 中配置，"
            "或设置 USE_MOCK_LLM=true 用于本地演示。"
        )

    kwargs = {
        "api_key": settings.openai_api_key,
        "model": settings.openai_model,
        "temperature": 0.4,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url

    return ChatOpenAI(**kwargs)


def _build_document_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("user", USER_PROMPT),
        ]
    )
    return prompt | _build_llm() | StrOutputParser()


def generate_documents(summary: ProjectSummary, repo_url: str) -> dict[str, str]:
    if settings.use_mock_llm:
        return _mock_documents(summary, repo_url)

    context = _summary_context(summary)
    chain = _build_document_chain()
    documents: dict[str, str] = {}

    for doc_name, spec in DOC_SPECS.items():
        documents[doc_name] = chain.invoke(
            {
                "repo_url": repo_url,
                "doc_title": spec["title"],
                "requirement": spec["requirement"],
                **context,
            }
        )

    return documents


def _build_llm() -> ChatOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError(
            "后端缺少 OPENAI_API_KEY。请在 backend/.env 中配置，"
            "或设置 USE_MOCK_LLM=true 用于本地演示。"
        )

    kwargs = {
        "api_key": settings.openai_api_key,
        "model": settings.openai_model,
        "temperature": 0.4,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url

    return ChatOpenAI(**kwargs)


def _build_document_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("user", USER_PROMPT),
        ]
    )
    return prompt | _build_llm() | StrOutputParser()


def generate_documents(summary: ProjectSummary, repo_url: str) -> dict[str, str]:
    if settings.use_mock_llm:
        return _mock_documents(summary, repo_url)

    context = _summary_context(summary)
    chain = _build_document_chain()
    documents: dict[str, str] = {}

    for doc_name, spec in DOC_SPECS.items():
        documents[doc_name] = chain.invoke(
            {
                "repo_url": repo_url,
                "doc_title": spec["title"],
                "requirement": spec["requirement"],
                **context,
            }
        )

    return documents


def _mock_documents(summary: ProjectSummary, repo_url: str) -> dict[str, str]:
    tech = ", ".join(summary.tech_stack)
    return {
        "learning_guide": f"""# 项目学习指南

Repo: {repo_url}

## 项目介绍

这是一个根据仓库文件结构和关键配置生成的演示版学习文档。当前识别到的技术栈：{tech}。

## 建议学习顺序

1. 先阅读 README 和配置文件，理解项目目标、启动方式和依赖。
2. 查看入口文件，确认请求、页面或命令行流程从哪里开始。
3. 沿着核心模块阅读业务代码，记录数据结构和模块边界。
4. 运行测试或示例，验证自己对代码路径的理解。

## 专业词解释

- 入口文件：应用启动或页面渲染最先执行的文件。
- 依赖配置：记录项目需要安装哪些库和工具的文件。
- 模块边界：不同功能代码之间的职责分工。
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

## 3. 为什么 API Key 不能放在前端？

参考答案：前端代码会暴露给浏览器用户，API Key 必须由后端通过环境变量读取和使用。

追问方向：生产环境还需要哪些权限和限流设计？
""",
    }
