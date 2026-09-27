"use client";
import { useEffect, useState } from "react";
import {
  Check,
  Copy,
  Download,
  Headphones,
  Pause,
  ArrowUpRight,
  ShieldCheck,
  Info,
} from "lucide-react";
import type { Huddle } from "@/types/huddle";

export function HuddleBrief({ huddle }: { huddle: Huddle }) {
  const [speaking, setSpeaking] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(
    () => () => {
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    },
    [],
  );
  if (!huddle.brief)
    return <p>This huddle is waiting for an expert response.</p>;
  const brief = huddle.brief;
  const text = `PULSEPOINT — CLINICAL HUDDLE BRIEF\n${brief.synthesisLabel}\n\nQUESTION\n${huddle.question.question}\n\nEVIDENCE\n${brief.evidence.join("\n")}\n\nEXPERT PERSPECTIVE${huddle.expert?.demo ? " (FICTIONAL DEMO)" : ""}\n${huddle.response}\n\nKEY TAKEAWAYS\n${brief.takeaways.map((t) => `• ${t}`).join("\n")}\n\nUNCERTAINTY\n${brief.uncertainty}\n\nSOURCES\n${huddle.sources.map((s) => `${s.title}\n${s.url}`).join("\n\n")}`;
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setNotice("Brief copied to clipboard.");
    } catch {
      setNotice("Clipboard is unavailable. Use Download brief instead.");
    }
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob([text], { type: "text/plain;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "pulsepoint-huddle-brief.txt";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function speak() {
    if (!("speechSynthesis" in window)) {
      setNotice(
        "Audio playback is unavailable in this browser. The full response is shown below.",
      );
      return;
    }
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(
      huddle.response || "No response available.",
    );
    utterance.rate = 0.94;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => {
      setSpeaking(false);
      setNotice("Audio could not play. Read the response below.");
    };
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  }
  return (
    <div className="brief-layout">
      <article className="brief-paper">
        <div className="brief-masthead">
          <span className="eyebrow">PULSEPOINT / CLINICAL HUDDLE BRIEF</span>
          <span className="complete-label">
            <Check size={14} /> Huddle complete
          </span>
        </div>
        <div className="brief-question">
          <span className="eyebrow">01 / CLINICAL QUESTION</span>
          <h2>{huddle.question.question}</h2>
          <div className="flex flex-wrap gap-2">
            <span className="pill">{huddle.question.specialty}</span>
            <span className="pill">{huddle.question.topic}</span>
          </div>
        </div>
        <section className="brief-section">
          <div className="brief-section-heading">
            <span className="section-index">02</span>
            <h3>What the evidence says</h3>
            <span className="tiny-tag">CURATED SOURCES</span>
          </div>
          {brief.evidence.map((line) => (
            <p key={line}>{line}</p>
          ))}
          <div className="inline-citations">
            {huddle.sources.map((s, i) => (
              <a key={s.id} href={s.url} target="_blank" rel="noreferrer">
                [{i + 1}] {s.publisher}
                <ArrowUpRight size={12} />
              </a>
            ))}
          </div>
        </section>
        <section className="brief-section">
          <div className="brief-section-heading">
            <span className="section-index">03</span>
            <h3>Expert perspective</h3>
            <span className="tiny-tag">
              {huddle.expert?.demo ? "SIMULATED OPINION" : "EXPERT OPINION"}
            </span>
          </div>
          <blockquote>{huddle.response}</blockquote>
          <div className="expert-byline">
            <span className="avatar small-avatar">
              {huddle.expert?.initials}
            </span>
            <span>
              {huddle.expert?.name}
              <small>
                {huddle.expert?.demo
                  ? "Fictional demo expert"
                  : huddle.expert?.specialty}
              </small>
            </span>
          </div>
        </section>
        <section className="brief-section takeaways">
          <div className="brief-section-heading">
            <span className="section-index">04</span>
            <h3>Key takeaways</h3>
            <span className="tiny-tag">
              {huddle.demo ? "DEMO SYNTHESIS" : "AI SYNTHESIS"}
            </span>
          </div>
          <ul>
            {brief.takeaways.map((t) => (
              <li key={t}>
                <Check size={16} />
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="uncertainty">
          <Info size={20} />
          <div>
            <h3>What remains uncertain</h3>
            <p>{brief.uncertainty}</p>
          </div>
        </section>
        <section className="brief-section sources-section">
          <h3>Sources & references</h3>
          <ol>
            {huddle.sources.map((s) => (
              <li key={s.id}>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.title}
                  <ArrowUpRight size={14} />
                </a>
                <small>
                  {s.publisher} · {s.date}
                </small>
              </li>
            ))}
          </ol>
        </section>
        <footer className="brief-footer">
          <ShieldCheck size={15} />
          {brief.synthesisLabel}
        </footer>
      </article>
      <aside className="brief-aside">
        <div className="eyebrow">A CLEARER NEXT CONVERSATION</div>
        <h3>
          Keep the context.
          <br />
          Carry it forward.
        </h3>
        <p>Evidence, perspective, and uncertainty in one place.</p>
        <button className="button primary full" onClick={download}>
          <Download size={16} /> Download brief
        </button>
        <button className="button secondary full" onClick={copy}>
          <Copy size={16} /> Copy brief
        </button>
        <div className="audio-card">
          <Headphones size={23} />
          <h4>Listen to the perspective</h4>
          <p>
            Synthetic reading of the response. This is not a clinician’s
            recording.
          </p>
          <button className="text-button" onClick={speak}>
            {speaking ? <Pause size={15} /> : <Headphones size={15} />}{" "}
            {speaking ? "Stop playback" : "Play response"}
          </button>
        </div>
        {notice && (
          <p className="notice" role="status">
            {notice}
          </p>
        )}
      </aside>
    </div>
  );
}
