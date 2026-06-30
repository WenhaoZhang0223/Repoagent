"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type JobStatus = "queued" | "cloning" | "analyzing" | "generating" | "completed" | "failed";
type Language = "zh" | "en";

type DocumentPayload = {
  name: "learning_guide" | "daily_plan" | "interview_questions";
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
  agent_trace?: string | null;
  agent_events: string[];
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const copy = {
  zh: {
    languageName: "中文",
    switchLanguage: "切换到英文",
    statusLabels: {
      queued: "排队中",
      cloning: "读取仓库",
      analyzing: "理解代码",
      generating: "生成内容",
      completed: "完成",
      failed: "失败"
    },
    starterPrompts: ["帮我总结这个项目亮点", "根据文档写简历描述", "问我 5 个面试问题"],
    defaultGoal: "帮我快速理解这个项目，并准备简历和面试复盘。",
    initialAssistant: "把仓库文档生成后，你可以问我项目逻辑、简历写法、学习路线或面试问题。",
    submittedAssistant: "我已经开始分析这个仓库。文档生成后，我会结合当前文档回答你的问题。",
    heroTitle: "把 GitHub 项目整理成适合收藏、复习和面试的学习笔记。",
    heroSubhead: "输入仓库地址，生成学习指南、每日计划和面试题，再让 AI 陪你追问文档细节。",
    stats: ["学习指南", "每日计划", "面试题库"],
    create: "Create",
    generateTitle: "生成项目笔记",
    repoLabel: "GitHub 仓库地址",
    start: "开始生成",
    submitting: "提交中",
    goalLabel: "分析目标",
    goalPlaceholder: "例如：帮我看懂架构，准备面试追问，或者找出适合写进简历的亮点。",
    submitError: "提交失败，请稍后再试。",
    chatError: "AI 暂时没有回复。",
    progressLabel: "生成进度",
    currentStatus: "当前状态",
    waiting: "等待提交",
    waitingText: "粘贴一个公开 GitHub 仓库地址，生成适合复习和分享的 Markdown 文档。",
    docsLabel: "文档",
    preview: "Markdown Preview",
    download: "下载",
    emptyTitle: "生成后会显示三份文档",
    emptyText: "左侧切换文档，右侧聊天框可以基于当前生成的文档继续追问。",
    chatLabel: "AI 聊天",
    askAI: "Ask AI",
    chatTitle: "文档问答助手",
    connected: "已连接到生成的文档",
    general: "通用问答",
    thinking: "正在思考...",
    chatPlaceholder: "问任何问题，也可以问当前文档...",
    send: "发送",
    taskSubmitted: "任务已提交。",
    agentActivityTitle: "任务进行中",
    agentActivitySubtitle: "",
    agentActivityEmpty: "等待 Agent 开始执行..."
  },
  en: {
    languageName: "English",
    switchLanguage: "Switch to Chinese",
    statusLabels: {
      queued: "Queued",
      cloning: "Reading repo",
      analyzing: "Understanding code",
      generating: "Generating",
      completed: "Done",
      failed: "Failed"
    },
    starterPrompts: ["Summarize this project's strengths", "Turn the docs into resume bullets", "Ask me 5 interview questions"],
    defaultGoal: "Help me understand this project quickly and prepare for resume and interview review.",
    initialAssistant: "After the repository documents are generated, you can ask me about project logic, resume wording, study plans, or interview questions.",
    submittedAssistant: "I have started analyzing this repository. Once the documents are ready, I will answer using the current document as context.",
    heroTitle: "Turn GitHub projects into study notes for review, resumes, and interviews.",
    heroSubhead: "Paste a repository URL, generate a learning guide, daily plan, and interview questions, then keep asking AI about the details.",
    stats: ["Learning guide", "Daily plan", "Interview bank"],
    create: "Create",
    generateTitle: "Generate project notes",
    repoLabel: "GitHub repository URL",
    start: "Start",
    submitting: "Submitting",
    goalLabel: "Analysis goal",
    goalPlaceholder: "For example: help me understand the architecture, prepare interview follow-ups, or find resume-worthy highlights.",
    submitError: "Submission failed. Please try again later.",
    chatError: "AI is not responding right now.",
    progressLabel: "Generation progress",
    currentStatus: "Current status",
    waiting: "Waiting",
    waitingText: "Paste a public GitHub repository URL to generate Markdown documents for review and sharing.",
    docsLabel: "Documents",
    preview: "Markdown Preview",
    download: "Download",
    emptyTitle: "Generated documents will appear here",
    emptyText: "Switch documents on the left, then ask follow-up questions in the chat panel using the current document.",
    chatLabel: "AI chat",
    askAI: "Ask AI",
    chatTitle: "Document Q&A assistant",
    connected: "Connected to generated docs",
    general: "General Q&A",
    thinking: "Thinking...",
    chatPlaceholder: "Ask anything, including questions about the current document...",
    send: "Send",
    taskSubmitted: "Task submitted.",
    agentActivityTitle: "Task In Progress",
    agentActivitySubtitle: "",
    agentActivityEmpty: "Waiting for the agent to start..."
  }
} satisfies Record<
  Language,
  {
    languageName: string;
    switchLanguage: string;
    statusLabels: Record<JobStatus, string>;
    starterPrompts: string[];
    defaultGoal: string;
    initialAssistant: string;
    submittedAssistant: string;
    heroTitle: string;
    heroSubhead: string;
    stats: string[];
    create: string;
    generateTitle: string;
    repoLabel: string;
    start: string;
    submitting: string;
    goalLabel: string;
    goalPlaceholder: string;
    submitError: string;
    chatError: string;
    progressLabel: string;
    currentStatus: string;
    waiting: string;
    waitingText: string;
    docsLabel: string;
    preview: string;
    download: string;
    emptyTitle: string;
    emptyText: string;
    chatLabel: string;
    askAI: string;
    chatTitle: string;
    connected: string;
    general: string;
    thinking: string;
    chatPlaceholder: string;
    send: string;
    taskSubmitted: string;
    agentActivityTitle: string;
    agentActivitySubtitle: string;
    agentActivityEmpty: string;
  }
>;

const statusOrder: JobStatus[] = ["queued", "cloning", "analyzing", "generating", "completed"];

export default function Home() {
  const [language, setLanguage] = useState<Language>("zh");
  const t = copy[language];
  const [repoUrl, setRepoUrl] = useState("");
  const [goal, setGoal] = useState(copy.zh.defaultGoal);
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<JobResponse | null>(null);
  const [activeDoc, setActiveDoc] = useState<DocumentPayload["name"]>("learning_guide");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: copy.zh.initialAssistant
    }
  ]);
  const [chatError, setChatError] = useState("");
  const [isChatting, setIsChatting] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const agentEventEndRef = useRef<HTMLDivElement | null>(null);

  const activeDocument = useMemo(
    () => job?.documents.find((doc) => doc.name === activeDoc) || job?.documents[0],
    [activeDoc, job]
  );

  useEffect(() => {
    setGoal((current) => {
      if (current === copy.zh.defaultGoal || current === copy.en.defaultGoal) {
        return copy[language].defaultGoal;
      }
      return current;
    });

    setChatMessages((current) => {
      const isOnlyIntro =
        current.length === 1 &&
        current[0].role === "assistant" &&
        (current[0].content === copy.zh.initialAssistant || current[0].content === copy.en.initialAssistant);

      return isOnlyIntro ? [{ role: "assistant", content: copy[language].initialAssistant }] : current;
    });
  }, [language]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatMessages, isChatting]);

  useEffect(() => {
    agentEventEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [job?.agent_events.length]);

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
        body: JSON.stringify({ repo_url: repoUrl, goal, language })
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || t.submitError);
      }

      setJobId(payload.job_id);
      setJob({
        job_id: payload.job_id,
        repo_url: repoUrl,
        status: payload.status,
        message: t.taskSubmitted,
        documents: [],
        agent_trace: null,
        agent_events: []
      });
      setChatMessages([
        {
          role: "assistant",
          content: t.submittedAssistant
        }
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t.submitError);
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
          document_content: activeDocument?.content,
          language
        })
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || t.chatError);
      }

      setChatMessages((current) => [...current, { role: "assistant", content: payload.answer }]);
    } catch (caught) {
      setChatError(caught instanceof Error ? caught.message : t.chatError);
    } finally {
      setIsChatting(false);
    }
  }

  const hasDocuments = Boolean(job?.documents.length);
  const showAgentActivity = Boolean(job && job.status !== "completed" && job.status !== "failed");

  return (
    <main className="shell" lang={language}>
      <section className="hero">
        <div className="heroCopy">
          <p className="eyebrow">Repo Learning Studio</p>
          <h1>{t.heroTitle}</h1>
          <p className="subhead">{t.heroSubhead}</p>
        </div>
        <div className="heroAside">
          <button
            className="languageToggle"
            type="button"
            aria-label={t.switchLanguage}
            title={t.switchLanguage}
            onClick={() => setLanguage((current) => (current === "zh" ? "en" : "zh"))}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="9" />
              <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
            </svg>
            <span>{language === "zh" ? "EN" : "中"}</span>
          </button>
          <div className="heroStats" aria-label={t.docsLabel}>
            {t.stats.map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="workspace">
        <div className="leftColumn">
          <form className="generator" onSubmit={handleSubmit}>
            <div className="sectionTitle">
              <p className="eyebrow">{t.create}</p>
              <h2>{t.generateTitle}</h2>
            </div>
            <label htmlFor="repo-url">{t.repoLabel}</label>
            <div className="inputRow">
              <input
                id="repo-url"
                value={repoUrl}
                onChange={(event) => setRepoUrl(event.target.value)}
                placeholder="https://github.com/owner/repo"
                required
              />
              <button type="submit" disabled={isSubmitting}>
                {isSubmitting ? t.submitting : t.start}
              </button>
            </div>
            <label htmlFor="analysis-goal" className="goalLabel">
              {t.goalLabel}
            </label>
            <textarea
              id="analysis-goal"
              className="goalInput"
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              placeholder={t.goalPlaceholder}
              rows={3}
            />
            {error && <p className="error">{error}</p>}
          </form>

          <div className="statusPanel" aria-label={t.progressLabel}>
            {statusOrder.map((status) => {
              const currentIndex = job ? statusOrder.indexOf(job.status) : -1;
              const itemIndex = statusOrder.indexOf(status);
              const isDone = job?.status === "completed" || (currentIndex > itemIndex && job?.status !== "failed");
              const isActive = job?.status === status;

              return (
                <div className={`step ${isDone ? "done" : ""} ${isActive ? "active" : ""}`} key={status}>
                  <span />
                  <p>{t.statusLabels[status]}</p>
                </div>
              );
            })}
          </div>

          <section className="resultArea">
            <div className="jobInfo">
              <div>
                <p className="muted">{t.currentStatus}</p>
                <h2>{job ? t.statusLabels[job.status] : t.waiting}</h2>
              </div>
              <p>{job ? job.error || job.message : t.waitingText}</p>
            </div>

            {showAgentActivity && (
              <section className="agentActivity" aria-label={t.agentActivityTitle}>
                <header>
                  <h2>{t.agentActivityTitle}</h2>
                </header>
                <div className="agentEventList">
                  {job?.agent_events.length ? (
                    job.agent_events.map((event, index) => (
                      <p key={`${event}-${index}`}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        {event}
                      </p>
                    ))
                  ) : (
                    <p className="agentTraceEmpty">{t.agentActivityEmpty}</p>
                  )}
                  <div ref={agentEventEndRef} />
                </div>
              </section>
            )}

            {hasDocuments ? (
              <div className="docsLayout">
                <nav className="docTabs" aria-label={t.docsLabel}>
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
                        <p className="muted">{t.preview}</p>
                        <h2>{activeDocument.title}</h2>
                      </div>
                      <a href={`${API_BASE}${activeDocument.download_url}`}>{t.download}</a>
                    </header>
                    <pre>{activeDocument.content}</pre>
                  </article>
                )}
              </div>
            ) : (
              <div className="emptyState">
                <strong>{t.emptyTitle}</strong>
                <p>{t.emptyText}</p>
              </div>
            )}
          </section>
        </div>

        <aside className="chatPanel" aria-label={t.chatLabel}>
          <div className="chatHeader">
            <div>
              <p className="eyebrow">{t.askAI}</p>
              <h2>{t.chatTitle}</h2>
            </div>
            <span>{activeDocument ? t.connected : t.general}</span>
          </div>

          <div className="promptChips">
            {t.starterPrompts.map((prompt) => (
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
                <p>{t.thinking}</p>
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
              placeholder={t.chatPlaceholder}
              rows={3}
            />
            <button type="submit" disabled={isChatting || !chatInput.trim()}>
              {t.send}
            </button>
          </form>
        </aside>
      </section>
    </main>
  );
}
