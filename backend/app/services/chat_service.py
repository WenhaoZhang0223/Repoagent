from openai import OpenAI

from app.config import settings
from app.models import ChatMessage


SYSTEM_PROMPT = """
你是一个中文 AI 学习助手，服务对象是正在学习 GitHub 项目、准备做简历项目或面试复盘的用户。
回答要求：
- 默认用简洁中文回答，语气自然、具体、可执行。
- 如果用户问题和给定文档相关，优先基于文档回答；不要编造文档里没有的事实。
- 如果信息不足，直接说明缺什么，并给出下一步建议。
- 可以回答通用编程、简历、学习计划、项目理解和面试问题。
""".strip()


def _create_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("后端缺少 OPENAI_API_KEY。请在 backend/.env 中配置，或设置 USE_MOCK_LLM=true。")

    client_kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**client_kwargs)


def _mock_answer(question: str, document_title: str | None) -> str:
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
) -> str:
    if settings.use_mock_llm:
        return _mock_answer(question, document_title)

    client = _create_client()
    context = ""
    if document_content:
        context = (
            f"当前用户正在查看的文档标题：{document_title or '未命名文档'}\n\n"
            f"文档内容：\n{document_content[:24000]}"
        )

    chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
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
