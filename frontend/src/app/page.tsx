"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Header } from "../components/layout/Header";
import { useUser } from "../lib/userContext";
import {
  Conversation,
  ConversationMessage,
  ConversationSummary,
  ConversationalResponse,
  WatchSummary,
} from "../types";
import { api } from "../lib/api";
import {
  AlertCircle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  Globe,
  HelpCircle,
  Loader2,
  MessageSquare,
  Plus,
  Radar,
  Send,
  Sparkles,
  Trash2,
  TrendingDown,
  User as UserIcon,
  Zap,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const { user, userId, isAuthenticated, loading: userLoading } = useUser();

  // State
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [inputMessage, setInputMessage] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [activeWatchesCount, setActiveWatchesCount] = useState<number>(0);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSubmitting]);

  // Protect route
  useEffect(() => {
    if (!userLoading && !isAuthenticated) {
      router.replace("/sign-in");
    }
  }, [isAuthenticated, userLoading, router]);

  // Load conversations list and active watches count
  const loadConversations = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const [convs, watches] = await Promise.all([
        api.getConversations().catch(() => []),
        api.getWatches(userId || undefined).catch(() => []),
      ]);
      setConversations(convs);
      setActiveWatchesCount(Array.isArray(watches) ? watches.length : 0);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    }
  }, [isAuthenticated, userId]);

  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
    }
  }, [isAuthenticated, loadConversations]);

  // Load specific conversation messages
  const selectConversation = async (convId: string) => {
    setActiveConversationId(convId);
    setLoadingHistory(true);
    try {
      const conv = await api.getConversation(convId);
      setMessages(conv.messages || []);
    } catch (err) {
      console.error("Failed to load conversation messages:", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  // Start a new task
  const handleNewTask = () => {
    setActiveConversationId(null);
    setMessages([]);
    setInputMessage("");
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  // Delete conversation
  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        handleNewTask();
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  };

  // Send message
  const handleSendPrompt = async (
    customMsg?: string,
    selectedOption?: string
  ) => {
    const textToSend = customMsg || inputMessage;
    if (!textToSend.trim() || isSubmitting) return;

    const userMsg: ConversationMessage = {
      id: `temp-${Date.now()}`,
      conversation_id: activeConversationId || "temp",
      role: "user",
      content: textToSend,
      message_type: "user",
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!customMsg) setInputMessage("");
    setIsSubmitting(true);

    try {
      const response: ConversationalResponse = await api.sendConversationalPrompt({
        message: textToSend,
        conversation_id: activeConversationId || undefined,
        selected_option: selectedOption,
      });

      if (!activeConversationId) {
        setActiveConversationId(response.conversation_id);
      }

      const asstMsg: ConversationMessage = {
        id: response.message_id,
        conversation_id: response.conversation_id,
        role: "assistant",
        content: response.content,
        message_type: response.message_type as any,
        metadata: {
          mode: response.mode,
          sources: response.sources,
          watch_id: response.watch?.id || null,
          watch_title: response.watch?.title || null,
          clarification_options: response.clarification_options,
          ...response.metadata,
        },
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, asstMsg]);
      loadConversations();
    } catch (err: any) {
      console.error("Conversational error:", err);
      const errMsg: ConversationMessage = {
        id: `err-${Date.now()}`,
        conversation_id: activeConversationId || "temp",
        role: "assistant",
        content: `Sorry, I encountered an issue processing your request: ${err.message || "Unknown error"}`,
        message_type: "error",
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendPrompt();
    }
  };

  const quickPrompts = [
    {
      title: "Find Admissions Contact",
      desc: "Istanbul University international office email & phone",
      mode: "ASK",
      prompt: "Find Istanbul University's official contact information.",
      icon: "🎓",
    },
    {
      title: "Watch Job Openings",
      desc: "Bahçeşehir University academic & staff vacancies",
      mode: "WATCH",
      prompt: "Watch Bahçeşehir University for new jobs.",
      icon: "💼",
    },
    {
      title: "Scholarship & Openings",
      desc: "Check Istanbul University scholarship and alert when open",
      mode: "ASK & WATCH",
      prompt: "Check Istanbul University's bachelor's scholarship information and tell me when applications open.",
      icon: "📚",
    },
    {
      title: "Daraz Price Drop",
      desc: "Find ergonomic chair under 10k and alert at 8k",
      mode: "SHOPPING",
      prompt: "Find an office chair on Daraz under PKR 10,000 and alert me if it reaches PKR 8,000.",
      icon: "🛒",
    },
  ];

  if (userLoading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <Radar className="w-8 h-8 text-radar-cyan animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Restoring Web Radar session...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-4rem)] overflow-hidden">
      <Header
        title="Conversational Command Center"
        subtitle="Natural-language web discovery, real-time answering & persistent autonomous monitoring"
        onRefresh={() => loadConversations()}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar: Recent Tasks */}
        <aside
          className={`w-80 border-r border-slate-800 bg-slate-900/60 backdrop-blur-md flex flex-col transition-all duration-200 ${
            sidebarOpen ? "block" : "hidden md:flex"
          }`}
        >
          {/* New Task Button */}
          <div className="p-4 border-b border-slate-800/80">
            <button
              onClick={handleNewTask}
              className="w-full flex items-center justify-center gap-2.5 px-4 py-2.5 rounded-xl bg-radar-cyan/15 border border-radar-cyan/30 text-radar-cyan font-medium text-sm hover:bg-radar-cyan/25 transition-all shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>New Task</span>
            </button>
          </div>

          {/* Quick Stats / Navigation */}
          <div className="px-4 py-3 border-b border-slate-800/60 flex items-center justify-between text-xs text-slate-400">
            <span className="font-mono uppercase tracking-wider text-[11px] text-slate-400">Tasks & Chats</span>
            <button
              onClick={() => router.push("/watches")}
              className="flex items-center gap-1.5 text-radar-cyan hover:underline font-mono text-[11px]"
            >
              <span>{activeWatchesCount} Active Watches</span>
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>

          {/* Conversation List */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {conversations.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500">
                No recent tasks. Start a conversation below!
              </div>
            ) : (
              conversations.map((c) => {
                const isActive = activeConversationId === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => selectConversation(c.id)}
                    className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer text-left transition-all ${
                      isActive
                        ? "bg-slate-800/90 text-white border border-slate-700/80 shadow-inner"
                        : "text-slate-300 hover:bg-slate-800/40 hover:text-white border border-transparent"
                    }`}
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      <MessageSquare
                        className={`w-4 h-4 mt-0.5 shrink-0 ${
                          isActive ? "text-radar-cyan" : "text-slate-500 group-hover:text-slate-300"
                        }`}
                      />
                      <div className="min-w-0">
                        <p className="text-xs font-medium truncate">{c.title}</p>
                        {c.latest_message_preview && (
                          <p className="text-[11px] text-slate-400 truncate mt-0.5">
                            {c.latest_message_preview}
                          </p>
                        )}
                      </div>
                    </div>

                    <button
                      onClick={(e) => handleDeleteConversation(c.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-red-500/20 text-slate-500 hover:text-red-400 transition-all ml-1 shrink-0"
                      title="Delete task"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* Main Conversation Stream */}
        <main className="flex-1 flex flex-col bg-slate-950/40 overflow-hidden relative">
          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
            {messages.length === 0 ? (
              /* Welcome AI Agent Hero */
              <div className="max-w-3xl mx-auto my-auto py-8 text-center space-y-6">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-radar-cyan/10 border border-radar-cyan/20 text-radar-cyan text-xs font-mono">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Phase 8 Conversational Web Radar</span>
                </div>

                <div className="space-y-2">
                  <h1 className="text-2xl sm:text-4xl font-bold text-white tracking-tight">
                    What would you like Web Radar to find or watch?
                  </h1>
                  <p className="text-slate-400 text-sm max-w-xl mx-auto">
                    Ask any question, discover university admissions & job portals, or monitor e-commerce prices.
                    Web Radar autonomously searches the web, grounds answers with official sources, and persists 24/7 background monitors.
                  </p>
                </div>

                {/* Quick Prompts Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-left max-w-2xl mx-auto pt-2">
                  {quickPrompts.map((item, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendPrompt(item.prompt)}
                      className="group p-4 rounded-xl bg-slate-900/80 hover:bg-slate-850 border border-slate-800 hover:border-radar-cyan/40 transition-all text-left shadow-sm flex flex-col justify-between"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xl">{item.icon}</span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 group-hover:text-radar-cyan border border-slate-700">
                          {item.mode}
                        </span>
                      </div>
                      <div className="mt-3">
                        <p className="text-xs font-semibold text-white group-hover:text-radar-cyan transition-colors">
                          {item.title}
                        </p>
                        <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">
                          {item.desc}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* Message Thread */
              <div className="max-w-3xl mx-auto space-y-6">
                {messages.map((m) => {
                  const isUser = m.role === "user";
                  return (
                    <div
                      key={m.id}
                      className={`flex gap-3.5 ${isUser ? "justify-end" : "justify-start"}`}
                    >
                      {!isUser && (
                        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-radar-cyan to-blue-600 flex items-center justify-center text-slate-950 font-bold shrink-0 shadow-md mt-0.5">
                          <Bot className="w-4 h-4 text-slate-950" />
                        </div>
                      )}

                      <div className={`space-y-3 max-w-2xl ${isUser ? "items-end" : "items-start"}`}>
                        {/* Message Bubble */}
                        <div
                          className={`p-4 sm:p-5 rounded-2xl text-sm leading-relaxed ${
                            isUser
                              ? "bg-radar-cyan/20 border border-radar-cyan/30 text-white rounded-br-none shadow-sm"
                              : "bg-slate-900/90 border border-slate-800 text-slate-200 rounded-bl-none shadow-md backdrop-blur-sm"
                          }`}
                        >
                          {/* Assistant Mode Tag */}
                          {!isUser && m.metadata?.mode && (
                            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-800/80">
                              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-radar-cyan border border-slate-700">
                                {m.metadata.mode}
                              </span>
                              <span className="text-[11px] text-slate-400 font-mono">
                                Grounded Web Intelligence
                              </span>
                            </div>
                          )}

                          {/* Markdown formatted content */}
                          <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap">
                            {m.content}
                          </div>

                          {/* Interactive Clarification Choices */}
                          {!isUser && m.metadata?.clarification_options && m.metadata.clarification_options.length > 0 && (
                            <div className="mt-4 pt-3 border-t border-slate-800 space-y-2">
                              <p className="text-xs font-semibold text-white flex items-center gap-1.5">
                                <HelpCircle className="w-3.5 h-3.5 text-radar-cyan" />
                                Please select the intended entity:
                              </p>
                              <div className="grid grid-cols-1 gap-1.5 pt-1">
                                {m.metadata.clarification_options.map((opt: string, optIdx: number) => (
                                  <button
                                    key={optIdx}
                                    onClick={() => handleSendPrompt(opt, opt)}
                                    className="text-left px-3.5 py-2 rounded-lg bg-slate-800/80 hover:bg-radar-cyan/20 border border-slate-700/80 hover:border-radar-cyan/40 text-xs text-slate-200 hover:text-white transition-all flex items-center justify-between group"
                                  >
                                    <span>{opt}</span>
                                    <ArrowRight className="w-3 h-3 text-slate-500 group-hover:text-radar-cyan transition-transform group-hover:translate-x-0.5" />
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Discovered Sources Citations */}
                          {!isUser && m.metadata?.sources && m.metadata.sources.length > 0 && (
                            <div className="mt-4 pt-3 border-t border-slate-800/80">
                              <p className="text-[11px] font-mono text-slate-400 mb-2 flex items-center gap-1.5">
                                <Globe className="w-3.5 h-3.5 text-radar-cyan" />
                                Discovered Official Sources:
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {m.metadata.sources.map((s, sIdx) => (
                                  <a
                                    key={sIdx}
                                    href={s.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/90 hover:bg-slate-750 border border-slate-700 text-xs text-radar-cyan hover:underline transition-all"
                                  >
                                    <span className="truncate max-w-[220px]">{s.title || s.url}</span>
                                    <ExternalLink className="w-3 h-3 shrink-0" />
                                  </a>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Created Watch CTA Card */}
                          {!isUser && m.metadata?.watch_id && (
                            <div className="mt-4 p-3.5 rounded-xl bg-slate-950/80 border border-radar-cyan/40 flex items-center justify-between gap-3 shadow-inner">
                              <div className="flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-radar-cyan/15 text-radar-cyan">
                                  <Radar className="w-5 h-5 animate-spin" />
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-white">
                                    {m.metadata.watch_title || "Autonomous Watch Created"}
                                  </p>
                                  <p className="text-[11px] text-slate-400 font-mono">
                                    Status: Active • Scanning background schedule
                                  </p>
                                </div>
                              </div>
                              <button
                                onClick={() => router.push(`/watches/${m.metadata?.watch_id}`)}
                                className="px-3 py-1.5 rounded-lg bg-radar-cyan text-slate-950 text-xs font-semibold hover:bg-radar-cyan/90 transition-all flex items-center gap-1 shrink-0"
                              >
                                <span>Open Watch</span>
                                <ArrowRight className="w-3 h-3" />
                              </button>
                            </div>
                          )}
                        </div>

                        {/* Timestamp */}
                        <div className={`text-[10px] text-slate-400 px-1 font-mono ${isUser ? "text-right" : "text-left"}`}>
                          {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </div>
                      </div>

                      {isUser && (
                        <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 font-semibold shrink-0 mt-0.5">
                          <UserIcon className="w-4 h-4" />
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Thinking / Scanning Loading Bubble */}
                {isSubmitting && (
                  <div className="flex gap-3.5 justify-start">
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-radar-cyan to-blue-600 flex items-center justify-center text-slate-950 font-bold shrink-0">
                      <Radar className="w-4 h-4 text-slate-950 animate-spin" />
                    </div>
                    <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 text-slate-300 text-xs font-mono flex items-center gap-2.5">
                      <Loader2 className="w-4 h-4 animate-spin text-radar-cyan" />
                      <span>Web Radar is discovering candidate web sources & evaluating intent...</span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Bottom Floating Prompt Input Bar */}
          <div className="p-4 sm:p-5 border-t border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
            <div className="max-w-3xl mx-auto">
              <div className="relative flex items-end bg-slate-900 border border-slate-800 focus-within:border-radar-cyan/60 rounded-2xl p-2 transition-all shadow-lg">
                <textarea
                  ref={inputRef}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask Web Radar anything, discover official pages, or monitor a website..."
                  rows={2}
                  disabled={isSubmitting}
                  className="w-full bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none resize-none px-3 py-1.5 min-h-[44px] max-h-[140px]"
                />

                <div className="flex items-center gap-2 pr-1 pb-1">
                  <button
                    onClick={() => handleSendPrompt()}
                    disabled={!inputMessage.trim() || isSubmitting}
                    className="p-2.5 rounded-xl bg-radar-cyan text-slate-950 font-semibold hover:bg-radar-cyan/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md"
                    title="Send message (Enter)"
                  >
                    {isSubmitting ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 px-1 font-mono">
                <span>Press <strong>Enter</strong> to send, <strong>Shift+Enter</strong> for newline</span>
                <span>Powered by Gemini Grounded Discovery & Bright Data</span>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
