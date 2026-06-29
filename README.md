# Repo Learning Agent

## 模型 API 配置

模型 API 不在前端改，也不在页面代码里改。第一版统一放在 `backend/.env`：

```env
OPENAI_API_KEY=你的模型 API Key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=
USE_MOCK_LLM=false
```

`OPENAI_BASE_URL` 为空时使用官方 OpenAI API；如果你用的是兼容 OpenAI SDK 的第三方接口，就填它的 `/v1` 地址。

可以用脚本切换模型：

```powershell
python scripts\switch_model.py --model gpt-4o-mini --api-key sk-your-key --base-url ""
```

切换到 OpenAI-compatible API：

```powershell
python scripts\switch_model.py --model your-model-name --api-key your-key --base-url https://your-api-host/v1
```

只想演示流程、不调用真实模型：

```powershell
python scripts\switch_model.py --model mock --mock true
```

一个用于学习 GitHub 项目的 MVP：前端输入公开 GitHub repo 地址，后端 clone、扫描并调用 OpenAI API 生成学习文档。

## 项目结构

```text
Repoagent/
  frontend/        Next.js / React 页面
  backend/         FastAPI 服务
  generated_docs/ 生成的 Markdown 文档
```

## 后端启动

```powershell
conda activate repoagent
cd backend
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

如果只是展示流程，可以在 `.env` 里设置：

```env
USE_MOCK_LLM=true
```

## 前端启动

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://localhost:3000`，粘贴 GitHub repo URL 后生成文档。

## API

- `POST /api/generate`：提交 repo URL，返回 `job_id`
- `GET /api/status/{job_id}`：查询任务状态和文档内容
- `GET /api/docs/{job_id}/{doc_type}/download`：下载 Markdown 文档
