"use client";
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileText,
  Home,
  Info,
  Network,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { HuddleSchema, type Huddle, type View } from "@/types/huddle";
import { initialHuddles } from "@/data/demo";
import { backendApi, huddleApi, isLive } from "@/lib/api";
import { mapHuddleDetail } from "@/types/huddle";
import { Brand, ErrorState, EvidenceList, FlowSteps, LoadingState } from "./ui";
import { QuestionInput } from "./QuestionInput";
import { ExpertResponse } from "./ExpertResponse";
import { HuddleBrief } from "./HuddleBrief";
import { QuestionGraph } from "./QuestionGraph";

const SESSION_KEY = "pulsepoint-demo-v1";
const viewTitles: Record<View, string> = {
  home: "My workspace",
  understanding: "Question understanding",
  evidence: "Your huddle",
  expert: "Expert workspace",
  brief: "Huddle brief",
  graph: "Question intelligence",
};

export function Pulsepoint() {
  const [view, setView] = useState<View>("home");
  const [question, setQuestion] = useState("");
  const [huddles, setHuddles] = useState<Huddle[]>(isLive ? [] : initialHuddles);
  const [current, setCurrent] = useState<Huddle | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [help, setHelp] = useState(false);
  const [forceDemo, setForceDemo] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const helpDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (isLive) {
      void backendApi.getHuddles().then((result) => setHuddles(result.huddles.map((item) => mapHuddleDetail(item)))).catch((e) => setError(e instanceof Error ? e.message : "Could not load huddles from the service."));
      setHydrated(true);
      return;
    }
    try {
      const saved = sessionStorage.getItem(SESSION_KEY);
      if (saved) {
        const parsed = HuddleSchema.array().safeParse(JSON.parse(saved));
        if (parsed.success) setHuddles(parsed.data.filter((h) => h.demo));
      }
    } catch {
      /* Session storage can be unavailable in private browsers. */
    }
    setHydrated(true);
  }, []);
  useEffect(() => {
    if (hydrated) {
      try {
        sessionStorage.setItem(
          SESSION_KEY,
          JSON.stringify(huddles.filter((h) => h.demo).slice(0, 30)),
        );
      } catch {
        /* The in-memory demo remains usable. */
      }
    }
  }, [huddles, hydrated]);
  useEffect(() => {
    heading.current?.focus();
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [view]);
  useEffect(() => {
    if (help) helpDialog.current?.showModal();
    else helpDialog.current?.close();
  }, [help]);
  function navigate(next: View) {
    if (busy) return;
    setError("");
    setView(next);
  }
  function save(huddle: Huddle) {
    setCurrent(huddle);
    setHuddles((old) =>
      [huddle, ...old.filter((h) => h.id !== huddle.id)].slice(0, 30),
    );
  }
  function newHuddle() {
    if (busy) return;
    setCurrent(null);
    setQuestion("");
    setError("");
    setView("home");
    setTimeout(() => document.getElementById("clinical-question")?.focus(), 0);
  }
  async function create(demo = forceDemo) {
    setBusy(true);
    setError("");
    try {
      const huddle = await huddleApi.create(question, demo);
      save(huddle);
      setView("understanding");
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "We couldn’t prepare your huddle. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function requestExpert() {
    if (!current) return;
    setBusy(true);
    setError("");
    try {
      save(await huddleApi.requestExpert(current));
      setView("expert");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "The request could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function simulateResponse() {
    if (!current) return;
    setBusy(true);
    setError("");
    try {
      save(await huddleApi.simulate(current));
      setView("brief");
    } catch (e) {
      setError(e instanceof Error ? e.message : "The simulated response could not be completed.");
    } finally { setBusy(false); }
  }
  async function respond(text: string, mode: "text" | "voice" = "text") {
    if (!current) return;
    setBusy(true);
    setError("");
    try {
      save(await huddleApi.respond(current, text, mode));
      setView("brief");
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "The brief could not be completed. Your response is still here.",
      );
    } finally {
      setBusy(false);
    }
  }
  function open(huddle: Huddle) {
    setCurrent(huddle);
    setError("");
    setView(
      huddle.status === "complete"
        ? "brief"
        : huddle.status === "pending"
          ? "expert"
          : "evidence",
    );
  }
  const filtered = huddles.filter(
    (h) =>
      (filter === "all" || h.status === filter) &&
      `${h.question.topic} ${h.question.question}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const demoMode = !isLive || forceDemo;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <a
          className="brand-link"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("home");
          }}
          aria-label="PULSEPOINT home"
        >
          <Brand />
        </a>
        <div className="workspace-label">
          <span className="workspace-symbol">P</span>
          <div>
            Clinical workspace<small>HackGT 13 · Prototype</small>
          </div>
          <span className="signal-dot" />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <button
            className={view === "home" ? "active" : ""}
            onClick={() => navigate("home")}
            disabled={busy}
          >
            <Home size={18} /> My huddles
            <span className="nav-count">{huddles.length}</span>
          </button>
          <button
            className={view === "expert" ? "active" : ""}
            onClick={() => {
              const pending = huddles.find((h) => h.status === "pending");
              if (pending) open(pending);
              else navigate("expert");
            }}
            disabled={busy}
          >
            <Users size={18} /> Expert workspace
            {huddles.some((h) => h.status === "pending") && (
              <span className="pending-dot" />
            )}
          </button>
          <button
            className={view === "graph" ? "active" : ""}
            onClick={() => navigate("graph")}
            disabled={busy}
          >
            <Network size={18} /> Question graph
          </button>
        </nav>
        <div className="sidebar-note">
          <span className="mini-icon">
            <Activity size={21} />
          </span>
          <h3>
            Better questions.
            <br />
            Better conversations.
          </h3>
          <p>A little more clarity, right when you need it.</p>
          <span className="note-line" />
        </div>
        <div className="sidebar-bottom">
          <button className="help-button" onClick={() => setHelp(true)}>
            <CircleHelp size={17} /> About this demo <ArrowUpRight size={14} />
          </button>
          <div className="user-profile">
            <span className="avatar">HC</span>
            <div>
              HCP demo workspace<small>Clinician view</small>
            </div>
            <span className="profile-dot" />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <span>{viewTitles[view]}</span>
          </div>
          <div className="topbar-actions">
            <span className="demo-indicator">
              <span />
              {demoMode ? "Demo environment" : "Connected service"}
            </span>
            <button
              className="button secondary compact"
              onClick={newHuddle}
              disabled={busy}
            >
              <Plus size={15} /> New huddle
            </button>
          </div>
        </header>
        <main id="main-content" className={`main-content view-${view}`}>
          {view === "home" ? (
            <>
              <div className="page-intro">
                <div className="eyebrow greeting">
                  <span className="signal-dot" /> A BETTER CLINICAL CONVERSATION
                </div>
                <h1 ref={heading} tabIndex={-1}>
                  Good questions deserve
                  <br />
                  <span>more than a quick search.</span>
                </h1>
                <p>
                  The clinical question you couldn’t ask in 30 seconds.
                  <br className="desktop-break" /> Bring it here. We’ll help you
                  find the next conversation.
                </p>
              </div>
              <div className="home-grid">
                <QuestionInput
                  value={question}
                  onChange={setQuestion}
                  onSubmit={() => void create()}
                  busy={busy}
                />
                <aside className="how-it-works">
                  <span className="eyebrow">FROM QUESTION TO CLARITY</span>
                  <h2>
                    A huddle. <br />
                    Not another rabbit hole.
                  </h2>
                  <ol>
                    <li>
                      <span>
                        <Search size={17} />
                      </span>
                      <div>
                        <h3>Start with your question</h3>
                        <p>Capture what matters, in your own words.</p>
                      </div>
                    </li>
                    <li>
                      <span>
                        <BookOpen size={17} />
                      </span>
                      <div>
                        <h3>Bring the evidence together</h3>
                        <p>Relevant sources, with context you can trace.</p>
                      </div>
                    </li>
                    <li>
                      <span>
                        <Users size={17} />
                      </span>
                      <div>
                        <h3>Add the right perspective</h3>
                        <p>An expert conversation, captured in a brief.</p>
                      </div>
                    </li>
                  </ol>
                  <div className="how-footer">
                    <ShieldCheck size={15} />
                    Built around evidence. Grounded in context.
                  </div>
                </aside>
              </div>
              {error && (
                <ErrorState message={error} retry={() => void create()} />
              )}
              {error && isLive && (
                <button
                  className="button secondary"
                  onClick={() => {
                    setForceDemo(true);
                    void create(true);
                  }}
                >
                  Switch to labeled demo
                </button>
              )}
              <section className="recent-section">
                <div className="section-label">
                  <div>
                    <span className="eyebrow">PICK UP THE CONVERSATION</span>
                    <h2>Recent huddles</h2>
                  </div>
                  <label className="search-field">
                    <Search size={15} />
                    <input
                      aria-label="Search huddles"
                      placeholder="Search huddles"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </label>
                </div>
                <div
                  className="recent-filters"
                  role="group"
                  aria-label="Filter huddles"
                >
                  {[
                    { key: "all", label: "All huddles" },
                    { key: "complete", label: "Completed" },
                    { key: "pending", label: "Awaiting response" },
                  ].map((item) => (
                    <button
                      key={item.key}
                      aria-pressed={filter === item.key}
                      className={filter === item.key ? "active" : ""}
                      onClick={() => setFilter(item.key)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="huddle-table">
                  <div className="table-header">
                    <span>CLINICAL QUESTION</span>
                    <span>STATUS</span>
                    <span>SPECIALTY</span>
                    <span />
                  </div>
                  {filtered.map((h) => (
                    <button
                      key={h.id}
                      className="huddle-row"
                      onClick={() => open(h)}
                      disabled={busy}
                    >
                      <span className="huddle-name">
                        <span className="document-icon">
                          <FileText size={19} />
                        </span>
                        <span>
                          {h.question.topic}
                          <small>
                            {h.demo ? "Demo case" : "Connected huddle"} ·{" "}
                            {h.sources.length} sources
                          </small>
                        </span>
                      </span>
                      <span className={`status ${h.status}`}>
                        {h.status === "complete" ? (
                          <Check size={13} />
                        ) : (
                          <Clock3 size={13} />
                        )}{" "}
                        {h.status === "complete"
                          ? "Huddle complete"
                          : h.status === "pending"
                            ? "Awaiting expert"
                            : "Ready to review"}
                      </span>
                      <span className="specialty-cell">
                        {h.question.specialty}
                      </span>
                      <ArrowUpRight size={17} />
                    </button>
                  ))}
                  {!filtered.length && (
                    <div className="empty-state">
                      <Search size={24} />
                      <h3>No huddles found</h3>
                      <p>Try another search or start a new question.</p>
                    </div>
                  )}
                </div>
              </section>
            </>
          ) : (
            <>
              <div className="subpage-heading">
                <div>
                  <button
                    className="back-button"
                    onClick={() => navigate("home")}
                    disabled={busy}
                  >
                    <ArrowLeft size={14} /> My huddles
                  </button>
                  <span className="eyebrow">
                    {view === "graph"
                      ? "THE BIGGER PICTURE"
                      : "CONTEXT MAKES THE DIFFERENCE"}
                  </span>
                  <h1 ref={heading} tabIndex={-1}>
                    {view === "graph"
                      ? "What HCPs are asking."
                      : view === "understanding"
                        ? "Let’s get the question right."
                        : view === "evidence"
                          ? "The right context. The right perspective."
                          : view === "expert"
                            ? "Bring your perspective."
                            : "Clarity, brought together."}
                  </h1>
                  <p>
                    {view === "graph"
                      ? "Turn individual questions into a shared understanding of what matters."
                      : view === "brief"
                        ? "Your question, the evidence, and an expert perspective—all in one place."
                        : view === "expert"
                          ? "A focused question deserves a thoughtful response."
                          : "A little structure makes room for a more useful conversation."}
                  </p>
                </div>
                {view !== "graph" && (
                  <FlowSteps
                    step={
                      view === "understanding"
                        ? 0
                        : view === "evidence"
                          ? 1
                          : view === "expert"
                            ? 2
                            : 3
                    }
                  />
                )}
              </div>
              {error && <ErrorState message={error} />}
              {view === "understanding" && current && (
                <section className="understanding-panel">
                  <div className="understanding-top">
                    <span className="mini-icon">
                      <Sparkles size={22} />
                    </span>
                    <div>
                      <h2>Your question, understood.</h2>
                      <p>
                        {current.demo
                          ? "Demo classification · review the extracted context below"
                          : "Review the extracted context below"}
                      </p>
                    </div>
                    <span className="complete-label">
                      <Check size={14} /> Ready for review
                    </span>
                  </div>
                  <blockquote>{current.question.question}</blockquote>
                  <div className="extraction-grid">
                    {[
                      ["SPECIALTY", current.question.specialty],
                      ["CONDITION", current.question.condition],
                      ["TOPIC", current.question.topic],
                      ["INTENT", current.question.intent],
                    ].map(([label, value], i) => (
                      <div
                        className="extraction-item"
                        key={label}
                        style={{ animationDelay: `${i * 140}ms` }}
                      >
                        <span className="eyebrow">
                          <Check size={13} />
                          {label}
                        </span>
                        <h3>{value}</h3>
                      </div>
                    ))}
                  </div>
                  <div className="panel-actions">
                    <button
                      className="button quiet"
                      onClick={() => {
                        setQuestion(current.question.question);
                        navigate("home");
                      }}
                    >
                      Edit question
                    </button>
                    <button
                      className="button primary"
                      onClick={() => navigate("evidence")}
                    >
                      Continue to evidence <ArrowRight size={16} />
                    </button>
                  </div>
                </section>
              )}
              {view === "evidence" && current && (
                <>
                  <div className="question-strip">
                    <span className="eyebrow">YOUR QUESTION</span>
                    <p>{current.question.question}</p>
                  </div>
                  <div className="two-column">
                    <section>
                      <div className="section-label">
                        <h2>
                          Evidence to explore{" "}
                          <span className="count-tag">
                            {current.sources.length}
                          </span>
                        </h2>
                        <span className="small muted">
                          {current.demo
                            ? "Curated demo resources"
                            : "Retrieved sources"}
                        </span>
                      </div>
                      {current.sources.length ? (
                        <EvidenceList sources={current.sources} />
                      ) : (
                        <div className="empty-state">
                          <BookOpen size={28} />
                          <h3>No matching evidence in this demo</h3>
                          <p>
                            The seeded demonstration covers breast cancer. Use
                            the sample question to explore the complete flow.
                          </p>
                          <button
                            className="button secondary"
                            onClick={newHuddle}
                          >
                            Start another question
                          </button>
                        </div>
                      )}
                      <p className="source-disclaimer">
                        <Info size={15} />
                        Source links are reference material, not a
                        patient-specific recommendation.
                      </p>
                    </section>
                    <aside className="expert-card">
                      <span className="eyebrow">YOUR EXPERT MATCH</span>
                      {current.expert ? (
                        <>
                          <div className="expert-card-profile">
                            <span className="avatar expert-avatar">
                              {current.expert.initials}
                            </span>
                            <h2>{current.expert.name}</h2>
                            <p>{current.expert.specialty}</p>
                            <span className="pill">
                              {current.expert.demo
                                ? "Fictional demo profile"
                                : "Matched expert"}
                            </span>
                          </div>
                          <div className="match-score">
                            <strong>
                              {current.expert.match}
                              <span>%</span>
                            </strong>
                            <div>
                              Expertise match
                              <small>
                                Relevance score, not medical certainty
                              </small>
                            </div>
                          </div>
                          <div className="expert-tags">
                            {current.expert.expertise.map((t) => (
                              <span key={t}>{t}</span>
                            ))}
                          </div>
                          <div className="expert-context">
                            <Check size={16} />
                            <p>
                              {current.expert.demo
                                ? "A simulated expert is ready for this demo huddle."
                                : "Request an expert perspective on this question."}
                            </p>
                          </div>
                          <button
                            className="button primary full"
                            onClick={requestExpert}
                            disabled={busy}
                          >
                            {busy ? (
                              <LoadingState label="Preparing request" />
                            ) : (
                              <>
                                Continue to huddle <ArrowRight size={16} />
                              </>
                            )}
                          </button>
                          <p className="small muted centered">
                            {current.expert.demo
                              ? "Opens the synthetic expert workspace; no real clinician is contacted."
                              : "Opens the matched expert workspace."}
                          </p>
                        </>
                      ) : (
                        <div className="empty-state">
                          <Users size={28} />
                          <h3>No expert match</h3>
                          <p>There is no seeded expert for this question.</p>
                        </div>
                      )}
                    </aside>
                  </div>
                </>
              )}
              {view === "expert" &&
                (current?.status === "pending" ||
                  current?.status === "complete") && (
                  <ExpertResponse
                    key={current.id}
                    huddle={current}
                    busy={busy}
                    onSubmit={(text, mode) => void respond(text, mode)}
                    onSimulate={() => void simulateResponse()}
                  />
                )}
              {view === "expert" &&
                !(
                  current?.status === "pending" ||
                  current?.status === "complete"
                ) && (
                  <div className="empty-state">
                    <Users size={32} />
                    <h2>No huddle requests yet</h2>
                    <p>
                      Start a question and request an expert huddle to try this
                      workspace.
                    </p>
                    <button className="button primary" onClick={newHuddle}>
                      Start a huddle <ArrowRight size={16} />
                    </button>
                  </div>
                )}
              {view === "brief" && current && (
                <HuddleBrief key={current.id} huddle={current} />
              )}
              {view === "graph" && <QuestionGraph />}
            </>
          )}
          <footer className="page-footer">
            <span>
              <Activity size={14} /> PULSEPOINT
            </span>
            <span>
              HackGT 13 prototype ·{" "}
              {demoMode
                ? "Demo content. Not for clinical use."
                : "Integration preview. Not for clinical use."}
            </span>
            <button onClick={() => setHelp(true)}>
              About this demo <ArrowUpRight size={13} />
            </button>
          </footer>
        </main>
      </div>
      <dialog
        ref={helpDialog}
        onCancel={() => setHelp(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setHelp(false);
        }}
        className="help-dialog"
      >
        <div className="dialog-heading">
          <Brand />
          <button
            className="icon-button"
            aria-label="Close about dialog"
            onClick={() => setHelp(false)}
          >
            <X size={20} />
          </button>
        </div>
        <h2>A clinical conversation, reimagined.</h2>
        <p>
          PULSEPOINT is a HackGT prototype that connects questions, evidence,
          and expert perspectives.
        </p>
        <ul>
          <li>
            Use synthetic questions only; never enter real patient information.
          </li>
          <li>
            Expert profiles and graph data are fictional. Demo briefs use
            templates, not a live AI model.
          </li>
          <li>
            Source links point to public NCI resources. Summaries are
            descriptive and not clinical advice.
          </li>
          <li>
            Demo huddles stay in this browser tab’s session storage. Live
            huddles are not stored there.
          </li>
          <li>
            Voice input uses your browser’s speech service. Playback is
            synthetic speech.
          </li>
        </ul>
        <button
          className="button secondary"
          onClick={() => {
            setHuddles(isLive ? [] : initialHuddles);
            setCurrent(null);
            setQuestion("");
            setView("home");
            setHelp(false);
          }}
        >
          Reset demo data
        </button>
      </dialog>
    </div>
  );
}
