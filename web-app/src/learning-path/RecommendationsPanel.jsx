// The right-hand quarter: links the lesson files suggest but no rule accepts
// on its own, each with the reason in plain words.
import { recommendations } from "./graphModel";

export default function RecommendationsPanel({ steps, busy, onAccept, onReject }) {
  const items = recommendations(steps);
  return (
    <aside className="pg-panel" aria-labelledby="pg-panel-title">
      <h4 id="pg-panel-title">Recommended links ({items.length})</h4>
      {items.length === 0 ? (
        <p className="muted-text">No recommendations. The links on the graph are everything the lesson files support.</p>
      ) : (
        <ul className="pg-cards">
          {items.map((item) => (
            <li key={item.linkId} className="pg-card">
              <strong>
                {item.fromTitle} → {item.toTitle}
              </strong>
              {item.reason && <p>{item.reason}</p>}
              {item.crossSection && (
                <span
                  className="pg-flag"
                  title="The two concepts are under different lesson headings. In a hand-check, such suggestions were usually wrong."
                >
                  different section
                </span>
              )}
              <div className="pg-card-actions">
                <button type="button" className="btn btn-small btn-primary" disabled={busy} onClick={() => onAccept(item)}>
                  Accept
                </button>
                <button type="button" className="btn btn-small btn-secondary" disabled={busy} onClick={() => onReject(item)}>
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
