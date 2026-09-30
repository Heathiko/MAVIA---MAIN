// Pure helpers behind the Course path page: where topics sit and how each
// arrow between them is drawn. Nothing here renders or calls the server.
export const TOPIC_WIDTH = 220;
export const TOPIC_HEIGHT = 60;
const COLUMNS = 4;
const COLUMN_STEP = TOPIC_WIDTH + 80;
const ROW_STEP = TOPIC_HEIGHT + 90;
const MARGIN = 20;

// "contradicts" first: a teacher must see an arrow against the outline even
// when it also carries accepted links.
export function arrowKind(arrow) {
  if (arrow.contradicts_outline) return "contradicts";
  if (!arrow.shaping) return "pending";
  return "follows";
}

function arrowLabel(arrow) {
  if (arrow.shaping) return `${arrow.shaping} link${arrow.shaping === 1 ? "" : "s"}`;
  return `${arrow.pending} suggestion${arrow.pending === 1 ? "" : "s"}`;
}

const COLOURS = { follows: "#2f6f4f", pending: "#b8860b", contradicts: "#b3261e" };

export function buildCourseGraph(path, selectedArrow = null) {
  const topics = [...path.topics].sort((a, b) => a.position - b.position);
  const nodes = topics.map((topic, index) => ({
    id: String(topic.id),
    type: "topic",
    position: { x: MARGIN + (index % COLUMNS) * COLUMN_STEP, y: MARGIN + Math.floor(index / COLUMNS) * ROW_STEP },
    data: { topic, empty: !topic.has_content },
    draggable: false,
  }));
  const edges = path.arrows.map((arrow) => {
    const kind = arrowKind(arrow);
    const id = `${arrow.from_topic}-${arrow.to_topic}`;
    return {
      id,
      source: String(arrow.from_topic),
      target: String(arrow.to_topic),
      label: arrowLabel(arrow),
      className: `cp-arrow ${kind}${selectedArrow === id ? " selected" : ""}`,
      markerEnd: { type: "arrowclosed", width: 18, height: 18, color: COLOURS[kind] },
      style: { stroke: COLOURS[kind], strokeWidth: selectedArrow === id ? 3 : 1.5, strokeDasharray: kind === "follows" ? undefined : "6 4" },
      data: { arrow },
    };
  });
  return { nodes, edges };
}
