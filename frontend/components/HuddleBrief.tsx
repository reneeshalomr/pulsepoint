"use client";
import { useEffect, useRef, useState } from "react";
import {
  Check,
  Copy,
  Download,
  Headphones,
  Pause,
  ArrowUpRight,
  ShieldCheck,
  Info,
  X,
} from "lucide-react";
import type { Huddle } from "@/types/huddle";

export function HuddleBrief({ huddle }: { huddle: Huddle }) {
  const [speaking, setSpeaking] = useState(false);
  const [notice, setNotice] = useState("");
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewPrepared, setReviewPrepared] = useState(false);
  const reviewDialog = useRef<HTMLDialogElement>(null);
  useEffect(
    () => () => {
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    },
    [],
  );
  useEffect(() => {
    const dialog = reviewDialog.current;
    if (!dialog) return;
    if (reviewOpen && !dialog.open) dialog.showModal();
    if (!reviewOpen && dialog.open) dialog.close();
  }, [reviewOpen]);
  if (!huddle.brief)
    return <p>This huddle is waiting for an expert perspective.</p>;
  const brief = huddle.brief;
  const text = `CLINIQ — CLINICAL HUDDLE BRIEF\n${brief.synthesisLabel}\n\nQUESTION\n${huddle.question.question}\n\nEVIDENCE\n${brief.evidence.join("\n")}\n\nSYNTHETIC EXPERT PERSPECTIVE${huddle.responseIsSimulated ? " (DEMO)" : ""}\n${huddle.response}\n\nAI SYNTHESIS\n${brief.takeaways.map((t) => `• ${t}`).join("\n")}\n\nUNCERTAINTY\n${brief.uncertainty}\n\nSOURCES\n${huddle.sources.map((s) => `${s.title}\n${s.citation || s.publisher}${s.url ? `\n${s.url}` : ""}`).join("\n\n")}`;
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
    link.download = "cliniq-huddle-brief.txt";
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
          <span className="eyebrow">CLINIQ / CLINICAL HUDDLE BRIEF</span>
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
            <h3>EVIDENCE</h3>
          </div>
          <p className="brief-layer-copy">What the retrieved sources say.</p>
          {brief.evidence.map((line) => (
            <p key={line}>{line}</p>
          ))}
          <div className="inline-citations">
            {huddle.sources.map((s) => (
              s.url ? <a key={s.id} href={s.url} target="_blank" rel="noreferrer">[{s.id}] {s.citation || s.publisher}<ArrowUpRight size={12} /></a> : <span key={s.id}>[{s.id}] {s.citation || s.publisher}</span>
            ))}
          </div>
        </section>
        <section className="brief-section">
          <div className="brief-section-heading">
            <span className="section-index">03</span>
            <h3>EXPERT PERSPECTIVE</h3>
            <span className="tiny-tag">
              {huddle.responseIsSimulated ? "SYNTHETIC EXPERT PERSPECTIVE" : huddle.expert?.demo ? "SYNTHETIC DEMO PROFILE" : "EXPERT PERSPECTIVE"}
            </span>
          </div>
          <p className="brief-layer-copy">
            How relevant expertise can contextualize the evidence.
          </p>
          <blockquote>{huddle.response}</blockquote>
          <div className="expert-byline">
            <span className="avatar small-avatar">
              {huddle.expert?.initials}
            </span>
            <span>
              {huddle.expert?.name}
              <small>
                {huddle.expert?.demo
                  ? "DEMO EXPERT / Synthetic profile"
                  : huddle.expert?.specialty}
              </small>
            </span>
          </div>
        </section>
        <section className="patient-review-prompt">
          <span className="eyebrow">PATIENT-SPECIFIC REVIEW</span>
          <p>Some clinical questions require additional patient context before expert review.</p>
          <button
            className="button secondary compact"
            type="button"
            onClick={() => {
              setReviewPrepared(false);
              setReviewOpen(true);
            }}
          >
            Prepare case for expert review
          </button>
        </section>
        <section className="brief-section takeaways">
          <div className="brief-section-heading">
            <span className="section-index">04</span>
            <h3>AI SYNTHESIS</h3>
            <span className="tiny-tag">
              {brief.generatedBy === "template" ? "DETERMINISTIC TEMPLATE" : brief.generatedBy === "llm" ? "AI-GENERATED" : "EXTERNAL SYNTHESIS"}
            </span>
          </div>
          <p className="brief-layer-copy">
            A structured synthesis of the retrieved evidence and expert perspective.
          </p>
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
            <div className="brief-section-heading">
              <span className="section-index">05</span>
              <h3>WHAT REMAINS UNCERTAIN</h3>
            </div>
            <p>{brief.uncertainty}</p>
          </div>
        </section>
        <section className="brief-section sources-section">
          <div className="brief-section-heading">
            <span className="section-index">06</span>
            <h3>SOURCES & REFERENCES</h3>
          </div>
          <ol>
            {huddle.sources.map((s) => (
              <li key={s.id}>
                {s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.title}<ArrowUpRight size={14} /></a> : <span>{s.title}</span>}
                <small>
                  {s.citation || s.publisher}{s.date ? ` · ${s.date}` : ""}
                </small>
              </li>
            ))}
          </ol>
        </section>
        <footer className="brief-footer">
          <ShieldCheck size={15} />
          {brief.synthesisLabel} · Not a clinical recommendation
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
            {speaking ? "Stop playback" : "Play perspective"}
          </button>
        </div>
        {notice && (
          <p className="notice" role="status">
            {notice}
          </p>
        )}
      </aside>
      <dialog
        ref={reviewDialog}
        className="review-dialog"
        aria-labelledby="patient-review-title"
        onCancel={(event) => {
          event.preventDefault();
          setReviewOpen(false);
        }}
        onClose={() => setReviewOpen(false)}
        onClick={(event) => {
          if (event.target === event.currentTarget) setReviewOpen(false);
        }}
      >
        <div className="review-dialog-heading">
          <span className="eyebrow">PATIENT-SPECIFIC REVIEW</span>
          <button
            className="icon-button"
            type="button"
            aria-label="Close patient-specific review preview"
            onClick={() => setReviewOpen(false)}
          >
            <X size={19} />
          </button>
        </div>
        <h2 id="patient-review-title">Prepare a case for expert review</h2>
        <p>
          Additional clinical context would be needed for a patient-specific expert review.
        </p>
        <h3>Context requested</h3>
        <ul className="review-context-list">
          {["Age", "Disease subtype", "Prior treatment history", "Biomarker results", "Current disease status"].map((item) => (
            <li key={item}><Check size={15} /> {item}</li>
          ))}
        </ul>
        <p className="review-safety-note">
          Prototype only. No patient information is collected, stored, or sent, and no real clinician is contacted.
        </p>
        {reviewPrepared ? (
          <div className="review-confirmation" role="status">
            <Check size={16} /> Preview prepared. Nothing was submitted or shared.
          </div>
        ) : (
          <button
            className="button primary full"
            type="button"
            onClick={() => setReviewPrepared(true)}
          >
            Prepare expert review
          </button>
        )}
      </dialog>
    </div>
  );
}
