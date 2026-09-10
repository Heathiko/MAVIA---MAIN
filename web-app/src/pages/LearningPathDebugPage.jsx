import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { fetchTopicLearningPath } from "../api";

// --- pure helpers, exported for quick checks -------------------------------

export function findFloatingSteps(steps) {
  const depended = new Set();
  for (const step of steps) {
    for (const id of step.prerequisite_ids || []) depended.add(id);
  }
  return new Set(
    steps
      .filter(
        (s) =>
          (s.prerequisite_count || 0) === 0 &&
          !depended.has(s.learning_object_id),
      )
      .map((s) => s.learning_object_id),
  );
}

const COL_W = 250;
const ROW_H = 66;
const NODE_W = 200;
const NODE_H = 44;

// Column = depth layer (arrows read left to right). Row = arrival order within
// the layer. Laying it out by hand keeps a dense graph readable.
export function layoutGraph(steps, edges) {
  const byDepth = new Map();
  for (const step of steps) {
    const d = step.dag_depth ?? 0;
    if (!byDepth.has(d)) byDepth.set(d, []);
    byDepth.get(d).push(step);
  }
  const pos = new Map();
  let maxRow = 0;
  for (const [depth, layer] of byDepth) {
    layer.forEach((step, i) => {
      pos.set(step.learning_object_id, {
        x: depth * COL_W + 20,
        y: i * ROW_H + 20,
        step,
      });
      maxRow = Math.max(maxRow, i);
    });
  }
  const width = (Math.max(0, ...[...byDepth.keys()]) + 1) * COL_W + 40;
  const height = (maxRow + 1) * ROW_H + 40;
  const links = edges
    .map((e) => {
      const a = pos.get(e.prerequisite_id);
      const b = pos.get(e.dependent_id);
      if (!a || !b) return null;
      return { edge: e, a, b, backward: b.x <= a.x };
    })
    .filter(Boolean);
  return { pos, links, width, height };
}

function edgeColor(edge) {
  if (edge.signal === "chunk_continuation") return "#9aa5b1";
  const tier = edge.evidence?.tier;
  if (edge.source === "teacher") return "#7c3aed";
  return tier === "strong" ? "#334155" : "#8aa0c6";
}

// --- graph view ----------------------------------------------------------

function Graph({ steps, edges, floating }) {
  const { pos, links, width, height } = useMemo(
    () => layoutGraph(steps, edges),
    [steps, edges],
  );
  const [view, setView] = useState({ tx: 0, ty: 0, k: 1 });
  const drag = useRef(null);

  const onWheel = (e) => {
    e.preventDefault();
    setView((v) => {
      const k = Math.min(2.5, Math.max(0.2, v.k * (e.deltaY < 0 ? 1.1 : 0.9)));
      return { ...v, k };
    });
  };
  const onDown = (e) => {
    drag.current = { x: e.clientX, y: e.clientY, tx: view.tx, ty: view.ty };
  };
  const onMove = (e) => {
    if (!drag.current) return;
    setView((v) => ({
      ...v,
      tx: drag.current.tx + (e.clientX - drag.current.x),
      ty: drag.current.ty + (e.clientY - drag.current.y),
    }));
  };
  const onUp = () => {
    drag.current = null;
  };

  if (!steps.length) return <p className="lp-muted">Nothing to draw.</p>;

  return (
    <div
      className="lp-graph"
      onWheel={onWheel}
      onMouseDown={onDown}
      onMouseMove={onMove}
      onMouseUp={onUp}
      onMouseLeave={onUp}
    >
      <svg width="100%" height="520" role="img" aria-label="Prerequisite graph">
        <g transform={`translate(${view.tx} ${view.ty}) scale(${view.k})`}>
          {links.map(({ edge, a, b, backward }, i) => {
            const x1 = a.x + NODE_W;
            const y1 = a.y + NODE_H / 2;
            const x2 = b.x;
            const y2 = b.y + NODE_H / 2;
            const mx = (x1 + x2) / 2;
            const d = backward
              ? `M${x1},${y1} C${x1 + 60},${y1 - 40} ${x2 - 60},${y2 - 40} ${x2},${y2}`
              : `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
            return (
              <path
                key={edge.id ?? i}
                d={d}
                fill="none"
                stroke={edgeColor(edge)}
                strokeWidth={Math.max(1, (edge.weight || 0.5) * 2.5)}
                strokeDasharray={backward ? "4 3" : undefined}
                opacity={0.7}
              />
            );
          })}
          {[...pos.values()].map(({ x, y, step }) => {
            const isRoot = (step.prerequisite_count || 0) === 0;
            const isFloating = floating.has(step.learning_object_id);
            return (
              <g key={step.learning_object_id} transform={`translate(${x} ${y})`}>
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx="7"
                  fill={isFloating ? "#fff4e5" : isRoot ? "#eef6ff" : "#ffffff"}
                  stroke={
                    isFloating ? "#e08a00" : isRoot ? "#3b82f6" : "#cbd3e1"
                  }
                />
                <text x="9" y="17" fontSize="11" fontWeight="600" fill="#1f2933">
                  {step.position}. {(step.title || "Untitled").slice(0, 26)}
                </text>
                <text x="9" y="33" fontSize="10" fill="#6b7280">
                  depth {step.dag_depth} · {step.prerequisite_count} prereq
                  {step.kind === "image" ? " · fig" : ""}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      <small className="lp-muted">
        Columns = depth layers. Dashed = runs against document order. Drag to pan,
        scroll to zoom. Reset:{" "}
        <button
          type="button"
          className="lp-linkbtn"
          onClick={() => setView({ tx: 0, ty: 0, k: 1 })}
        >
          recenter
        </button>
      </small>
    </div>
  );
}

// --- one material ------------------------------------------------------------

function MaterialPath({ path }) {
  const [tab, setTab] = useState("graph");
  const steps = path.steps || [];
  const edges = path.edges || [];
  const floating = useMemo(() => findFloatingSteps(steps), [steps]);
  const titleById = useMemo(
    () => new Map(steps.map((s) => [s.learning_object_id, s.title])),
    [steps],
  );
  const d = path.diagnostics || {};

  return (
    <section className="lp-material">
      <header className="lp-mat-head">
        <h3>{path.material_title || "Untitled lesson file"}</h3>
        <div className="lp-stats">
          <span>{d.node_count ?? steps.length} nodes</span>
          <span>{d.edge_count ?? edges.length} edges</span>
          <span>
            {(edges.length / Math.max(1, steps.length)).toFixed(1)}/node
          </span>
          <span>{d.root_count ?? "?"} roots</span>
          <span>depth {d.max_depth ?? "?"}</span>
          {floating.size > 0 && (
            <span className="lp-warn">{floating.size} not connected</span>
          )}
          <span>
            {d.matches_source_order
              ? "matches PDF order"
              : `${d.displaced_object_count ?? "?"} moved by the graph`}
          </span>
        </div>
        <div className="lp-tabs">
          {["graph", "list", "edges"].map((t) => (
            <button
              key={t}
              type="button"
              className={tab === t ? "is-active" : ""}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </header>

      {tab === "graph" && (
        <Graph steps={steps} edges={edges} floating={floating} />
      )}

      {tab === "list" && (
        <ol className="lp-list">
          {steps.map((s) => (
            <li
              key={s.learning_object_id}
              className={floating.has(s.learning_object_id) ? "is-floating" : ""}
            >
              <span className="lp-pos">{s.position}</span>
              <div>
                <strong>{s.title || "Untitled"}</strong>{" "}
                {s.kind === "image" && <span className="lp-chip">figure</span>}
                {floating.has(s.learning_object_id) && (
                  <span className="lp-chip lp-chip-warn">not connected</span>
                )}
                {s.position - 1 !== s.source_order && (
                  <span className="lp-chip">from #{s.source_order + 1}</span>
                )}
                <div className="lp-muted">
                  depth {s.dag_depth} · confidence {s.support_confidence} ·{" "}
                  {(s.prerequisite_ids || [])
                    .map((id) => titleById.get(id))
                    .filter(Boolean)
                    .join(", ") || "no prerequisites"}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}

      {tab === "edges" && (
        <ul className="lp-edges">
          {edges.map((e, i) => (
            <li key={e.id ?? i}>
              <strong>{e.prerequisite_title}</strong> → {e.dependent_title}
              <span className="lp-muted">
                {" "}
                {e.signal_label || e.signal}
                {e.evidence?.strong?.length
                  ? ` · ${e.evidence.strong.join(", ")}`
                  : e.evidence?.medium?.length
                    ? ` · ${e.evidence.medium.join(", ")}`
                    : ""}
                {e.weight != null && ` · w${e.weight}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// --- page ------------------------------------------------------------------

const STYLES = `
.lp-debug{padding:24px;max-width:1100px;margin:0 auto}
.lp-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:16px}
.lp-head h2{margin:.2em 0}
.lp-eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280}
.lp-muted{color:#6b7280;font-size:12px}
.lp-linkbtn{background:none;border:none;color:#2563eb;cursor:pointer;font:inherit;padding:0;text-decoration:underline}
.lp-material{border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin-bottom:18px;background:#fff}
.lp-mat-head h3{margin:0 0 6px}
.lp-stats{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:#374151;margin-bottom:10px}
.lp-warn{color:#b45309;font-weight:600}
.lp-tabs{display:flex;gap:6px;margin-bottom:10px}
.lp-tabs button{border:1px solid #cbd5e1;background:#f8fafc;border-radius:6px;padding:3px 12px;font-size:12px;cursor:pointer;text-transform:capitalize}
.lp-tabs button.is-active{background:#2563eb;color:#fff;border-color:#2563eb}
.lp-graph{position:relative;border:1px solid #eef2f7;border-radius:8px;overflow:hidden;background:#fafcff;cursor:grab}
.lp-graph:active{cursor:grabbing}
.lp-list{list-style:none;padding:0;margin:0}
.lp-list li{display:flex;gap:10px;padding:8px 6px;border-bottom:1px solid #f1f5f9}
.lp-list li.is-floating{background:#fff8ef}
.lp-pos{flex:0 0 24px;height:24px;border-radius:50%;background:#eef2ff;color:#3730a3;font-size:12px;font-weight:700;display:grid;place-items:center}
.lp-chip{display:inline-block;font-size:10px;background:#eef2f7;border-radius:4px;padding:1px 6px;margin-left:4px;color:#475569}
.lp-chip-warn{background:#fde9d3;color:#9a3412}
.lp-edges{font-size:13px;line-height:1.7;padding-left:18px}
`;

export default function LearningPathDebugPage() {
  const { courseId, topicId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await fetchTopicLearningPath(topicId));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [topicId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="app-shell">
      <style>{STYLES}</style>
      <div className="lp-debug">
        <div className="lp-head">
          <div>
            <span className="lp-eyebrow">Debug · prerequisite DAG</span>
            <h2>{data?.topic?.title || "Learning path"}</h2>
            <p className="lp-muted">
              Derived teaching order per lesson file, grouped by prerequisite
              depth. Read-only.
            </p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className="lp-tabs"
              onClick={load}
              disabled={loading}
              style={{
                border: "1px solid #cbd5e1",
                borderRadius: 6,
                padding: "4px 12px",
                background: "#f8fafc",
                cursor: "pointer",
              }}
            >
              {loading ? "Loading…" : "Refresh"}
            </button>
            <Link
              to={`/courses/${courseId}/topics/${topicId}`}
              style={{ alignSelf: "center" }}
            >
              Back to topic
            </Link>
          </div>
        </div>

        {error && (
          <div style={{ color: "#b91c1c", marginBottom: 12 }}>{error}</div>
        )}
        {loading && !data && <p className="lp-muted">Deriving the path…</p>}

        {data?.problems?.map((p) => (
          <div key={p.material_id} style={{ color: "#b91c1c", marginBottom: 12 }}>
            <strong>{p.material_title}:</strong> {p.detail}
          </div>
        ))}

        {data?.paths?.length === 0 && !loading && (
          <p className="lp-muted">No completed lesson files in this topic yet.</p>
        )}

        {(data?.paths || []).map((path) => (
          <MaterialPath key={path.material_id} path={path} />
        ))}
      </div>
    </div>
  );
}
