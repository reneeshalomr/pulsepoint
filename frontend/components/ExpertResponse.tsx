"use client";
import { useState } from "react";
import { ArrowRight, Mic, Square, Sparkles } from "lucide-react";
import type { Huddle } from "@/types/huddle";
import { useVoice } from "@/hooks/useVoice";
import { EvidenceList, LoadingState } from "./ui";

export function ExpertResponse({
  huddle,
  busy,
  onSubmit,
  onSimulate,
}: {
  huddle: Huddle;
  busy: boolean;
  onSubmit: (text: string, mode: "text" | "voice") => void;
  onSimulate: () => void;
}) {
  const [response, setResponse] = useState(huddle.response || "");
  const [voiceUsed, setVoiceUsed] = useState(false);
  const voice = useVoice((text) => {
    setVoiceUsed(true);
    setResponse((old) => `${old} ${text}`.trim().slice(0, 4000));
  });
  return (
    <div className="two-column expert-layout">
      <section>
        <div className="section-label">
          <span className="eyebrow">THE CLINICAL QUESTION</span>
          <span className="pill">{huddle.question.specialty}</span>
        </div>
        <h2 className="question-display">{huddle.question.question}</h2>
        <h3 className="section-title">Evidence context</h3>
        <EvidenceList sources={huddle.sources} />
      </section>
      <section className="response-panel">
        <div className="expert-identity">
          <span className="avatar large">
            {huddle.expert?.initials || "EX"}
          </span>
          <div>
            <h3>{huddle.expert?.name || "Expert perspective"}</h3>
            <p>
              {huddle.expert?.demo
                ? "DEMO EXPERT / Synthetic profile"
                : huddle.expert?.specialty}
            </p>
          </div>
        </div>
        <h2>Your perspective matters.</h2>
        <p className="muted">
          Add context, call out uncertainty, and help focus the next
          conversation.
        </p>
        <button
          type="button"
          className={`button secondary full ${voice.listening ? "recording" : ""}`}
          onClick={voice.toggle}
          disabled={busy}
        >
          {voice.listening ? <Square size={17} /> : <Mic size={17} />}{" "}
          {voice.listening ? "Stop recording" : "Record response"}
        </button>
        <p className="small muted">
          Speech is transcribed to text by your browser; audio is not stored.
        </p>
        {voice.notice && (
          <p className="notice" role="status">
            {voice.notice}
          </p>
        )}
        {voice.listening && (
          <p className="voice-status" role="status">
            <span className="record-dot" /> Listening…
          </p>
        )}
        <label htmlFor="expert-response" className="field-label">
          Or type your response
        </label>
        <textarea
          id="expert-response"
          rows={8}
          value={response}
          onChange={(e) => setResponse(e.target.value)}
          maxLength={4000}
          placeholder="What would you highlight from the evidence? What is still uncertain?"
          disabled={busy}
        />
        <div className="flex justify-between small muted">
          <span>20 characters minimum</span>
          <span>{response.length}/4,000</span>
        </div>
        {huddle.expert?.demo && (
          <button
            className="text-button sample-response"
            disabled={busy}
            onClick={onSimulate}
          >
            <Sparkles size={14} /> Use synthetic expert perspective
          </button>
        )}
        <button
          className="button primary full"
          disabled={busy || response.trim().length < 20}
          onClick={() => onSubmit(response, voiceUsed ? "voice" : "text")}
        >
          {busy ? (
            <LoadingState label="Preparing brief" />
          ) : (
            <>
              Create huddle brief <ArrowRight size={17} />
            </>
          )}
        </button>
        <p className="small muted">
          {huddle.expert?.demo
            ? "Demo response only. No request is sent to a real clinician."
            : "Submit this perspective to the connected huddle service."}
        </p>
      </section>
    </div>
  );
}
