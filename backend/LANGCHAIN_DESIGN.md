# LangChain Design

当前版本使用 LangChain 负责模型编排，FastAPI 负责 Web API、任务状态和文件下载。

## 调用链路

```text
POST /api/generate
-> main.py 后台任务
-> repo_service.py clone 和扫描仓库
-> analyzer_service.py 生成项目摘要
-> langchain_service.py 使用 LangChain 生成 Markdown
-> doc_service.py 保存文档
```

## LangChain 所在位置

核心文件：

```text
backend/app/services/repo_rag_agent_service.py
```

里面使用：

- `ChatPromptTemplate`：管理 system/user prompt
- `ChatOpenAI`：调用 OpenAI 或 OpenAI-compatible 模型，例如 DeepSeek
- `StrOutputParser`：把模型响应转成字符串 Markdown
- LCEL 管道：`prompt | llm | parser`

## 模型配置

模型仍然通过 `backend/.env` 配置：

```env
OPENAI_API_KEY=你的 API Key
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com/v1
USE_MOCK_LLM=false
```

`OPENAI_BASE_URL` 为空时使用官方 OpenAI；填写 DeepSeek、硅基流动等兼容 OpenAI SDK 的 `/v1` 地址时，会调用对应平台。

## 为什么现在用 Chain，不直接用 Agent

当前 MVP 的任务是固定流程：读取仓库、分析摘要、生成三份文档。这个流程不需要模型自主选择工具，所以用 LangChain Chain 更稳定。

后续可以升级为：

```text
Repo Analyzer Tool
-> Learning Guide Agent
-> Daily Plan Agent
-> Interview Agent
-> Reviewer Agent
```

如果要做多 agent 编排，建议下一步引入 LangGraph。
