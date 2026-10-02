// One arrow of the Course path, opened as a dialog: every concept link it
// carries, confirmed ones first and suggestions by shortlist rank, each with
// its reason and the teacher's buttons. Nothing here changes links itself;
// decisions go back up to the page, which confirms them.
import { useEffect } from "react";

const STATUS_LABEL = { accepted: "Accepted", approved: "Approved", pending: "Suggestion" };
const byRank = (a, b) => (a.rank ?? Infinity) - (b.rank ?? Infinity) || a.id - b.id;

function Concept({ concept, topicTitle }) {
  return (
    <div className="cad-concept">
      <span className="cad-concept-title">{concept.title}</span>
      <span className="cad-concept-topic">{topicTitle(concept.topic_id)}</span>
    </div>
  );
}

function LinkCard({ link, topicTitle, onDecide }) {
  const pending = link.status === "pending";
  const pair = `${link.prerequisite.title} before ${link.dependent.title}`;
  return (
    <li className={`cad-card ${link.status}`}>
      <div className="cad-card-head">
        <span className={`cad-badge ${link.status}`}>{STATUS_LABEL[link.status] || link.status}</span>
        {pending && link.rank && <span className="cad-rank">Closest match #{link.rank}</span>}
      </div>
      <div className="cad-pair">
        <Concept concept={link.prerequisite} topicTitle={topicTitle} />
        <span className="cad-pair-arrow" aria-hidden="true">→</span>
        <Concept concept={link.dependent} topicTitle={topicTitle} />
      </div>
      {link.reason && <p className="cad-reason">{link.reason}</p>}
      <div className="cad-actions">
        {pending && (
          <button type="button" className="btn btn-small btn-primary" aria-label={`Approve ${pair}`}
                  onClick={() => onDecide(link, "approved")}>
            Approve
          </button>
        )}
        <button type="button" className="btn btn-small btn-secondary" aria-label={`${pending ? "Dismiss" : "Remove"} ${pair}`}
                onClick={() => onDecide(link, "rejected")}>
          {pending ? "Dismiss" : "Remove"}
        </button>
      </div>
    </li>
  );
}

export default function CourseArrowDialog({ arrow, topicTitle, onDecide, onClose, paused = false }) {
  useEffect(() => {
    // While a confirm dialog sits on top, Escape belongs to it.
    const onKey = (event) => event.key === "Escape" && !paused && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [paused, onClose]);

  const from = topicTitle(arrow.from_topic);
  const to = topicTitle(arrow.to_topic);
  const confirmed = arrow.links.filter((link) => link.status !== "pending").sort(byRank);
  const suggestions = arrow.links.filter((link) => link.status === "pending").sort(byRank);

  return (
    <div className="pg-dialog-backdrop cad-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !paused && onClose()}>
      <section className="cad-dialog" role="dialog" aria-modal="true" aria-labelledby="cad-title">
        <header className="cad-head">
          <div className="cad-head-text">
            <p className="cad-eyebrow">Links between topics</p>
            <h3 id="cad-title">
              <span>{from}</span>
              <span className="cad-head-arrow" aria-label="builds into">→</span>
              <span>{to}</span>
            </h3>
            <p className="cad-summary">
              {confirmed.length} confirmed · {suggestions.length} to review
            </p>
          </div>
          <button type="button" className="cad-close" aria-label="Close" onClick={onClose}>×</button>
        </header>
        {arrow.contradicts_outline && (
          <p className="cad-warning" role="note">
            These links run against your outline. To follow them, move “{from}” before “{to}” in the outline.
          </p>
        )}
        <div className="cad-body">
          {confirmed.length > 0 && (
            <section className="cad-group" aria-label="Confirmed links">
              <h4>Confirmed <span className="cad-count">{confirmed.length}</span></h4>
              <ul className="cad-grid">
                {confirmed.map((link) => <LinkCard key={link.id} link={link} topicTitle={topicTitle} onDecide={onDecide} />)}
              </ul>
            </section>
          )}
          {suggestions.length > 0 && (
            <section className="cad-group" aria-label="Suggestions to review">
              <h4>To review <span className="cad-count">{suggestions.length}</span></h4>
              <ul className="cad-grid">
                {suggestions.map((link) => <LinkCard key={link.id} link={link} topicTitle={topicTitle} onDecide={onDecide} />)}
              </ul>
            </section>
          )}
        </div>
      </section>
    </div>
  );
}
