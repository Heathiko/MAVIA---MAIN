import { describe, expect, it } from "vitest";

import { contentGaps, tierCounts } from "./TopicDetailPage";

const question = (thinking_order, extra = {}) => ({ thinking_order, source_type: "generated", bloom_level: "x", ...extra });
const concept = (questions) => ({
  versions: { representative_id: 1, slots: { simplified: {}, elaborated: {} } },
  questions,
});
// Exactly the minimum: 4 LOTS and 2 HOTS.
const full = [...Array(4)].map(() => question("LOT")).concat([...Array(2)].map(() => question("HOT")));

describe("question minimum per concept", () => {
  it("counts LOTS and HOTS from every source", () => {
    expect(tierCounts([question("LOT"), question("HOT", { source_type: "pdf" }), question("")])).toEqual({ LOT: 1, HOT: 1 });
  });

  it("is ready only when every concept has 4 LOTS and 2 HOTS", () => {
    expect(contentGaps([concept(full)]).ready).toBe(true);
    const short = contentGaps([concept(full), concept(full.slice(1))]);
    expect(short.shortQuestions).toBe(1);
    expect(short.ready).toBe(false);
  });

  it("a create question does not count toward either tier", () => {
    // One LOTS short, topped up with a "create" question that has no tier.
    const withCreate = [...full.slice(1), question("", { bloom_level: "create" })];
    expect(contentGaps([concept(withCreate)]).shortQuestions).toBe(1);
  });
});
