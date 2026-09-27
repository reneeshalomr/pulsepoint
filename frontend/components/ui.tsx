import {
  Activity,
  ArrowUpRight,
  Check,
  FileText,
  Info,
  LoaderCircle,
} from "lucide-react";
import type { Evidence } from "@/types/huddle";
export function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark">
        <Activity size={21} strokeWidth={1.7} />
      </span>
      PULSEPOINT
    </span>
  );
}
export function LoadingState({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <LoaderCircle className="spin" size={17} />
      {label}
    </span>
  );
}
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="error-box" role="alert">
      <Info size={18} />
      <span>{message}</span>
      {retry && (
        <button className="text-button" onClick={retry}>
          Retry
        </button>
      )}
    </div>
  );
}
export function EvidenceList({ sources }: { sources: Evidence[] }) {
  return (
    <div className="evidence-list">
      {sources.map((source, i) => (
        <article className="evidence-card" key={source.id}>
          <div className="source-number">0{i + 1}</div>
          <div className="source-content">
            <div className="flex flex-wrap items-center gap-2">
              <span className="eyebrow">{source.type}</span>
              <span className="source-status">
                <Check size={12} />
                {source.verified ? "Source linked" : "Unverified"}
              </span>
            </div>
            <h3>
              {source.url && /^https?:\/\//.test(source.url) ? <a href={source.url} target="_blank" rel="noreferrer">{source.title}<ArrowUpRight size={17} /></a> : <span>{source.title}</span>}
            </h3>
            <p>{source.snippet}</p>
            <div className="source-meta">
              <FileText size={13} />
              {source.publisher}
              <span>·</span>
              {source.date || "Date not provided"}
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
export function FlowSteps({ step }: { step: number }) {
  return (
    <ol className="flow-steps" aria-label="Huddle progress">
      {["Question", "Evidence", "Expert", "Brief"].map((label, i) => (
        <li
          key={label}
          className={i <= step ? "active" : ""}
          aria-current={i === step ? "step" : undefined}
        >
          <span>{i < step ? <Check size={12} /> : i + 1}</span>
          {label}
        </li>
      ))}
    </ol>
  );
}
