// The card a teacher reads after clicking a concept: its text, the files it
// came from, and what must be learned before it. It sits over the graph's
// corner without a backdrop, so the highlighted neighbours stay visible.
import { useEffect } from "react";

export default function ConceptDetails({ step, editable = false, onRemove, onClose }) {
  useEffect(() => {
    if (!step) return undefined;
    const onKey = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, onClose]);

  if (!step) return null;
  const prerequisites = step.prerequisites || [];
  const sources = step.source_materials || [];

  return (
    <section className="pg-details" aria-labelledby="pg-details-title">
      <header className="pg-details-head">
        <h3 id="pg-details-title">
          {step.position}. {step.title || "Untitled concept"}
        </h3>
        <button type="button" className="btn btn-small btn-secondary" onClick={onClose}>
          Close
        </button>
      </header>
      {step.content && <p className="pg-details-text">{step.content}</p>}
      {sources.length > 0 && (
        <p className="pg-details-sources">From: {sources.map((source) => source.title).join(", ")}</p>
      )}
      <h4>Must learn first</h4>
      {prerequisites.length === 0 ? (
        <p className="muted-text">Nothing must be learned before this.</p>
      ) : (
        <ul className="pg-details-list">
          {prerequisites.map((link) => (
            <li key={link.link_id}>
              <div>
                <strong>{link.title}</strong>
                {link.reason && <small>{link.reason}</small>}
              </div>
              {editable && (
                <button type="button" className="btn btn-small btn-secondary" onClick={() => onRemove(link, step)}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
