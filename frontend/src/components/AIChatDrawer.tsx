"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Bot,
  Send,
  RefreshCw,
  User,
} from "lucide-react";
import { AirQualityPipelineResponse, AIChatMessage, CityInfo } from "../lib/types";
import { SUGGESTED_QUESTIONS, POPULAR_CITIES } from "../lib/constants";
import { sendAIChat } from "../lib/api";
import {
  classifyApiErrorMessage,
  extractComparisonTargets,
  MAX_CHAT_MESSAGE_CHARS,
} from "../lib/chatHistory";

interface AIChatDrawerProps {
  currentAirQuality: AirQualityPipelineResponse;
  cities?: CityInfo[];
  activity?: string;
  sensitivityPreference?: string;
  duration?: string;
}

export function AIChatDrawer({
  currentAirQuality,
  cities,
  activity,
  sensitivityPreference,
  duration,
}: AIChatDrawerProps) {
  const idx = currentAirQuality.indicative_index;
  const locationName = currentAirQuality.location.name;

  const [messages, setMessages] = useState<AIChatMessage[]>([
    {
      role: "assistant",
      isLocalOnly: true,
      content: `Hello! I am your AirAware AI assistant. I am currently grounded with model-derived estimates for **${locationName}** (Indicative Index: **${idx.value ?? "N/A"}** - ${idx.category ?? "Unknown"}). How can I help with precautions, pollutant analysis, or activity recommendations today?`,
    },
  ]);
  const [input, setInput] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [modelUsed, setModelUsed] = useState<string>("Grounded AI Engine");
  const [explanationMode, setExplanationMode] = useState<string>("");
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

    if (text.length > MAX_CHAT_MESSAGE_CHARS) {
      setValidationError(
        `Question exceeds the ${MAX_CHAT_MESSAGE_CHARS}-character limit (${text.length}/${MAX_CHAT_MESSAGE_CHARS}). Please shorten your message.`
      );
      return;
    }

    setValidationError(null);
    const priorHistory = messages;
    const userMsg: AIChatMessage = { role: "user", content: text };
    const updatedMessages = [...priorHistory, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setLoading(true);

    try {
      const knownCities = cities && cities.length > 0 ? cities : POPULAR_CITIES;
      const compareLocations = extractComparisonTargets(
        text,
        {
          city: locationName,
          latitude: currentAirQuality.coordinates.requested_latitude,
          longitude: currentAirQuality.coordinates.requested_longitude,
        },
        knownCities
      );
      // NEVER send current_context or comparison_context — backend forbids them.
      const resp = await sendAIChat({
        message: text,
        city: locationName,
        latitude: currentAirQuality.coordinates.requested_latitude,
        longitude: currentAirQuality.coordinates.requested_longitude,
        compare_locations: compareLocations,
        activity,
        sensitivity_preference: sensitivityPreference,
        duration,
        chat_history: priorHistory,
      });

      setModelUsed(resp.model_used);
      setExplanationMode(resp.explanation_mode);
      setMessages([
        ...updatedMessages,
        {
          role: "assistant",
          content: resp.reply,
          historyContent: resp.history_summary || undefined,
          attestation: resp.reply_attestation || undefined,
        },
      ]);
    } catch (err: unknown) {
      const classified = classifyApiErrorMessage(err);
      setMessages([
        ...updatedMessages,
        {
          role: "assistant",
          isLocalOnly: true,
          content: classified.message,
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
              <h3 className="text-base font-bold text-white tracking-tight">
                AI Environmental Assistant
              </h3>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 whitespace-nowrap shrink-0">
                Server-Grounded
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Context: {locationName} • {modelUsed}
              {explanationMode && (
                <span className="ml-1.5 text-[10px] text-slate-400">
                  ({explanationMode === "llm_grounded" ? "LLM Grounded" : "Deterministic Fallback"})
                </span>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Quick Questions */}
      <div className="py-2 flex items-center gap-1.5 overflow-x-auto no-scrollbar border-b border-navy-800/60">
        {SUGGESTED_QUESTIONS.map((q, qIdx) => (
          <button
            key={qIdx}
            type="button"
            onClick={() => handleSend(q)}
            disabled={loading}
            className="whitespace-nowrap px-3 py-1 rounded-xl bg-navy-850 hover:bg-navy-800 text-[11px] font-medium text-slate-300 hover:text-cyan-300 border border-navy-700/60 transition-colors shrink-0"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div aria-live="polite" aria-label="AI conversation messages" className="flex-1 overflow-y-auto py-4 space-y-4 pr-1">
        {messages.map((m, i) => {
          const isUser = m.role === "user";
          return (
            <div
              key={i}
              className={`flex items-start space-x-2.5 ${
                isUser ? "flex-row-reverse space-x-reverse" : ""
              }`}
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
                className={`p-3.5 rounded-2xl text-xs max-w-[85%] leading-relaxed break-words overflow-hidden ${
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
            <span>Formulating server-grounded response...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Inline Validation Message */}
      {validationError && (
        <div role="alert" className="mb-2 px-3 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-300">
          {validationError}
        </div>
      )}

      {/* Input */}
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
          maxLength={MAX_CHAT_MESSAGE_CHARS}
          onChange={(e) => {
            setInput(e.target.value);
            if (validationError) setValidationError(null);
          }}
          placeholder="Ask about air quality, precautions, or pollutants..."
          className="flex-1 bg-navy-850 border border-navy-700 rounded-2xl px-4 py-2.5 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-cyan-500 transition-colors"
          aria-label="Chat message input"
        />
        {input.length >= 800 && (
          <span className="text-[10px] text-slate-400 tabular-nums shrink-0">
            {input.length}/{MAX_CHAT_MESSAGE_CHARS}
          </span>
        )}
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="p-2.5 rounded-2xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold transition-all shadow-md"
          aria-label="Send message"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>

      {/* Footer */}
      <p className="text-[10px] text-slate-400 text-center mt-2">
        AI responses are grounded in server-verified CAMS model data using CPCB guidelines. No
        medical diagnoses are provided. Data reflects model-derived estimates, not physical station
        observations.
      </p>
    </div>
  );
}
