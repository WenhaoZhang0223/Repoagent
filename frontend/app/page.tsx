"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type JobStatus = "queued" | "cloning" | "analyzing" | "generating" | "completed" | "failed";

type DocumentPayload = {
  name: "learning_guide" | "daily_plan" | "interview_questions" | "agent_trace";
  title: string;
  filename: string;
  content: string;
  download_url: string;
};

type JobResponse = {
  job_id: string;
  repo_url: string;
  status: JobStatus;
  message: string;
  error?: string | null;
  documents: DocumentPayload[];
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const statusLabels: Record<JobStatus, string> = {
  queued: "排队中",
  cloning: "读取仓库",
  analyzing: "理解代码",
  generating: "生成内容",
  completed: "完成",
  failed: "失败"
};

const statusOrder: JobStatus[] = ["queued", "cloning", "analyzing", "generating", "completed"];
const starterPrompts = ["帮我总结这个项目亮点", "根据文档写简历描述", "问我 5 个面试问题"];

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("");
  const [goal, setGoal] = useState("帮我快速理解这个项目，并准备简历和面试复盘。");
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<JobResponse | null>(null);
  const [activeDoc, setActiveDoc] = useState<DocumentPayload["name"]>("learning_guide");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "把仓库文档生成后，你可以问我项目逻辑、简历写法、学习路线或面试问题。"
    }
  ]);
  const [chatError, setChatError] = useState("");
  const [isChatting, setIsChatting] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const activeDocument = useMemo(
    () => job?.documents.find((doc) => doc.name === activeDoc) || job?.documents[0],
    [activeDoc, job]
  );

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatMessages, isChatting]);

  useEffect(() => {
    if (!jobId) return;

    async function pollStatus() {
      const response = await fetch(`${API_BASE}/api/status/${jobId}`);
      if (!response.ok) return;

      const data = (await response.json()) as JobResponse;
      setJob(data);

      if (data.documents[0] && !data.documents.some((doc) => doc.name === activeDoc)) {
        setActiveDoc(data.documents[0].name);
      }
    }

    void pollStatus();
    const timer = window.setInterval(() => {
      void pollStatus();
    }, 1400);

    return () => window.clearInterval(timer);
  }, [activeDoc, jobId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setJob(null);
    setJobId("");
    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl, goal })
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || "提交失败，请稍后再试。");
      }

      setJobId(payload.job_id);
      setJob({
        job_id: payload.job_id,
        repo_url: repoUrl,
        status: payload.status,
        message: "任务已提交。",
        documents: []
      });
      setChatMessages([
        {
          role: "assistant",
          content: "我已经开始分析这个仓库。文档生成后，我会结合当前文档回答你的问题。"
        }
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "提交失败，请稍后再试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function sendChat(questionOverride?: string) {
    const question = (questionOverride || chatInput).trim();
    if (!question || isChatting) return;

    const history = chatMessages.filter((message) => message.content.trim());
    setChatMessages((current) => [...current, { role: "user", content: question }]);
    setChatInput("");
    setChatError("");
    setIsChatting(true);

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          messages: history,
          document_title: activeDocument?.title,
          document_content: activeDocument?.content
        })
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || "AI 暂时没有回复。");
      }

      setChatMessages((current) => [...current, { role: "assistant", content: payload.answer }]);
    } catch (caught) {
      setChatError(caught instanceof Error ? caught.message : "AI 暂时没有回复。");
    } finally {
      setIsChatting(false);
    }
  }

  const hasDocuments = Boolean(job?.documents.length);

  return (
    <main className="shell">
      <section className="hero">
        <div className="heroCopy">
          <p className="eyebrow">Repo Learning Studio</p>
          <h1>把 GitHub 项目整理成适合收藏、复习和面试的学习笔记。</h1>
          <p className="subhead">输入仓库地址，生成学习指南、每日计划和面试题，再让 AI 陪你追问文档细节。</p>
        </div>
        <div className="heroStats" aria-label="生成内容类型">
          <span>学习指南</span>
          <span>每日计划</span>
          <span>面试题库</span>
        </div>
      </section>

      <section className="workspace">
        <div className="leftColumn">
          <form className="generator" onSubmit={handleSubmit}>
            <div className="sectionTitle">
              <p className="eyebrow">Create</p>
              <h2>生成项目笔记</h2>
            </div>
            <label htmlFor="repo-url">GitHub 仓库地址</label>
            <div className="inputRow">
              <input
                id="repo-url"
                value={repoUrl}
                onChange={(event) => setRepoUrl(event.target.value)}
                placeholder="https://github.com/owner/repo"
                required
              />
              <button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "提交中" : "开始生成"}
              </button>
            </div>
            <label htmlFor="analysis-goal" className="goalLabel">
              分析目标
            </label>
            <textarea
              id="analysis-goal"
              className="goalInput"
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              placeholder="例如：帮我看懂架构，准备面试追问，或者找出适合写进简历的亮点。"
              rows={3}
            />
            {error && <p className="error">{error}</p>}
          </form>

          <div className="statusPanel" aria-label="生成进度">
            {statusOrder.map((status) => {
              const currentIndex = job ? statusOrder.indexOf(job.status) : -1;
              const itemIndex = statusOrder.indexOf(status);
              const isDone = job?.status === "completed" || (currentIndex > itemIndex && job?.status !== "failed");
              const isActive = job?.status === status;

              return (
                <div className={`step ${isDone ? "done" : ""} ${isActive ? "active" : ""}`} key={status}>
                  <span />
                  <p>{statusLabels[status]}</p>
                </div>
              );
            })}
          </div>

          <section className="resultArea">
            <div className="jobInfo">
              <div>
                <p className="muted">当前状态</p>
                <h2>{job ? statusLabels[job.status] : "等待提交"}</h2>
              </div>
              <p>{job ? job.error || job.message : "粘贴一个公开 GitHub 仓库地址，生成适合复习和分享的 Markdown 文档。"}</p>
            </div>

            {hasDocuments ? (
              <div className="docsLayout">
                <nav className="docTabs" aria-label="文档">
                  {job?.documents.map((doc) => (
                    <button
                      className={activeDocument?.name === doc.name ? "selected" : ""}
                      key={doc.name}
                      onClick={() => setActiveDoc(doc.name)}
                      type="button"
                    >
                      {doc.title}
                    </button>
                  ))}
                </nav>

                {activeDocument && (
                  <article className="docViewer">
                    <header>
                      <div>
                        <p className="muted">Markdown Preview</p>
                        <h2>{activeDocument.title}</h2>
                      </div>
                      <a href={`${API_BASE}${activeDocument.download_url}`}>下载</a>
                    </header>
                    <pre>{activeDocument.content}</pre>
                  </article>
                )}
              </div>
            ) : (
              <div className="emptyState">
                <strong>生成后会显示三份文档</strong>
                <p>左侧切换文档，右侧聊天框可以基于当前生成的文档继续追问。</p>
              </div>
            )}
          </section>
        </div>

        <aside className="chatPanel" aria-label="AI 聊天">
          <div className="chatHeader">
            <div>
              <p className="eyebrow">Ask AI</p>
              <h2>文档问答助手</h2>
            </div>
            <span>{activeDocument ? "已连接到生成的文档" : "通用问答"}</span>
          </div>

          <div className="promptChips">
            {starterPrompts.map((prompt) => (
              <button key={prompt} type="button" onClick={() => void sendChat(prompt)}>
                {prompt}
              </button>
            ))}
          </div>

          <div className="chatMessages">
            {chatMessages.map((message, index) => (
              <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
                <p>{message.content}</p>
              </div>
            ))}
            {isChatting && (
              <div className="message assistant pending">
                <p>正在思考...</p>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {chatError && <p className="error chatError">{chatError}</p>}

          <form
            className="chatInput"
            onSubmit={(event) => {
              event.preventDefault();
              void sendChat();
            }}
          >
            <textarea
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="问任何问题，也可以问当前文档..."
              rows={3}
            />
            <button type="submit" disabled={isChatting || !chatInput.trim()}>
              发送
            </button>
          </form>
        </aside>
      </section>
    </main>
  );
}
