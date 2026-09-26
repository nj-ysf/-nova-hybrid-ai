"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowUp,
  ChevronDown,
  Cpu,
  FolderClosed,
  LogOut,
  Menu,
  MessageSquare,
  PanelLeftClose,
  Plus,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  api,
  listAll,
  signOut,
  type ChatMessage,
  type ChatResponse,
  type Conversation,
  type Project,
} from "@/lib/api";

type ProcessingMode = "auto" | "local" | "external";

function conversationLabel(conversation: Conversation) {
  return conversation.title || `Chat ${conversation.id}`;
}

function relativeTime(value: string) {
  const timestamp = new Date(value).getTime();
  const minutes = Math.max(1, Math.round((Date.now() - timestamp) / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function NovaChat() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [mode, setMode] = useState<ProcessingMode>("auto");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("Loading projects…");
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const reduceMotion = useReducedMotion();

  const activeProject = projects.find((project) => String(project.id) === projectId);
  const activeConversation = conversations.find((conversation) => conversation.id === conversationId);

  useEffect(() => {
    let cancelled = false;

    async function initialize() {
      try {
        const availableProjects = await listAll<Project>("/api/projects/?limit=100");
        if (cancelled) return;
        setProjects(availableProjects);
        if (!availableProjects.length) {
          setStatus("No projects are assigned to this account.");
          return;
        }
        setProjectId(String(availableProjects[0].id));
        setStatus("Choose a conversation or start a new chat.");
      } catch (error) {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load projects.");
      }
    }

    void initialize();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;

    async function refreshConversations() {
      try {
        const items = await listAll<Conversation>(`/api/conversations/?project_id=${projectId}&limit=100`);
        if (!cancelled) setConversations(items);
      } catch (error) {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Could not load conversations.");
      }
    }

    void refreshConversations();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: reduceMotion ? "auto" : "smooth" });
  }, [messages, busy, reduceMotion]);

  async function selectConversation(selected: Conversation) {
    setBusy(true);
    setSidebarOpen(false);
    setStatus("Loading conversation…");
    try {
      const loadedMessages = await listAll<ChatMessage>(`/api/conversations/${selected.id}/messages/?limit=100`);
      setConversationId(selected.id);
      setMessages(loadedMessages);
      setStatus("Conversation loaded.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not load the conversation.");
    } finally {
      setBusy(false);
    }
  }

  function newConversation() {
    setConversationId(null);
    setMessages([]);
    setSidebarOpen(false);
    setStatus("New conversation. Project access rules apply to every request.");
    window.setTimeout(() => textareaRef.current?.focus(), 0);
  }

  function changeProject(nextProjectId: string) {
    setProjectId(nextProjectId);
    setConversationId(null);
    setMessages([]);
    setConversations([]);
    setStatus("Loading conversations…");
  }

  async function submitMessage(event?: FormEvent) {
    event?.preventDefault();
    const content = message.trim();
    if (!content || !projectId || busy) return;

    const pendingMessage: ChatMessage = { id: `pending-${Date.now()}`, role: "user", content };
    setMessages((current) => [...current, pendingMessage]);
    setMessage("");
    setBusy(true);
    setStatus("Preparing an answer…");
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    try {
      const response = await api<ChatResponse>("/api/chat/", {
        method: "POST",
        body: JSON.stringify({
          project_id: Number(projectId),
          ...(conversationId ? { conversation_id: conversationId } : {}),
          message: content,
          mode,
        }),
      });

      setConversationId(response.conversation_id);
      setMessages((current) => [
        ...current,
        { id: `assistant-${Date.now()}`, role: "assistant", content: response.reply },
      ]);
      setStatus(
        `${response.provider} · ${response.model}${response.sources.length ? ` · Sources: ${response.sources.join(", ")}` : ""}`,
      );
      const items = await listAll<Conversation>(`/api/conversations/?project_id=${projectId}&limit=100`);
      setConversations(items);
    } catch (error) {
      setMessages((current) => current.filter((item) => item.id !== pendingMessage.id));
      setMessage(content);
      setStatus(error instanceof Error ? error.message : "The message could not be sent.");
    } finally {
      setBusy(false);
      textareaRef.current?.focus();
    }
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
    }
  }

  const sidebar = (
    <div className="flex h-full flex-col p-4">
      <div className="flex h-14 items-center gap-3 px-2">
        <span className="grid size-10 shrink-0 place-items-center rounded-[14px] bg-gradient-to-br from-blue-800 via-blue-600 to-blue-300 text-white blue-glow">
          <Sparkles className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[17px] font-semibold tracking-tight text-white">Nova</p>
          <p className="text-[11px] text-zinc-500">Project assistant</p>
        </div>
        <button onClick={() => setSidebarOpen(false)} className="grid size-10 place-items-center rounded-xl text-zinc-500 outline-none transition hover:bg-white/[.05] hover:text-white focus-visible:ring-2 focus-visible:ring-blue-300/60 md:hidden" aria-label="Close navigation">
          <PanelLeftClose className="size-5" />
        </button>
      </div>

      <label htmlFor="project" className="mt-6 px-2 text-[10px] font-semibold uppercase tracking-[.14em] text-zinc-600">Project</label>
      <div className="relative mt-2">
        <FolderClosed className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-blue-300" />
        <select id="project" value={projectId} onChange={(event) => changeProject(event.target.value)} disabled={busy || !projects.length} className="h-12 w-full appearance-none rounded-[14px] border border-white/[.07] bg-[#111216] pl-10 pr-9 text-xs font-semibold text-slate-200 outline-none transition focus:border-blue-300/50 focus:ring-4 focus:ring-blue-500/[.08] disabled:opacity-50">
          {!projects.length && <option value="">No projects</option>}
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-zinc-600" />
      </div>

      <button onClick={newConversation} disabled={!projectId || busy} className="mt-4 flex h-11 items-center justify-center gap-2 rounded-[14px] bg-blue-600 text-sm font-semibold text-white shadow-[0_0_30px_rgba(37,99,235,.15)] outline-none transition hover:bg-blue-500 focus-visible:ring-2 focus-visible:ring-blue-300/70 disabled:opacity-40">
        <Plus className="size-[18px]" /> New chat
      </button>

      <div className="mt-7 min-h-0 flex-1 overflow-y-auto">
        <p className="px-2 text-[10px] font-semibold uppercase tracking-[.14em] text-zinc-600">Conversations</p>
        <div className="mt-3 space-y-1">
          {conversations.map((conversation) => {
            const active = conversation.id === conversationId;
            return (
              <button key={conversation.id} onClick={() => void selectConversation(conversation)} disabled={busy} className={`flex w-full items-center gap-3 rounded-[14px] px-3 py-3 text-left outline-none transition focus-visible:ring-2 focus-visible:ring-blue-300/60 ${active ? "bg-blue-600/10 text-blue-200" : "text-zinc-500 hover:bg-white/[.04] hover:text-slate-200"}`}>
                <MessageSquare className="size-[17px] shrink-0" />
                <span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium">{conversationLabel(conversation)}</span><span className="mt-0.5 block text-[10px] text-zinc-600">{relativeTime(conversation.updated_at)}</span></span>
              </button>
            );
          })}
          {!!projectId && !conversations.length && <p className="px-3 py-4 text-xs leading-5 text-zinc-600">No conversations yet.</p>}
        </div>
      </div>
    </div>
  );

  return (
    <main className="flex h-dvh min-h-[560px] overflow-hidden bg-[#050505]">
      <aside className="hidden w-[260px] shrink-0 border-r border-white/[.07] bg-[#080808] md:block xl:w-[280px]">{sidebar}</aside>

      <AnimatePresence>
        {sidebarOpen && (
          <>
            <motion.button initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setSidebarOpen(false)} className="fixed inset-0 z-40 bg-black/75 backdrop-blur-sm md:hidden" aria-label="Close navigation overlay" />
            <motion.aside initial={reduceMotion ? false : { x: -320 }} animate={{ x: 0 }} exit={{ x: -320 }} transition={{ duration: 0.2, ease: "easeOut" }} className="fixed inset-y-0 left-0 z-50 w-[min(88vw,320px)] border-r border-white/[.07] bg-[#080808] md:hidden">{sidebar}</motion.aside>
          </>
        )}
      </AnimatePresence>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[72px] shrink-0 items-center gap-3 border-b border-white/[.07] px-4 sm:px-6">
          <button onClick={() => setSidebarOpen(true)} className="grid size-10 shrink-0 place-items-center rounded-xl border border-white/[.07] text-zinc-500 outline-none transition hover:bg-white/[.05] hover:text-white focus-visible:ring-2 focus-visible:ring-blue-300/60 md:hidden" aria-label="Open navigation"><Menu className="size-5" /></button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-sm font-semibold text-white">{activeConversation ? conversationLabel(activeConversation) : "New conversation"}</h1>
            <p className="mt-0.5 flex items-center gap-1.5 truncate text-[10px] text-zinc-500"><span className="size-1.5 shrink-0 rounded-full bg-emerald-400" />{activeProject?.name ?? "Select a project"}</p>
          </div>
          <button onClick={() => void signOut()} className="grid size-10 place-items-center rounded-xl border border-white/[.07] text-zinc-500 outline-none transition hover:bg-white/[.05] hover:text-white focus-visible:ring-2 focus-visible:ring-blue-300/60 sm:flex sm:w-auto sm:px-3" aria-label="Sign out"><LogOut className="size-4" /><span className="ml-2 hidden text-xs font-medium sm:inline">Sign out</span></button>
        </header>

        <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-7 sm:px-7 lg:py-10">
          <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col">
            {!messages.length ? (
              <div className="m-auto flex max-w-md flex-col items-center px-4 py-10 text-center">
                <div className="relative grid size-20 place-items-center rounded-full border border-blue-300/15 bg-blue-600/[.06] blue-glow">
                  <div className="absolute size-10 rounded-[42%_58%_55%_45%] bg-gradient-to-br from-blue-300 via-blue-600 to-blue-950 opacity-80" />
                  <Sparkles className="relative size-5 text-blue-100" />
                </div>
                <h2 className="mt-6 text-2xl font-semibold tracking-tight text-white">Ask about your project</h2>
                <p className="mt-3 text-sm leading-6 text-zinc-500">Nova answers with the project sources and permissions available to you.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-7 pb-4">
                <div className="text-center"><span className="inline-flex rounded-full border border-white/[.07] bg-[#0d0d0f] px-3 py-1.5 text-[10px] text-zinc-600">Project access rules apply to every answer</span></div>
                <AnimatePresence initial={false}>
                  {messages.map((item) => {
                    const user = item.role === "user";
                    return (
                      <motion.article key={item.id} initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex items-start gap-3 ${user ? "justify-end" : ""}`}>
                        {!user && <span className="mt-1 grid size-9 shrink-0 place-items-center rounded-xl bg-blue-600/10 text-blue-300"><Sparkles className="size-4" /></span>}
                        <div className={`max-w-2xl whitespace-pre-wrap px-5 py-4 text-sm leading-6 ${user ? "rounded-[20px_7px_20px_20px] bg-gradient-to-br from-blue-800 via-blue-600 to-blue-500 text-white shadow-[0_0_30px_rgba(37,99,235,.12)]" : "rounded-[7px_20px_20px_20px] border border-white/[.07] bg-[#111216] text-slate-300"}`}>{item.content}</div>
                        {user && <span className="mt-1 grid size-9 shrink-0 place-items-center rounded-xl bg-blue-600/15 text-[10px] font-semibold text-blue-200">You</span>}
                      </motion.article>
                    );
                  })}
                </AnimatePresence>
                {busy && messages.length > 0 && <div className="flex items-start gap-3"><span className="mt-1 grid size-9 place-items-center rounded-xl bg-blue-600/10 text-blue-300"><Sparkles className="size-4" /></span><div className="flex h-12 items-center gap-1 rounded-[7px_20px_20px_20px] border border-white/[.07] bg-[#111216] px-5">{[0, 1, 2].map((dot) => <span key={dot} className="size-1.5 animate-bounce rounded-full bg-blue-300/70" style={{ animationDelay: `${dot * 100}ms` }} />)}</div></div>}
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 border-t border-white/[.07] bg-[#050505]/95 px-3 pb-[max(12px,env(safe-area-inset-bottom))] pt-3 backdrop-blur-xl sm:px-6 sm:pb-4 sm:pt-4">
          <form onSubmit={submitMessage} className="mx-auto max-w-3xl rounded-[22px] border border-white/[.08] bg-[#111216] p-2 transition focus-within:border-blue-300/45 focus-within:ring-4 focus-within:ring-blue-500/[.08]">
            <textarea ref={textareaRef} value={message} onChange={(event) => { setMessage(event.target.value); event.currentTarget.style.height = "auto"; event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 144)}px`; }} onKeyDown={onComposerKeyDown} rows={1} maxLength={12000} placeholder="Ask about your project…" disabled={!projectId || busy} className="max-h-36 min-h-11 w-full resize-none bg-transparent px-3 py-3 text-sm leading-5 text-slate-100 outline-none placeholder:text-zinc-600 disabled:opacity-50" />
            <div className="flex items-center gap-2 px-1 pb-1">
              <label className="flex h-9 shrink-0 items-center gap-2 rounded-xl border border-white/[.07] bg-[#0d0d0f] pl-2.5 pr-1 text-[10px] font-medium text-zinc-500 transition focus-within:border-blue-300/45">
                <Cpu className="size-3.5 text-blue-300" aria-hidden="true" />
                <span className="hidden sm:inline">Model</span>
                <select value={mode} onChange={(event) => setMode(event.target.value as ProcessingMode)} disabled={busy} aria-label="Choose model routing" className="bg-transparent py-1.5 pr-1 text-[11px] font-semibold text-slate-300 outline-none disabled:opacity-50">
                  <option value="auto">Auto</option>
                  <option value="local">Local model</option>
                </select>
              </label>
              <p className="hidden min-w-0 flex-1 truncate text-[10px] text-zinc-600 sm:block">{status}</p>
              <button type="submit" disabled={!message.trim() || !projectId || busy} className="ml-auto grid size-11 shrink-0 place-items-center rounded-[14px] bg-blue-600 text-white shadow-[0_0_30px_rgba(37,99,235,.2)] outline-none transition hover:bg-blue-500 focus-visible:ring-2 focus-visible:ring-blue-300/70 disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-600 disabled:shadow-none" aria-label="Send message">{busy ? <span className="size-4 animate-spin rounded-full border-2 border-white/20 border-t-white" /> : <ArrowUp className="size-5" />}</button>
            </div>
          </form>
          <p className="mt-2 truncate text-center text-[10px] text-zinc-700 sm:hidden">{status}</p>
        </div>
      </section>
    </main>
  );
}
