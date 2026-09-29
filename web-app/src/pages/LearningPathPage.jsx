import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { fetchTopicLearningPath } from "../api";
import ConceptDetails from "../learning-path/ConceptDetails";
import PathGraph from "../learning-path/PathGraph";

// Exported so the topic review flow shows the same path display inline as its
// own step, rather than keeping a second copy in sync with this one.
export function MaterialPath({ path, topicId = null, editable = false, onPathData = null }) {
  const steps = path.steps || [];
  const [selectedId, setSelectedId] = useState(null);
  const selected = steps.find((step) => step.concept_id === selectedId) || null;
  const linkCount = steps.reduce((count, step) => count + (step.prerequisites || []).length, 0);
  const clearSelection = useCallback(() => setSelectedId(null), []);

  useEffect(() => {
    if (selectedId !== null && !selected) setSelectedId(null);
  }, [selectedId, selected]);

  return (
    <section className="path-material">
      <header className="path-material-head">
        <h3>{path.topic_title || "Learning path"}</h3>
      </header>

      {linkCount === 0 && steps.length > 0 && (
        <p className="muted-text path-ordering-note">
          Ordered as your lesson files present it. Nothing has to be learned before anything else yet.
        </p>
      )}

      {editable && path.diagnostics?.changed_since_publish && (
        <p className="path-changed-note" role="status">
          You changed what must be learned first after the last publish. Students still follow
          the published path until you publish again.
        </p>
      )}

      <div className="pg-screen is-read-only">
        <div className="pg-graph-area">
          <PathGraph steps={steps} selectedId={selectedId} onSelect={setSelectedId} editable={false} onDrop={() => {}} />
          <ConceptDetails step={selected} onClose={clearSelection} />
        </div>
      </div>
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
        <MaterialPath key={path.topic_id ?? path.material_id} path={path} />
      ))}
    </div>
  );
}
