from openai import OpenAI

from app.config import settings
from app.services.analyzer_service import ProjectSummary


def _create_client() -> OpenAI:
    client_kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**client_kwargs)


DOC_SPECS = {
    "learning_guide": "生成 learning_guide.md，包含项目介绍、技术栈、学习顺序、专业词解释。",
    "daily_plan": "生成 daily_plan.md，按天拆分一个 5-10 天的快速学习路线。",
    "interview_questions": "生成 interview_questions.md，包含项目相关面试题、参考答案、追问方向。",
}


def _summary_context(summary: ProjectSummary) -> str:
    return f"""
Repo name: {summary.repo_name}
Tech stack: {", ".join(summary.tech_stack)}

File tree:
{summary.file_tree[:12000]}

Selected file excerpts:
{summary.file_summaries[:60000]}
""".strip()


def generate_documents(summary: ProjectSummary, repo_url: str) -> dict[str, str]:
    if settings.use_mock_llm:
        return _mock_documents(summary, repo_url)
    if not settings.openai_api_key:
        raise RuntimeError("后端缺少 OPENAI_API_KEY。请在 backend/.env 中配置，或设置 USE_MOCK_LLM=true 用于本地演示。")

    client = _create_client()
    context = _summary_context(summary)
    docs: dict[str, str] = {}

    for doc_name, requirement in DOC_SPECS.items():
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "你是资深软件工程学习教练。请用中文输出结构清晰、可执行、Markdown 格式良好的学习文档。",
                },
                {
                    "role": "user",
                    "content": f"GitHub repo: {repo_url}\n\n{requirement}\n\n项目分析材料如下：\n{context}",
                },
            ],
            temperature=0.4,
        )
        docs[doc_name] = response.choices[0].message.content or ""

    return docs


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
        "interview_questions": f"""# 项目面试题

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
