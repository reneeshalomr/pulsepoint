"use client";
import { useEffect, useState } from "react";
import { ArrowUpRight, CircleHelp, TrendingUp } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from "recharts";
import { graphTopics } from "@/data/demo";
import { backendApi, isLive } from "@/lib/api";
import type { AnalyticsDTO } from "@/types/huddle";

export function QuestionGraph() {
  const [specialty, setSpecialty] = useState("All specialties");
  const [analytics, setAnalytics] = useState<AnalyticsDTO | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!isLive) return;
    setError("");
    void backendApi.getAnalytics(30, specialty === "All specialties" ? undefined : specialty)
      .then(setAnalytics)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Question analytics could not be loaded."));
  }, [specialty]);

  const factor = specialty === "Oncology" ? 0.7 : specialty === "Cardiology" ? 0.3 : 1;
  const data = isLive
    ? (analytics?.by_topic.map((row) => ({ topic: row.name, count: row.count })) || [])
    : graphTopics.map((row) => ({ ...row, count: Math.round(row.count * factor) }));
  const total = isLive ? analytics?.total ?? 0 : data.reduce((sum, row) => sum + row.count, 0);
  const unanswered = isLive ? analytics?.unanswered.reduce((sum, row) => sum + row.count, 0) ?? 0 : Math.round(16 * factor);
  const leading = data[0];
  const specialties = isLive ? analytics?.by_specialty || [] : [{ name: "Oncology", count: 70 }, { name: "Cardiology", count: 30 }];
  return (
    <div className="graph-page">
      <div className="graph-toolbar">
        <div>
          <span className="pill amber">SYNTHETIC DEMO ANALYTICS</span>
          <p className="small muted">Anonymized aggregate category signals only. No individual HCP question text or identity is shown; values are synthetic demo aggregates.</p>
        </div>
        <label className="select-label">Specialty
          <select value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
            <option>All specialties</option><option>Oncology</option><option>Cardiology</option><option>Endocrinology</option>
          </select>
        </label>
      </div>
      {error && <p role="alert" className="error-box">{error}</p>}
      <div className="graph-metrics">
        <div><span className="eyebrow">{isLive ? "QUESTIONS · 30 DAYS" : "QUESTIONS IN THE DEMO"}</span><strong>{total}</strong><p>{isLive ? "Anonymized category signals" : "Across five clinical topics"}</p></div>
        <div><span className="eyebrow">LEADING TOPIC</span><strong className="metric-text">{leading?.topic || "No topic data"}</strong><p>{total ? Math.round(((leading?.count || 0) / total) * 100) : 0}% of selected questions</p></div>
        <div><span className="eyebrow">UNANSWERED</span><strong>{unanswered}</strong><p>Opportunities for a new huddle</p></div>
      </div>
      <div className="graph-columns">
        <section className="chart-panel">
          <div className="section-label"><div><span className="eyebrow">THE QUESTION LANDSCAPE</span><h2>What’s coming up most?</h2></div><span className="small muted">{isLive ? "Synthetic demo analytics · 30 days" : "Synthetic demo snapshot"}</span></div>
          <div className="chart" role="img" aria-label={`Clinical topics: ${data.map((d) => `${d.topic}: ${d.count}`).join(", ")}`}>
            <ResponsiveContainer width="100%" height="100%"><BarChart data={data} layout="vertical" margin={{ left: 0, right: 25, top: 15, bottom: 0 }} barSize={24}>
              <CartesianGrid horizontal={false} stroke="#e7ebe9" /><XAxis type="number" axisLine={false} tickLine={false} allowDecimals={false} tick={{ fontSize: 12, fill: "#75817d" }} /><YAxis type="category" dataKey="topic" width={156} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#334c45" }} /><Tooltip cursor={{ fill: "#f0f5f2" }} contentStyle={{ borderRadius: 10, border: "1px solid #dce5e0" }} /><Bar dataKey="count" name="Questions" fill="#24796a" radius={[0, 4, 4, 0]} isAnimationActive={false} />
            </BarChart></ResponsiveContainer>
          </div>
          <details className="data-table"><summary>View accessible data table</summary><table><thead><tr><th>Topic</th><th>Questions</th></tr></thead><tbody>{data.map((d) => <tr key={d.topic}><td>{d.topic}</td><td>{d.count}</td></tr>)}</tbody></table></details>
        </section>
        <aside className="insights-panel">
          <span className="eyebrow">SIGNALS WORTH EXPLORING</span>
          <div className="insight"><TrendingUp size={19} /><h3>Emerging questions</h3><p>{isLive ? analytics?.emerging[0]?.topic || "No emerging topic signal in this period." : "How should teams frame conversations about new evidence?"}</p><span className="tiny-tag">{isLive ? "DEMO CATEGORY SIGNAL" : <>ILLUSTRATIVE TREND <ArrowUpRight size={12} /></>}</span></div>
          <div className="insight"><CircleHelp size={19} /><h3>Unanswered questions</h3><p>{isLive ? analytics?.unanswered[0]?.topic || "No unanswered topic signal in this period." : "What support do clinicians need when trial eligibility is unclear?"}</p><span className="tiny-tag">{isLive ? "CATEGORY SIGNAL" : "DEMO EVIDENCE GAP"}</span></div>
          <div className="specialty-distribution"><h3>Specialty distribution</h3>{specialties.map((s) => {
            const share = total ? Math.round((s.count / total) * 100) : 0;
            return <div key={s.name}><div className="flex justify-between small"><span>{s.name}</span><span>{isLive ? `${share}% (${s.count})` : `${s.count}%`}</span></div><div className="distribution-track"><span style={{ width: `${isLive ? share : s.count}%` }} /></div></div>;
          })}</div>
        </aside>
      </div>
      <div className="graph-note"><span className="signal-dot" />Every good question reveals where a better conversation is needed.</div>
    </div>
  );
}
