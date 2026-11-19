"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Bot,
  Send,
  Sparkles,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  RefreshCw,
  User,
} from "lucide-react";
import { AirQualityCurrentResponse, AIChatMessage } from "../lib/types";
import { SUGGESTED_QUESTIONS } from "../lib/constants";
import { sendAIChat } from "../lib/api";

interface AIChatDrawerProps {
  currentAirQuality: AirQualityCurrentResponse;
  comparisonContext?: AirQualityCurrentResponse[];
}

export function AIChatDrawer({ currentAirQuality, comparisonContext }: AIChatDrawerProps) {
  const [messages, setMessages] = useState<AIChatMessage[]>([
    {
      role: "assistant",
      content: `Hello! I am your AirAware AI assistant. I am currently grounded with live observations from **${currentAirQuality.location.name}** (CPCB AQI: **${currentAirQuality.aqi ?? "N/A"}** - ${currentAirQuality.category ?? "Unknown"}). How can I assist with precautions, pollutant analysis, or activity recommendations today?`,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [modelUsed, setModelUsed] = useState<string>("Grounded AI Engine");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (messageText: string) => {
    const text = messageText.trim();
    if (!text || loading) return;

    const userMsg: AIChatMessage = { role: "user", content: text };
    const updatedHistory = [...messages, userMsg];
    setMessages(updatedHistory);
    setInput("");
    setLoading(true);

    try {
      const resp = await sendAIChat({
        message: text,
        current_context: currentAirQuality,
        comparison_context: comparisonContext,
        chat_history: updatedHistory.slice(-6),
      });

      setModelUsed(resp.model_used);
      setMessages([...updatedHistory, { role: "assistant", content: resp.reply }]);
    } catch (err: any) {
      setMessages([
        ...updatedHistory,
        {
          role: "assistant",
          content:
            "I encountered an issue connecting to the AI inference service. However, verified dashboard readings and deterministic recommendations remain fully accessible above.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-navy-900/90 border border-navy-800 rounded-3xl p-6 shadow-xl flex flex-col h-[650px] relative overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-navy-800">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-md">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-bold text-white tracking-tight">AI Environmental Assistant</h3>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                Grounded Context
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Active Context: {currentAirQuality.location.name} • {modelUsed}
            </p>
          </div>
        </div>
      </div>

      {/* Suggested Quick Questions */}
      <div className="py-2 flex items-center gap-1.5 overflow-x-auto no-scrollbar border-b border-navy-800/60">
        {SUGGESTED_QUESTIONS.map((q, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(q)}
            disabled={loading}
            className="whitespace-nowrap px-3 py-1 rounded-xl bg-navy-850 hover:bg-navy-800 text-[11px] font-medium text-slate-300 hover:text-cyan-300 border border-navy-700/60 transition-colors shrink-0"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4 pr-1">
        {messages.map((m, idx) => {
          const isUser = m.role === "user";
          return (
            <div
              key={idx}
              className={`flex items-start space-x-2.5 ${isUser ? "flex-row-reverse space-x-reverse" : ""}`}
            >
              <div
                className={`w-7 h-7 rounded-xl flex items-center justify-center shrink-0 text-xs font-bold ${
                  isUser
                    ? "bg-cyan-500 text-slate-950"
                    : "bg-navy-800 text-cyan-400 border border-navy-700"
                }`}
              >
                {isUser ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
              </div>

              <div
                className={`p-3.5 rounded-2xl text-xs max-w-[85%] leading-relaxed ${
                  isUser
                    ? "bg-cyan-600 text-white rounded-tr-none shadow-sm font-medium"
                    : "bg-navy-850/90 text-slate-200 border border-navy-700/60 rounded-tl-none whitespace-pre-wrap"
                }`}
              >
                {m.content}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex items-center space-x-2 text-xs text-slate-400 bg-navy-850 p-3 rounded-2xl w-fit">
            <RefreshCw className="w-3.5 h-3.5 animate-spin text-cyan-400" />
            <span>Formulating grounded response from verified measurements...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(input);
        }}
        className="pt-3 border-t border-navy-800 flex items-center space-x-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about current air quality, precautions, or pollutants..."
          className="flex-1 bg-navy-850 border border-navy-700 rounded-2xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="p-2.5 rounded-2xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold transition-all shadow-md"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>

      {/* Grounding & Ethics Footer */}
      <p className="text-[10px] text-slate-400 text-center mt-2">
        AirAware AI responses are strictly grounded in CPCB guidelines and verified data. No medical diagnoses are provided.
      </p>
    </div>
  );
}
