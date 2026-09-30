import { describe, expect, it } from "vitest";

import { arrowKind, buildCourseGraph } from "./coursePathModel";

const PATH = {
  course: { id: 1, title: "Grade 1 Science" },
  topics: [
    { id: 10, title: "Solid, Liquid and Gas", position: 0, has_content: true },
    { id: 11, title: "Grouping Materials", position: 1, has_content: true },
    { id: 12, title: "Empty topic", position: 2, has_content: false },
  ],
  arrows: [
    { from_topic: 10, to_topic: 11, contradicts_outline: false, shaping: 2, pending: 1, links: [] },
    { from_topic: 11, to_topic: 10, contradicts_outline: true, shaping: 0, pending: 1, links: [] },
  ],
};

describe("arrowKind", () => {
  it("names an arrow by what the teacher must know first", () => {
    expect(arrowKind(PATH.arrows[0])).toBe("follows");
    expect(arrowKind(PATH.arrows[1])).toBe("contradicts");
    expect(arrowKind({ contradicts_outline: false, shaping: 0, pending: 2 })).toBe("pending");
  });
});

describe("buildCourseGraph", () => {
  it("draws every topic in outline order and greys topics without content", () => {
    const graph = buildCourseGraph(PATH);
    expect(graph.nodes.map((node) => node.id)).toEqual(["10", "11", "12"]);
    expect(graph.nodes[2].data.empty).toBe(true);
    expect(graph.nodes[0].position.x).toBeLessThan(graph.nodes[1].position.x);
  });

  it("labels each arrow with its link count", () => {
    const graph = buildCourseGraph(PATH);
    expect(graph.edges.map((edge) => edge.label)).toEqual(["2 links", "1 suggestion"]);
    expect(graph.edges[1].className).toContain("contradicts");
  });
});
