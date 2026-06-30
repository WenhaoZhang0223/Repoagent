from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.models import ChatMessage


SYSTEM_PROMPTS = {
    "zh": """
你是 RepoAgent，一个面向 GitHub 仓库理解、代码学习、项目文档整理、简历项目表达和面试复盘的 AI 助手。

身份要求：
- 不要把自己介绍成“中文 AI 学习助手”或只服务中文用户。
- 你的默认身份是 RepoAgent，可以中英文工作。
- 用户用英文提问时用英文回答，用户用中文提问时用中文回答。

回答要求：
- 语气自然、具体、可执行，避免空泛介绍。
- 如果用户问题和给定文档相关，优先基于文档回答；不要编造文档里没有的事实。
- 如果信息不足，直接说明缺什么，并给出下一步建议。
- 可以回答通用编程、仓库架构、学习计划、简历描述、项目亮点和面试问题。
""".strip(),
    "en": """
You are RepoAgent, an AI assistant for understanding GitHub repositories, learning codebases, organizing project documents, shaping resume project stories, and preparing for interviews.

Identity rules:
- Do not introduce yourself as a "Chinese AI learning assistant" or as an assistant only for Chinese users.
- Your default identity is RepoAgent, and you can work in both English and Chinese.
- Match the user's language when it is clear.

Response requirements:
- Be natural, specific, and actionable.
- If the user's question relates to the provided document, prioritize the document and do not invent facts that are not present.
- If information is missing, say what is missing and suggest the next useful step.
- You can help with programming, repository architecture, study plans, resume wording, project highlights, and interview practice.
""".strip(),
}


def _build_llm() -> ChatOpenAI: # checks for OPENAI_API_KEY and USE_MOCK_LLM
    if not settings.openai_api_key:
        raise RuntimeError("The backend is missing OPENAI_API_KEY. Configure backend/.env or set USE_MOCK_LLM=true.")

    kwargs = {
        "api_key": settings.openai_api_key,
        "model": settings.openai_model,
        "temperature": 0.5,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**kwargs)


def _mock_answer(question: str, document_title: str | None, language: str) -> str:
    if language == "en":
        source = f"I will prioritize the content in {document_title}." if document_title else "This is a general chat answer."
        return (
            "This is a mock chat response from RepoAgent.\n\n"
            f"{source}\n\n"
            f"Your question: {question}\n\n"
            "To get a real AI answer, set USE_MOCK_LLM=false and configure OPENAI_API_KEY."
        )

    source = f"我会优先参考《{document_title}》里的内容。" if document_title else "当前是通用问答。"
    return (
        "这是 RepoAgent 在 mock 模式下的聊天回复。\n\n"
        f"{source}\n\n"
        f"你的问题是：{question}\n\n"
        "如果要获得真实 AI 回答，请把 USE_MOCK_LLM 设为 false，并配置 OPENAI_API_KEY。"
    )


def _content_to_text(content: str | list[object]) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(str(item) for item in content)


def answer_question(
    question: str,
    messages: list[ChatMessage],
    document_title: str | None = None,
    document_content: str | None = None,
    language: str = "zh",
) -> str:
    normalized_language = language if language in SYSTEM_PROMPTS else "zh"

    if settings.use_mock_llm:
        return _mock_answer(question, document_title, normalized_language)

    langchain_messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPTS[normalized_language])]

    if document_content:
        if normalized_language == "en":
            context = (
                f"Document currently viewed by the user: {document_title or 'Untitled document'}\n\n"
                f"Document content:\n{document_content[:24000]}"
            )
        else:
            context = (
                f"当前用户正在查看的文档标题：{document_title or '未命名文档'}\n\n"
                f"文档内容：\n{document_content[:24000]}"
            )
        langchain_messages.append(SystemMessage(content=context))

    for message in messages[-8:]:
        content = message.content[:4000]
        if message.role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        else:
            langchain_messages.append(HumanMessage(content=content))

    langchain_messages.append(HumanMessage(content=question[:4000]))

    response = _build_llm().invoke(langchain_messages)
    return _content_to_text(response.content)
