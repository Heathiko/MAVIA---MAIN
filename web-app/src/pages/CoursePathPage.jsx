import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Background, Controls, Handle, Position, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { decideCoursePathLink, fetchCourseLearningPath, restoreCoursePathLinks } from "../api";
import ConfirmDialog from "../learning-path/ConfirmDialog";
import UndoBar from "../learning-path/UndoBar";
import { buildCourseGraph } from "../learning-path/coursePathModel";
import "../learning-path/pathGraph.css";
import "../learning-path/coursePath.css";

function TopicNode({ data }) {
  const { topic, empty } = data;
  return (
    <div className={`cp-topic${empty ? " empty" : ""}`} title={topic.title}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span className="cp-topic-position">{topic.position + 1}</span>
      <span className="cp-topic-title">{topic.title}</span>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

const NODE_TYPES = { topic: TopicNode };

export default function CoursePathPage() {
  const { courseId } = useParams();
  const [path, setPath] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [undo, setUndo] = useState(null);

  useEffect(() => {
    fetchCourseLearningPath(courseId)
      .then(setPath)
      .catch((err) => setError(err.message || "Could not load the course path."));
  }, [courseId]);

  const graph = useMemo(() => (path ? buildCourseGraph(path, selected) : { nodes: [], edges: [] }), [path, selected]);
  const arrow = path?.arrows.find((item) => `${item.from_topic}-${item.to_topic}` === selected) || null;
  const topicTitle = (id) => path?.topics.find((topic) => topic.id === id)?.title || "";

  const decide = useCallback(async (link, status) => {
    setBusy(true);
    try {
      const result = await decideCoursePathLink(courseId, link.id, status);
      setPath(result);
      setConfirm(null);
      setUndo({
        records: result.undo,
        message: `${status === "approved" ? "Approved" : "Removed"}: ${link.prerequisite.title} → ${link.dependent.title}.`,
      });
    } catch (err) {
      setConfirm((current) => current && { ...current, error: err.message || "Could not save." });
    } finally {
      setBusy(false);
    }
  }, [courseId]);

  const handleUndo = useCallback(async () => {
    if (!undo) return;
    setBusy(true);
    try {
      setPath(await restoreCoursePathLinks(courseId, undo.records));
      setUndo(null);
    } catch (err) {
      setUndo((current) => current && { ...current, error: err.message || "Could not undo." });
    } finally {
      setBusy(false);
    }
  }, [courseId, undo]);
  const closeUndo = useCallback(() => setUndo(null), []);

  const ask = (link, status) => setConfirm({
    title: status === "approved" ? "Approve this link?" : "Remove this link?",
    message: `${link.prerequisite.title} (${topicTitle(link.prerequisite.topic_id)}) before ${link.dependent.title} (${topicTitle(link.dependent.topic_id)}).`,
    actions: [{ label: status === "approved" ? "Approve" : "Remove", primary: true, onClick: () => decide(link, status) }],
  });

  if (error) return <div className="error-banner">{error}</div>;
  if (!path) return <p className="muted-text">Loading the course path…</p>;

  return (
    <>
      <section className="card">
        <Link to={`/courses/${courseId}`} style={{ color: "var(--muted)" }}>Back to course</Link>
        <h2>Course path: {path.course.title}</h2>
        <p className="muted-text">
          Topics in your outline order. An arrow means a concept in one topic builds on a concept in another.
          Green follows your outline, yellow is a suggestion, red contradicts your outline.
        </p>
      </section>
      <div className="cp-layout">
        <div className="pg-canvas">
          <ReactFlow
            nodes={graph.nodes}
            edges={graph.edges}
            nodeTypes={NODE_TYPES}
            nodesDraggable={false}
            onEdgeClick={(_, edge) => setSelected(edge.id)}
            onPaneClick={() => setSelected(null)}
            fitView
          >
            <Background />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        {arrow && (
          <section className="pg-details cp-panel" aria-labelledby="cp-panel-title">
            <h3 id="cp-panel-title">{topicTitle(arrow.from_topic)} → {topicTitle(arrow.to_topic)}</h3>
            {arrow.contradicts_outline && (
              <p className="cp-warning">
                To follow these links, move “{topicTitle(arrow.from_topic)}” before “{topicTitle(arrow.to_topic)}” in the outline.
              </p>
            )}
            <ul className="pg-details-list">
              {arrow.links.map((link) => (
                <li key={link.id} className={`cp-link ${link.status}`}>
                  <strong>{link.prerequisite.title} → {link.dependent.title}</strong>
                  <span className="cp-link-status">{link.status}</span>
                  <p>{link.reason}</p>
                  <div className="action-row">
                    {link.status === "pending" && (
                      <button type="button" className="btn btn-small btn-primary" onClick={() => ask(link, "approved")}>Approve</button>
                    )}
                    <button type="button" className="btn btn-small btn-secondary" onClick={() => ask(link, "rejected")}>
                      {link.status === "pending" ? "Reject" : "Remove"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          actions={confirm.actions}
          error={confirm.error}
          busy={busy}
          onCancel={() => setConfirm(null)}
        />
      )}
      {undo && <UndoBar message={undo.message} error={undo.error} busy={busy} onUndo={handleUndo} onClose={closeUndo} />}
    </>
  );
}
