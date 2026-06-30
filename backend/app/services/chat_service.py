from openai import OpenAI

from app.config import settings
from app.models import ChatMessage


SYSTEM_PROMPTS = {
    "zh": """
你是 RepoAgent，一个面向 GitHub 项目学习、简历项目整理和面试复盘的 AI 助手。
回答要求：
- 默认用简洁中文回答，语气自然、具体、可执行。
- 如果用户问题和给定文档相关，优先基于文档回答；不要编造文档里没有的事实。
- 如果信息不足，直接说明缺什么，并给出下一步建议。
- 可以回答通用编程、简历、学习计划、项目理解和面试问题。
""".strip(),
    "en": """
You are RepoAgent, an AI assistant for learning GitHub projects, shaping resume project stories, and preparing for interviews.
Response requirements:
- Answer in concise, natural, actionable English by default.
- If the user's question relates to the provided document, prioritize the document and do not invent facts that are not present.
- If information is missing, say what is missing and suggest the next useful step.
- You can help with programming, resumes, study plans, project understanding, and interview practice.
""".strip(),
}


def _create_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("The backend is missing OPENAI_API_KEY. Configure backend/.env or set USE_MOCK_LLM=true.")

    client_kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**client_kwargs)


def _mock_answer(question: str, document_title: str | None, language: str) -> str:
    if language == "en":
        source = f"I will prioritize the content in {document_title}." if document_title else "This is a general chat answer."
        return (
            "This is a mock chat response.\n\n"
            f"{source}\n\n"
            f"Your question: {question}\n\n"
            "To get a real AI answer, set USE_MOCK_LLM=false and configure OPENAI_API_KEY."
        )

    source = f"我会优先参考《{document_title}》里的内容。" if document_title else "当前是通用问答。"
    return (
        "这是 mock 模式下的聊天回复。\n\n"
        f"{source}\n\n"
        f"你的问题是：{question}\n\n"
        "如果要获得真实 AI 回答，请把 USE_MOCK_LLM 设为 false，并配置 OPENAI_API_KEY。"
    )


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

    client = _create_client()
    context = ""
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

    chat_messages = [{"role": "system", "content": SYSTEM_PROMPTS[normalized_language]}]
    if context:
        chat_messages.append({"role": "system", "content": context})

    for message in messages[-8:]:
        chat_messages.append({"role": message.role, "content": message.content[:4000]})

    chat_messages.append({"role": "user", "content": question[:4000]})

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=chat_messages,
        temperature=0.5,
    )
    return response.choices[0].message.content or ""
