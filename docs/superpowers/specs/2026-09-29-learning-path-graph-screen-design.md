# Learning path review screen: graph-first with drag-and-drop editing

Date: 2026-09-29
Status: design approved in conversation; awaiting written-spec review

## 1. Why

The topic's learning path review step shows a list view (every concept's text,
"Learn first" panels, collapsed suggestions) plus a secondary graph that groups
concepts into columns by lesson heading. The teacher who owns the screen found
the list too much to take in and confusing. Separately, links are only derived
at **publish**, so the review screen shows no links and no recommendations at
all until a publish has run — publish also narrates, settles versions and
synthesises audio, so a teacher cannot review links without triggering all of
that, and after publish students follow links the teacher never saw.

Goal: the teacher reviews and edits the topic's prerequisite structure on one
graph, sees the system's recommendations beside it, and every change is
confirmed and undoable.

## 2. Decisions (made by the user)

| # | Decision |
|---|---|
| D1 | Graph is the only view. List view and the List/Graph toggle are removed. |
| D2 | Split screen: graph 75% width (left), recommended links 25% (right). |
| D3 | Layout is prerequisite-layered (prerequisites above, dependents below, siblings side by side) — it must read as a graph, not a single line. |
| D4 | Editing is drag and drop: dropping **B onto A** means "teach A before B". |
| D5 | If B already has a prerequisite, the confirm asks whether to **add** A as another prerequisite or **move** B under A. |
| D6 | Every change asks for confirmation before it is applied. |
| D7 | Every confirmed change offers **Undo** for ~10 seconds. |
| D8 | Clicking a concept opens a details popup (text, sources, "must learn first" with remove). |
| D9 | Links are derived when the learning path screen opens, not only at publish. |
| D10 | Graph library: React Flow + dagre. |
| D11 | Vitest is added as a dev-only dependency for pure frontend logic. |

## 3. Screen

### 3.1 Editable screen (topic review, learning path step)

```
┌──────────────────────── 75% ────────────────────────┬──── 25% ─────────┐
│ [−][+][Fit]                                          │ Recommended (n)  │
│                 [Matter]                             │ ┌──────────────┐ │
│          ┌────────┼────────┐                         │ │ Solid →      │ │
│       [Solid]  [Liquid]  [Gas]                       │ │  Comparing   │ │
│                                                      │ │ reason…      │ │
│ Not linked yet: [As a general rule] [Summary] …      │ │[Accept][Rej.]│ │
└──────────────────────────────────────────────────────┴──────────────────┘
```

**Graph (left).**
- Nodes are concepts (`steps` from the preview). Edges are links that shape
  the path (`accepted` + `approved`), arrow from prerequisite to dependent.
- Layered layout computed by dagre (`rankdir: TB`). Positions are computed on
  every render and never stored.
- Node shows the concept title, its teaching-order position as a badge, and a
  "Figure" badge when `kind === "image"`.
- Concepts with no incoming and no outgoing path link are left out of the
  dagre graph and shown in a **"Not linked yet"** strip below it, in teaching
  order. They are still draggable and still drop targets.
- Pan, zoom, and a Fit control (React Flow built-ins).
- Selecting a node highlights its prerequisites and dependents and dims the
  rest (the behaviour the old concept map had), and opens the details popup.

**Recommended links (right).**
- Lists `pending` links between live concepts, in teaching order of the
  dependent.
- Each card: "A → B", the plain-words `reason` (section 4.5), an "under
  different headings" flag when `cross_section` is true (existing wording), and
  Accept / Reject.
- Empty state: "No recommendations. The links on the graph are everything the
  lesson files support."

**Details popup (click a node).**
- Title, full text (`content`), source PDFs, and "Must learn first": each
  prerequisite listed with a Remove control. "Nothing must be learned before
  this" when empty.

**Kept:** the "changed since publish" note ("Students follow the old path until
you publish again").

**Removed:** `PathStep`, `LearnFirstPanel`, the List/Graph toggle, the
heading-column `ConceptMap` and `buildConceptMap`, `PathStats` if nothing else
uses it.

### 3.2 Read-only page (`LearningPathPage`)

Same graph component with `editable={false}`: no dragging, no recommendations
panel, details popup shows text and prerequisites without Remove controls.

## 4. Interactions

### 4.1 Drop B onto A

After any drop the dragged node returns to its layout position; only links
persist. Dropping on empty canvas does nothing.

| Situation | Popup | On confirm |
|---|---|---|
| A is B | none | nothing |
| A → B already shapes the path | "A is already taught before B." [OK] | nothing |
| B has no path prerequisite | "Teach **A** before **B**?" [Yes] [Cancel] | add A → B |
| B has path prerequisites P1..Pn | "**B** already comes after **P1, …**. What do you want?" [Add A as another prerequisite] [Move: A replaces P1, …] [Cancel] | *Add*: add A → B. *Move*: `move` (4.4) |

A loop is detected by the server (existing `_refuse_loop`); the popup stays
open and shows its message ("That would make a loop: … Remove one of those
links first.").

### 4.2 Recommendations

- Accept: "Teach **A** before **B**?" → approve the link.
- Reject: "Don't teach **A** before **B**? It won't be suggested again." → reject.

### 4.3 Remove (details popup)

"**P** no longer has to come before **B**? It won't be suggested again." →
reject the link (existing semantics: removing is rejecting).

### 4.4 Undo

Every confirmed change shows a bar for ~10 s: "<what changed>. [Undo]". A new
change replaces the bar. Undo sends the change's `undo` record to
`restore` (5.4); a move is undone as one action. On failure: "Couldn't undo:
<server message>. Refresh to see the current path."

## 5. Backend

### 5.1 Derive on open

`views.topic_learning_path` calls `refresh_prerequisites(topic)` before
`build_topic_path`. v4 criteria call no model; measured 2026-09-29 at ~25 ms
per topic (topics 340, 357). `build_topic_path`'s docstring, which says the
preview never derives because the encoder is too slow, is updated. Publish is
unchanged and still calls `refresh_prerequisites`.

### 5.2 Stable link ids in `refresh_prerequisites`

Today it deletes every non-teacher row and re-creates what the criteria
produce, so a derived link gets a new id on every derivation. With derivation
on every screen load, an Accept or Undo holding an id from the previous load
would hit a deleted row.

New behaviour, same transaction:
- pair produced and a non-teacher row exists → update `status`, `evidence`,
  `cross_section` in place;
- pair produced and no row → create (as today);
- pair produced and teacher-decided row → refresh explanation only (as today);
- non-teacher row whose pair is no longer produced → delete.

Return value unchanged.

### 5.3 Move

`teacher_links.move_link(node, prerequisite_id, dependent_id)`, atomic:
reject every `SHAPES_PATH` link into `dependent` other than from
`prerequisite`, then approve `prerequisite → dependent`. The loop check ignores
the links being rejected. Endpoint: `POST /learning-path/topics/<id>/links/move/`
with the same body as add.

### 5.4 Undo record and restore

`add_link`, `move_link` and `decide_link` capture, before changing anything,
the prior state of every pair they touch:

```json
{"undo": [
  {"prerequisite_id": 831, "dependent_id": 833,
   "prior": {"status": "pending", "source": "derived", "decided_at": null}},
  {"prerequisite_id": 846, "dependent_id": 833, "prior": null}
]}
```

`prior: null` means the pair had no row. The three link endpoints return the
preview as today plus this `undo` list.

`teacher_links.restore_links(node, records)` and
`POST /learning-path/topics/<id>/links/restore/`, atomic: each pair with a
prior state gets that status/source/decided_at back (creating the row if it was
deleted meanwhile); each `prior: null` pair's row is deleted. Validation: both
concepts belong to the topic, statuses are valid choices, and the resulting
path links form no loop (else `LinkError`, nothing applied). Returns the
preview.

### 5.5 Plain-words reason

`build_topic_path` adds `reason` to each suggestion entry (and to path-shaping
link entries), from `evidence["rule"]`:

| rule | reason |
|---|---|
| `definition` | "B's definition uses A: “<sentence>”" |
| `containment` | "B sits under the heading “<heading>”." |
| `reference` | "B's text names A in <k> of <n> passages; A's text names B in <m> of <p>." (from `prw_forward`/`prw_backward` and passage counts) |
| `conflict` | "The lesson files point both ways; choose one." |
| teacher-added | "Added by you." |

The reference counts need each concept's passage count; `passage_reference`
already has it and will record `passages_forward`/`passages_backward` counts
in its output so the sentence can say "k of n" rather than a ratio.

## 6. Frontend structure

- Dependencies: `@xyflow/react`, `@dagrejs/dagre`; dev: `vitest`.
- `web-app/src/learning-path/graphModel.js` (pure, tested): preview → React
  Flow nodes/edges with dagre positions; split of unlinked concepts;
  `classifyDrop(path, draggedId, targetId)` → `self | already | add | choose`.
- `web-app/src/learning-path/PathGraph.jsx`: graph, selection highlight,
  drag/drop, "Not linked yet" strip.
- `RecommendationsPanel.jsx`, `ConceptDetails.jsx`, `ConfirmDialog.jsx`,
  `UndoBar.jsx` in the same folder.
- `MaterialPath` in `LearningPathPage.jsx` becomes a thin wrapper choosing
  editable or read-only; `TopicDetailPage.jsx` keeps importing it.
- `api.js`: `movePathLink`, `restorePathLinks`; existing calls unchanged.

## 7. Errors

- Server refuses a change → confirm popup stays open with the message; graph
  unchanged.
- Undo fails → undo bar shows the message and suggests refresh.
- Preview load fails → error with Retry, not an empty graph.
- Topic with no steps → existing "No path yet…" message.

## 8. Testing

**Backend (Django):**
- GET creates derived links; a second GET keeps every id.
- A pair no longer produced is deleted; approved/rejected rows survive.
- `move_link`: all other incoming path links rejected, new one approved,
  atomic; refuses a loop and changes nothing.
- `restore_links`: undoes add (row deleted), approve/reject (status and source
  back), move (both halves); refuses a loop; refuses concepts from another topic.
- Each rule yields its reason sentence.
- Existing `learning_path` tests, including `test_gold_paths`, pass unchanged.

**Frontend (Vitest, pure logic):** `graphModel` layering places a prerequisite
above its dependent; siblings share a rank; unlinked concepts go to the strip;
`classifyDrop` returns each of its four outcomes.

**Manual, real app:** topics 340 and 357 — add, move, remove, accept, reject,
undo each, trigger a loop refusal; read-only page shows no editing controls.

## 9. Risks and notes

- **Pending links become prominent.** The model's comment says pending rows
  were hidden by default because a blind hand-check found most v3 proposals
  wrong. v4's pending rows come from R3 only; their precision has not been
  measured. On topics 340/357 today: 20 of 21 pending looked directionally
  right; one (`Seed formation → Reproduction in Flowering Plants`) is
  backwards. The right panel shows them all; the teacher's Reject is the
  control.
- **A GET now writes.** The preview endpoint derives and stores links. It is
  teacher-only, runs in one transaction, and is idempotent given unchanged
  content.
- Out of scope: the criteria themselves, the figure rule, course-level links,
  version generation.

## 10. Revision 2026-09-30 (user decision after trying the screen)

Supersedes D2 and the recommendations panel in 3.1:

- **One full-width graph.** The 25% recommended-links panel is removed on both
  the editable and the read-only screen.
- **Recommendations live on the concept they would change.** A pending link
  "A → B" is listed in **B**'s details card under *Must learn first*, as a
  yellow row labelled *Pending* with its reason, the "different section" flag,
  and Accept / Reject (same confirm and 10 s Undo as before).
- **The graph flags concepts needing a decision.** A concept with pending
  links gets a yellow fill and border and a yellow count badge; a line above
  the graph reads "N concepts have recommended links to review." Neither
  appears on the read-only page.
- **"Topic published!" dialog.** After a successful publish it replaces the
  progress window (a failed run keeps it). It loads
  `GET /learning-path/topics/<id>/published/` and lists each concept in path
  order with one player for its **Normal** narration only — no questions, no
  Simplified/Elaborated. A concept told in several parts plays them back to
  back ("Part 1 of 2"), as the learner hears that step; only one concept plays
  at a time; there is no "Play all" (user decision). Missing audio is shown as
  "No audio for this concept" or "N parts have no audio and are skipped".
