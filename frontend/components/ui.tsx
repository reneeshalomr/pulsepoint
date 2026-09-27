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
      CLINIQ
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
function EvidenceCard({ source, index }: { source: Evidence; index: number }) {
  return (
    <article className="evidence-card" key={source.id}>
      <div className="source-number">{String(index + 1).padStart(2, "0")}</div>
      <div className="source-content">
        <div className="flex flex-wrap items-center gap-2">
          <span className="eyebrow">{source.type}</span>
          <span className="source-status">
            <Check size={12} />
            {source.verified ? "Source linked" : "Unverified"}
          </span>
        </div>
        <h3>
          {source.url && /^https?:\/\//.test(source.url) ? (
            <a href={source.url} target="_blank" rel="noreferrer">
              {source.title}<ArrowUpRight size={17} />
            </a>
          ) : (
            <span>{source.title}</span>
          )}
        </h3>
        <p>{source.snippet}</p>
        <div className="source-meta">
          <FileText size={13} />
          <span>{source.external_id || source.id}</span>
          <span>·</span>
          {source.publisher}
          <span>·</span>
          {source.date || "Date not provided"}
        </div>
      </div>
    </article>
  );
}

export function EvidenceList({ sources }: { sources: Evidence[] }) {
  const hasRelevance = sources.some((source) => source.relevance_type);
  if (!hasRelevance) {
    return (
      <div className="evidence-list">
        {sources.map((source, index) => (
          <EvidenceCard key={source.id} source={source} index={index} />
        ))}
      </div>
    );
  }
  const direct = sources.filter((source) => source.relevance_type === "direct");
  const contextual = sources.filter((source) => source.relevance_type === "contextual");
  const unclassified = sources.filter((source) => !source.relevance_type);
  const renderGroup = (label: string, items: Evidence[], className: string) =>
    items.length > 0 && (
      <section className="evidence-group">
        <h3 className={`relevance-badge ${className}`}>{label}</h3>
        <div>
          {items.map((source) => (
            <EvidenceCard
              key={source.id}
              source={source}
              index={sources.indexOf(source)}
            />
          ))}
        </div>
      </section>
    );
  return (
    <div className="evidence-list evidence-list-classified">
      <p className="evidence-relevance-note">
        Relevance reflects how closely a source matches the question; it does
        not indicate medical certainty or evidence quality.
      </p>
      {renderGroup("DIRECTLY RELEVANT", direct, "direct")}
      {renderGroup("CONTEXTUAL", contextual, "contextual")}
      {unclassified.length > 0 && renderGroup("OTHER RETRIEVED SOURCES", unclassified, "other")}
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
