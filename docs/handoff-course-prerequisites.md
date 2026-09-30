# Hand-off: `course_prerequisites` in the published learning path

**For:** the owner of the adaptive engine (`backend/adaptive/`).
**From:** the learning path pipeline (`backend/learning_path/`), 2026-09-30.
**Design:** `docs/superpowers/specs/2026-09-30-course-learning-path-design.md` §6.

Nothing in `adaptive/` was changed. This note describes new data the engine can use; whether and
how to use it is your decision.

## What the field is

Every step of the published path — `get_published_path(node)` in
`learning_path/services/published.py`, and `GET /api/learning-path/topics/<id>/published/` — now
carries `course_prerequisites`, next to the existing in-topic `prerequisites`:

```json
"course_prerequisites": [
  {"topic_id": 340, "concept_id": 847, "position": 4, "status": "accepted"}
]
```

It means: *this step's concept builds on concept `concept_id` of an earlier topic `topic_id`*.
`position` is that concept's step position in its own topic's published path. `status` is
`accepted` (the evidence confirmed it and it agrees with the outline) or `approved` (a teacher
confirmed it on the Course path page).

## Guarantees

- **Earlier topics only** — the prerequisite's topic comes before this topic in the course
  outline (unit order, then topic order). A link that contradicts the outline is never listed,
  even when a teacher approved it.
- **Published targets only** — the prerequisite's topic is published and has a saved step at
  `position` for that concept.
- **Never pending or rejected links.**
- **Nearest topic first**, then by position.
- **Changes only when a topic is published again**, like the rest of the published path.
- An empty list when there is nothing — the key is always present.

## Suggested use in `_reroute`

Today `_reroute` tries: (1) the nearest in-topic prerequisite detour, (2) an alternate chunk,
(3) a second pass through the variants, (4) moving on. A natural place for this data is between
(1) and (2):

1. In-topic prerequisite detour (unchanged, still first — closest to what the learner is doing).
2. **If none:** detour to the first `course_prerequisites` entry — switch the learner to
   `topic_id`, step `position`, and serve its first question as a refresher.
3. Alternate chunk, second pass, move on (unchanged).

Things to keep in mind if you do this:

- The remediation-stack frame must also record the **topic** it came from, so
  `_resume_or_advance` returns the learner to the topic and step they left. Today a frame holds
  only a position within the current topic.
- `remediated_positions` ("one detour per step") would need to be keyed by topic as well, since
  positions repeat across topics.
- `MAX_REMEDIATION_DEPTH` should still bound nesting across topics.
- Logging it as the existing `DETOUR_PREREQUISITE` action with the topic in the decision log
  avoids a new action type.

## Example payload

As of 2026-09-30 every list is empty: only topics 340 (Solid, Liquid and Gas) and 357
(Reproduction Among Flowering Plants) have content, and they are unrelated. Once topic 341
(Grouping Materials Based on Properties) is uploaded and published and a link is confirmed, a
step of 341 would carry an entry like the one above pointing at a concept of 340. This section
will be updated with a real payload then.

## Questions

Ask the learning path owner (Jure). The data shape is stable; if you need another field (for
example the prerequisite's title), it can be added without breaking existing readers.
