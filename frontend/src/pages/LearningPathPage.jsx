import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Background, Controls, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { addPathLink, decidePathLink, fetchTopicLearningPath } from "../api";

// Everything in one depth layer is a peer: nothing in it depends on anything
// else in it, so the layer is what the ordering actually asserts. Exported so
// the grouping can be checked without rendering.
export function groupStepsByDepth(steps) {
  const byDepth = new Map();
  for (const step of steps) {
    const depth = step.dag_depth ?? 0;
    if (!byDepth.has(depth)) byDepth.set(depth, []);
    byDepth.get(depth).push(step);
  }
  return [...byDepth.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([depth, layerSteps]) => ({ depth, steps: layerSteps }));
}

// A step nothing depends on and that depends on nothing is not part of the
// graph at all. It still gets taught, but its position is document order rather
// than anything the criteria found -- which is the first thing to look at when
// a path looks wrong.
export function findFloatingSteps(steps) {
  const depended = new Set();
  for (const step of steps) {
    for (const id of step.prerequisite_ids || []) depended.add(id);
  }
  return steps
    .filter(
      (step) =>
        (step.prerequisite_count || 0) === 0 &&
        !depended.has(step.learning_object_id),
    )
    .map((step) => step.learning_object_id);
}

// Depth decides the column, so arrows read left to right and every node in a
// column is a peer. Laying out by depth rather than letting the library find a
// layout is what keeps a dense graph interpretable at all.
export function buildFlowLayout(steps, edges) {
  const byDepth = new Map();
  for (const step of steps) {
    const depth = step.dag_depth ?? 0;
    if (!byDepth.has(depth)) byDepth.set(depth, []);
    byDepth.get(depth).push(step);
  }

  const nodes = [];
  for (const [depth, layerSteps] of byDepth) {
    layerSteps.forEach((step, index) => {
      nodes.push({
        id: String(step.learning_object_id),
        position: { x: depth * 260, y: index * 86 },
        data: { label: `${step.position}. ${step.title || "Untitled"}` },
        style: {
          width: 210,
          fontSize: 12,
          padding: 6,
          borderRadius: 8,
          border: "1px solid #cbd3e1",
          background: (step.prerequisite_count || 0) === 0 ? "#fdfaf3" : "#ffffff",
        },
      });
    });
  }

  const flowEdges = edges.map((edge, index) => ({
    id: String(edge.id ?? `e${index}`),
    source: String(edge.prerequisite_id),
    target: String(edge.dependent_id),
    animated: false,
    style: { strokeWidth: Math.max(1, (edge.weight || 0.25) * 3) },
  }));

  return { nodes, edges: flowEdges };
}

function PathGraph({ steps, edges }) {
  const layout = useMemo(() => buildFlowLayout(steps, edges), [steps, edges]);

  if (!steps.length) {
    return <p className="muted-text">Nothing to draw yet.</p>;
  }

  return (
    <div className="path-graph">
      <ReactFlow
        nodes={layout.nodes}
        edges={layout.edges}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: false }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
      <small className="muted-text">
        Columns are depth layers. Thicker arrows carried more criteria. Drag to pan, scroll to
        zoom.
      </small>
    </div>
  );
}

// A teacher's controls for one step's prerequisites. Changes are saved at once
// and the preview re-orders, but students keep the published path until the
// topic is published again.
function PrerequisiteEditor({ step, concepts, busy, onAdd, onDecide }) {
  const current = step.prerequisites || [];
  const suggestions = step.suggestions || [];
  const taken = new Set([step.concept_id, ...current.map((link) => link.concept_id)]);
  const choices = concepts.filter((concept) => !taken.has(concept.concept_id));

  return (
    <div className="path-link-editor">
      <div className="path-link-row">
        <span className="path-link-label">Needs first:</span>
        {current.length === 0 && <span className="muted-text">nothing</span>}
        {current.map((link) => (
          <span className="path-link-chip" key={link.link_id}>
            {link.title}
            <button
              type="button"
              disabled={busy}
              aria-label={`Remove ${link.title} as a prerequisite of ${step.title}`}
              title="Remove. It won't be suggested again."
              onClick={() => {
                if (window.confirm(`Remove “${link.title}” as a prerequisite of “${step.title}”? It won't be suggested again.`)) {
                  onDecide(link.link_id, "rejected");
                }
              }}
            >
              ×
            </button>
          </span>
        ))}
        <label className="path-link-add">
          <span className="sr-only">Add a prerequisite for {step.title}</span>
          <select
            id={`add-prerequisite-${step.concept_id}`}
            value=""
            disabled={busy || choices.length === 0}
            onChange={(event) => {
              if (event.target.value) onAdd(Number(event.target.value), step.concept_id);
            }}
          >
            <option value="">+ Add a prerequisite…</option>
            {choices.map((concept) => (
              <option key={concept.concept_id} value={concept.concept_id}>
                {concept.position}. {concept.title}
              </option>
            ))}
          </select>
        </label>
      </div>
      {suggestions.length > 0 && (
        <details className="path-link-suggestions">
          <summary>Suggestions ({suggestions.length})</summary>
          <ul>
            {suggestions.map((link) => (
              <li key={link.link_id}>
                <span>
                  {link.title}
                  {link.cross_section && <small className="muted-text"> · different section</small>}
                </span>
                <span className="path-link-actions">
                  <button type="button" className="btn btn-small btn-primary" disabled={busy} onClick={() => onDecide(link.link_id, "approved")}>
                    Approve
                  </button>
                  <button type="button" className="btn btn-small btn-secondary" disabled={busy} onClick={() => onDecide(link.link_id, "rejected")}>
                    Reject
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function PathStep({ step, titleById, floating, showText, editor }) {
  const prerequisites = step.prerequisites
    ? step.prerequisites.map((link) => link.title)
    : (step.prerequisite_ids || []).map((id) => titleById.get(id)).filter(Boolean);
  const moved = step.position - 1 !== step.source_order;

  return (
    <li className={`path-step ${floating ? "is-floating" : ""}`.trim()}>
      <span className="path-step-position">{step.position}</span>
      <div className="path-step-body">
        <div className="path-step-head">
          <strong>{step.title || "Untitled"}</strong>
          {step.kind === "image" && <span className="path-chip is-image">Figure</span>}
          {floating && (
            <span className="path-chip is-floating" title="No prerequisites and nothing depends on it">
              Not connected
            </span>
          )}
          {moved && (
            <span className="path-chip is-moved" title="The graph moved this away from its position in the PDF">
              Reordered from #{step.source_order + 1}
            </span>
          )}
        </div>
        {step.section_title && <small className="path-step-section">{step.section_title}</small>}
        {step.content && (
          <details className="path-step-content" open={showText}>
            <summary>Show passage</summary>
            <p>{step.content}</p>
          </details>
        )}
        {editor}
        <div className="path-step-meta">
          {editor ? null : prerequisites.length > 0 ? (
            <span>
              After: <em>{prerequisites.join(", ")}</em>
            </span>
          ) : (
            <span className="muted-text">No prerequisites</span>
          )}
          {step.support_confidence != null && (
            <span className="muted-text">confidence {step.support_confidence}</span>
          )}
          {step.source_count > 1 && (
            <span className="muted-text" title="Uploaded files that teach this concept">
              from {step.source_count} sources
            </span>
          )}
        </div>
      </div>
    </li>
  );
}

// Exported so the topic review flow can show the same path display inline as
// its own step, rather than keeping a second copy in sync with this one.
export function MaterialPath({ path, topicId = null, editable = false, onPathData = null }) {
  const [view, setView] = useState("list");
  const [showText, setShowText] = useState(false);
  const [linkBusy, setLinkBusy] = useState(false);
  const [linkError, setLinkError] = useState("");
  const conceptChoices = useMemo(
    () => (path.steps || []).map((step) => ({
      concept_id: step.concept_id, title: step.title, position: step.position,
    })),
    [path.steps],
  );

  async function changeLinks(action) {
    setLinkBusy(true);
    setLinkError("");
    try {
      const data = await action();
      if (onPathData) onPathData(data);
    } catch (error) {
      setLinkError(error.message);
    } finally {
      setLinkBusy(false);
    }
  }

  const editorFor = (step) => (editable && topicId ? (
    <PrerequisiteEditor
      step={step}
      concepts={conceptChoices}
      busy={linkBusy}
      onAdd={(prerequisiteId, dependentId) => changeLinks(() => addPathLink(topicId, prerequisiteId, dependentId))}
      onDecide={(linkId, status) => changeLinks(() => decidePathLink(topicId, linkId, status))}
    />
  ) : null);
  const steps = path.steps || [];
  const titleById = useMemo(
    () => new Map(steps.map((step) => [step.learning_object_id, step.title])),
    [steps],
  );
  const layers = useMemo(() => groupStepsByDepth(steps), [steps]);
  const edges = path.edges || [];
  // No prerequisites have been derived, so the sequence is the one the teacher's
  // own materials present. Every dependency-flavoured signal below would be a
  // falsehood in this mode: with no edges, *every* step reads as "not
  // connected", every position looks unmoved by a graph that never ran, and
  // confidence describes support that does not exist.
  const documentOrder = path.diagnostics?.ordering === "document_order";
  const floating = useMemo(
    () => (documentOrder ? new Set() : new Set(findFloatingSteps(steps))),
    [steps, documentOrder],
  );

  return (
    <section className="path-material">
      <header className="path-material-head">
        <h3>{path.material_title || path.topic_title || "Untitled lesson file"}</h3>
        <div className="path-material-stats">
          <span>{steps.length} {documentOrder ? "concepts" : "steps"}</span>
          {documentOrder ? (
            <>
              <span>{path.diagnostics?.material_count ?? 0} lesson files</span>
              <span title="Concepts taught by more than one of the uploaded files.">
                {path.diagnostics?.multi_source_concept_count ?? 0} shared across files
              </span>
            </>
          ) : (
            <>
              <span>{edges.length} edges</span>
              <span>{layers.length} layers</span>
              {floating.size > 0 && (
                <span className="is-warning">{floating.size} not connected</span>
              )}
              {path.diagnostics && (
                <span
                  title="The graph decides what must precede what; the author breaks the ties it leaves open."
                >
                  {path.diagnostics.displaced_object_count === 0
                    ? "matches the PDF order"
                    : `${path.diagnostics.displaced_object_count} moved by the graph`}
                </span>
              )}
            </>
          )}
        </div>
        <div className="path-view-toggle" role="group" aria-label="View">
          <button
            type="button"
            className={`btn btn-small ${showText ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setShowText((current) => !current)}
          >
            {showText ? "Hide passages" : "Show passages"}
          </button>
          <button
            type="button"
            className={`btn btn-small ${view === "list" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setView("list")}
          >
            List
          </button>
          {/* Kept visible but disabled while there is nothing to draw. Hiding it
              reads as broken; saying why does not. */}
          <button
            type="button"
            className={`btn btn-small ${view === "graph" ? "btn-primary" : "btn-secondary"}`}
            disabled={documentOrder}
            title={
              documentOrder
                ? `The graph draws prerequisite arrows. None are derived yet, so it would be ${steps.length} unconnected boxes.`
                : undefined
            }
            onClick={() => setView("graph")}
          >
            Graph
          </button>
        </div>
      </header>

      {documentOrder && (
        <p className="muted-text path-ordering-note">
          Ordered as your lesson files present it. No prerequisites are set yet, so no
          step depends on another{editable ? " — add one on any step below" : ""}.
        </p>
      )}

      {editable && path.diagnostics?.changed_since_publish && (
        <p className="path-changed-note" role="status">
          You changed prerequisites after the last publish. Students still follow the
          published path until you publish again.
        </p>
      )}

      {linkError && <p className="path-link-error" role="alert">{linkError}</p>}

      {view === "graph" && <PathGraph steps={steps} edges={edges} />}

      {view === "list" && !steps.length ? (
        <p className="muted-text">This topic has no teaching steps yet.</p>
      ) : view === "list" ? (
        layers.map(({ depth, steps: layerSteps }) => (
          <div className="path-layer" key={depth}>
            <div className="path-layer-head">
              <span className="path-layer-label">Layer {depth}</span>
              <small>
                {depth === 0
                  ? "taught first — depends on nothing"
                  : `after ${depth} level${depth === 1 ? "" : "s"} of prerequisites`}
              </small>
            </div>
            <ol className="path-step-list">
              {layerSteps.map((step) => (
                <PathStep
                  key={step.learning_object_id}
                  step={step}
                  titleById={titleById}
                  floating={floating.has(step.learning_object_id)}
                  showText={showText}
                  editor={editorFor(step)}
                />
              ))}
            </ol>
          </div>
        ))
      ) : null}

      {edges.length > 0 && (
        <details className="path-edge-log">
          <summary>Why these edges exist ({edges.length})</summary>
          <ul>
            {edges.map((edge) => {
              const voted = edge.evidence?.voted_forward;
              const criteria = voted ? Object.keys(voted) : [];
              return (
                <li key={edge.id ?? `${edge.prerequisite_id}-${edge.dependent_id}`}>
                  <strong>{edge.prerequisite_title}</strong> → {edge.dependent_title}
                  <small>
                    {" "}
                    {criteria.length ? criteria.join(", ") : edge.signal_label}
                    {edge.weight != null && ` · ${edge.weight}`}
                  </small>
                </li>
              );
            })}
          </ul>
        </details>
      )}
    </section>
  );
}

export default function LearningPathPage() {
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
    <div className="learning-path-page">
      <div className="learning-path-heading">
        <div>
          <span className="connection-eyebrow">Learning path</span>
          <h2>{data?.topic?.title || "Learning path"}</h2>
          <p className="muted-text">
            One path for the whole topic. Each step is a concept, assembled from every
            uploaded file that teaches it.
          </p>
        </div>
        <div className="learning-path-actions">
          <button type="button" className="btn btn-secondary" disabled={loading} onClick={load}>
            {loading ? "Loading..." : "Refresh"}
          </button>
          <Link className="btn btn-secondary" to={`/courses/${courseId}/topics/${topicId}`}>
            Back to topic
          </Link>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading && !data && <p className="muted-text">Deriving the path…</p>}

      {data?.problems?.length > 0 && (
        <div className="alert alert-error">
          <strong>Some lesson files have no usable order.</strong>
          <ul>
            {data.problems.map((problem) => (
              <li key={problem.material_id}>
                {problem.material_title}: {problem.detail}
              </li>
            ))}
          </ul>
        </div>
      )}

      {data?.paths?.length === 0 && !loading && (
        <p className="muted-text">
          No path yet. Each step is a concept, so confirm the learning objects in
          your lesson files first — grouping is what turns them into concepts.
        </p>
      )}

      {(data?.paths || []).map((path) => (
        <MaterialPath key={path.material_id} path={path} />
      ))}
    </div>
  );
}
