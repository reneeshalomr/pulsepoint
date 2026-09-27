"use client";
import {
  ArrowRight,
  AudioLines,
  Keyboard,
  Mic,
  ShieldCheck,
  Square,
} from "lucide-react";
import { useRef } from "react";
import { EXAMPLE_QUESTION } from "@/data/demo";
import { useVoice } from "@/hooks/useVoice";
import { LoadingState } from "./ui";

export function QuestionInput({
  value,
  onChange,
  onSubmit,
  busy,
}: {
  value: string;
  onChange: (text: string) => void;
  onSubmit: () => void;
  busy: boolean;
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  const { listening, notice, toggle } = useVoice((text) =>
    onChange(text.slice(0, 2000)),
  );
  return (
    <div className="question-composer">
      <div className="composer-heading">
        <span className="eyebrow">YOUR NEXT CLINICAL CONVERSATION</span>
        <AudioLines size={22} />
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <label className="sr-only" htmlFor="clinical-question">
          Clinical question
        </label>
        <textarea
          ref={input}
          id="clinical-question"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          maxLength={2000}
          placeholder="What’s the question on your mind?"
          rows={3}
          required
          disabled={busy}
        />
        <div className="composer-tools">
          <button
            type="button"
            className={`voice-button ${listening ? "recording" : ""}`}
            onClick={toggle}
            disabled={busy}
          >
            {listening ? <Square size={16} /> : <Mic size={17} />}{" "}
            {listening ? "Stop listening" : "Speak your question"}
          </button>
          <span className="character-count">{value.length}/2,000</span>
        </div>
        <div className="composer-actions">
          <button
            type="submit"
            className="button primary"
            disabled={busy || !value.trim()}
          >
            {busy ? (
              <LoadingState label="Preparing huddle" />
            ) : (
              <>
                Start huddle <ArrowRight size={17} />
              </>
            )}
          </button>
          <button
            type="button"
            className="button quiet"
            onClick={() => input.current?.focus()}
          >
            <Keyboard size={17} /> Type question
          </button>
        </div>
      </form>
      {listening && (
        <div className="voice-status" role="status">
          <span className="record-dot" />
          Listening. Speak your demo question.
        </div>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <div className="composer-footer">
        <ShieldCheck size={15} />
        <span>Synthetic cases only. Don’t include patient identifiers.</span>
      </div>
      <p className="voice-privacy">
        Voice transcription uses your browser’s speech service.
      </p>
      <button
        className="sample-button"
        onClick={() => {
          onChange(EXAMPLE_QUESTION);
          input.current?.focus();
        }}
        disabled={busy}
      >
        Try a sample question <ArrowUpRightSmall />
      </button>
    </div>
  );
}
function ArrowUpRightSmall() {
  return <ArrowRight size={13} style={{ transform: "rotate(-35deg)" }} />;
}
