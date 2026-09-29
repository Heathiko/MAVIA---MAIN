# Learning Path Graph Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the learning path review screen's list view with a graph-only screen (75% graph, 25% recommended links) where a teacher edits prerequisites by drag and drop, every change is confirmed and undoable, and links are derived when the screen opens.

**Architecture:** Backend (Django, `backend/learning_path/`): the preview GET re-derives links through an id-stable `refresh_prerequisites`; link actions return an `undo` record; new `move` and `restore` endpoints; each link carries a plain-words `reason`. Frontend (React/Vite, `web-app/src/`): a pure `graphModel.js` (dagre layout, drop classification) under Vitest, rendered by React Flow in `PathGraph.jsx`, with confirm dialog, recommendations panel, details card and undo bar.

**Tech Stack:** Django 5 + DRF (tests: `python manage.py test`), React 18, Vite 5, `@xyflow/react` 12, `@dagrejs/dagre` 1, Vitest 2.

**Spec:** `docs/superpowers/specs/2026-09-29-learning-path-graph-screen-design.md`

## Global Constraints

- Graph is the only view; the List view and List/Graph toggle are removed.
- Editable screen: graph 75% width left, recommended links 25% right.
- Layout is prerequisite-layered (`rankdir: TB`): prerequisites above, dependents below, siblings side by side.
- Dropping **B onto A** means "teach A before B". When B already has path prerequisites, the confirm offers Add or Move.
- Every change is confirmed before it is applied; every confirmed change offers Undo for 10 seconds.
- Links are derived when the learning path screen opens (`GET /api/learning-path/topics/<id>/`); publishing still derives too.
- Derived link rows keep their id across derivations.
- New runtime dependencies: `@xyflow/react`, `@dagrejs/dagre` only. `vitest` is dev-only.
- Unchanged: the criteria's rules (`criteria.decide_pairs` verdicts), `order_with_links`, publishing, the adaptive engine.
- All link endpoints stay `IsTeacherOrAdmin`.
- Copy (use verbatim):
  - add: "Teach **A** before **B**?"
  - choose: "**B** already comes after **P1, …**. What do you want?" with "Add A as another prerequisite" / "Move: A replaces P1, …"
  - already: "A is already taught before B." [OK]
  - accept: "Teach **A** before **B**?"
  - reject: "Don't teach **A** before **B**? It won't be suggested again."
  - remove: "**P** no longer has to come before **B**? It won't be suggested again."
  - undo failure: "Couldn't undo: <message>. Refresh to see the current path."
  - empty panel: "No recommendations. The links on the graph are everything the lesson files support."

## Review Focus

1. A teacher clicks Accept/Remove on a link whose row was deleted since the page loaded (another tab re-derived, content changed) → the server answers "That link no longer exists. Refresh the page." and the dialog shows it; nothing crashes. *(Task 4 test `test_deciding_a_link_that_no_longer_exists_is_refused`.)*
2. Undo is pressed after the pair's row was deleted by a re-derivation in between → restore recreates the row as it was. *(Task 4 test `test_undo_recreates_a_link_deleted_in_between`.)*
3. A topic with no links at all → every concept sits in the "Not linked yet" row, the graph renders, no dagre call on an empty graph. *(Task 6 test `every concept sits in the strip when there are no links`.)*
4. Dropping a concept onto itself or onto its existing prerequisite → no request is sent (self ignored, "already" message); moving under the only current prerequisite keeps it approved without rejecting anything. *(Task 6 `classifyDrop` tests; Task 5 test `test_moving_under_the_current_prerequisite_rejects_nothing`.)*
5. Very long concept titles (LLM figure titles run to 60+ characters) → node shows two lines, full title on hover and in the details card; the layout does not overlap. *(Task 8 manual check step.)*

---

### Task 1: Keep derived link ids stable across derivations

**Files:**
- Modify: `backend/learning_path/services/publishing.py:28-80` (`refresh_prerequisites`)
- Test: `backend/learning_path/test_publishing.py` (class `RefreshPrerequisiteTests`)

**Interfaces:**
- Consumes: nothing new.
- Produces: `refresh_prerequisites(node, concepts=None, runtime_instance=None) -> {"accepted": int, "pending": int, "teacher_decided": int}` — same signature and return; rows the criteria still produce keep their primary key.

- [ ] **Step 1: Create the branch and commit the spec and plan**

```bash
cd /c/MAVIA
git switch -c learning-path-graph-screen
git add docs/superpowers/specs/2026-09-29-learning-path-graph-screen-design.md docs/superpowers/plans/2026-09-29-learning-path-graph-screen.md
git commit -m "Add spec and plan for the graph-first learning path screen"
```

- [ ] **Step 2: Write the failing tests**

Add to `class RefreshPrerequisiteTests` in `backend/learning_path/test_publishing.py`:

```python
    def test_a_link_the_criteria_still_produce_keeps_its_id(self):
        with self._derive(("Matter", "Solid", "accepted", False)):
            publishing.refresh_prerequisites(self.topic)
            first = ConceptPrerequisite.objects.get().id
            publishing.refresh_prerequisites(self.topic)

        self.assertEqual(ConceptPrerequisite.objects.get().id, first)

    def test_a_changed_verdict_is_updated_in_place(self):
        with self._derive(("Matter", "Solid", "accepted", False)):
            publishing.refresh_prerequisites(self.topic)
        first = ConceptPrerequisite.objects.get().id

        with self._derive(("Matter", "Solid", "pending", True)):
            publishing.refresh_prerequisites(self.topic)

        row = ConceptPrerequisite.objects.get()
        self.assertEqual((row.id, row.status, row.cross_section), (first, "pending", True))
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path.test_publishing.RefreshPrerequisiteTests -v 2`
Expected: the two new tests FAIL (`AssertionError: <new id> != <old id>`); the four existing ones pass.

- [ ] **Step 4: Rewrite the transaction in `refresh_prerequisites`**

Replace the `with transaction.atomic():` block (currently: delete non-teacher rows, then loop creating) with:

```python
    with transaction.atomic():
        for pair, decision in fresh.items():
            row = existing.get(pair)
            if pair in decided_pairs:
                # The teacher's call stands; refresh only the explanation.
                row.evidence = decision["evidence"]
                row.cross_section = decision["cross_section"]
                row.save(update_fields=["evidence", "cross_section", "updated_at"])
                continue
            if row is not None:
                # Updated in place, not re-created: the review screen derives on
                # every load, and an Accept or Undo holds this row's id.
                row.status = decision["verdict"]
                row.source = ConceptPrerequisite.Source.DERIVED
                row.cross_section = decision["cross_section"]
                row.evidence = decision["evidence"]
                row.save(update_fields=["status", "source", "cross_section", "evidence", "updated_at"])
                continue
            ConceptPrerequisite.objects.create(
                outline_node=node,
                prerequisite_id=pair[0],
                dependent_id=pair[1],
                status=decision["verdict"],
                source=ConceptPrerequisite.Source.DERIVED,
                cross_section=decision["cross_section"],
                evidence=decision["evidence"],
            )

        # Derived rows the criteria no longer produce.
        stale = [
            row.pk for pair, row in existing.items()
            if pair not in fresh and row.status not in ConceptPrerequisite.TEACHER_DECIDED
        ]
        ConceptPrerequisite.objects.filter(pk__in=stale).delete()
```

Leave the `counts` computation after the block unchanged.

- [ ] **Step 5: Run the class to verify all pass**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path.test_publishing -v 2`
Expected: all PASS (including `test_a_derived_link_the_criteria_drop_is_removed`).

- [ ] **Step 6: Commit**

```bash
cd /c/MAVIA
git add backend/learning_path/services/publishing.py backend/learning_path/test_publishing.py
git commit -m "Keep derived prerequisite link ids stable across derivations"
```

---

### Task 2: Derive links when the learning path screen opens

**Files:**
- Modify: `backend/learning_path/views.py:27-39` (`topic_learning_path`)
- Modify: `backend/learning_path/services/path_builder.py:1-9` (module docstring)
- Modify: `backend/learning_path/tests.py` (`TopicFixture`, `TopicPreviewTests`, `TeacherLinkTests`)

**Interfaces:**
- Consumes: `refresh_prerequisites(node)` from Task 1.
- Produces: `TopicFixture._derive(*rows)` test helper — `rows` are `(before_title, after_title, verdict)`; returns a `patch` context manager replacing `criteria.decide_pairs` with reference-rule decisions. Later tasks' tests use it.

- [ ] **Step 1: Add the `_derive` helper to `TopicFixture`**

In `backend/learning_path/tests.py`, add to `class TopicFixture` (after `_link`):

```python
    def _derive(self, *rows):
        """Replace the criteria with a fixed outcome, as a context manager.

        Each row is ``(before, after, verdict)``; evidence is a reference rule
        naming one passage each way, so reasons read predictably.
        """
        from unittest.mock import patch

        from .services import publishing

        concepts = {concept.title: concept for concept in publishing.concepts_for_topic(self.topic)}
        built = [
            {
                "prerequisite": concepts[before],
                "dependent": concepts[after],
                "verdict": verdict,
                "evidence": {"rule": "reference", "reference": {
                    "prw_forward": 1.0, "prw_backward": 0.0, "prd": 1.0, "theta": 0.05,
                    "passages_forward": 1, "passages_backward": 1,
                }},
                "cross_section": False,
            }
            for before, after, verdict in rows
        ]
        return patch.object(publishing.criteria, "decide_pairs", return_value=built)
```

- [ ] **Step 2: Write the failing tests**

Add to `class TopicPreviewTests`:

```python
    def test_opening_the_preview_derives_and_stores_links(self):
        with self._derive(("Matter", "Solid", "accepted")):
            path = self._path()

        solid = next(step for step in path["steps"] if step["title"] == "Solid")
        self.assertEqual([link["title"] for link in solid["prerequisites"]], ["Matter"])
        self.assertEqual(ConceptPrerequisite.objects.get().status, "accepted")

    def test_reopening_the_preview_keeps_every_link_id(self):
        with self._derive(("Matter", "Solid", "accepted"), ("Liquid", "Solid", "pending")):
            self._path()
            first = sorted(ConceptPrerequisite.objects.values_list("id", flat=True))
            self._path()

        self.assertEqual(sorted(ConceptPrerequisite.objects.values_list("id", flat=True)), first)
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path.tests.TopicPreviewTests -v 2`
Expected: `test_opening_the_preview_derives_and_stores_links` FAILS (`ConceptPrerequisite.DoesNotExist` / empty prerequisites); `test_reopening…` FAILS or passes vacuously with `[] == []` — either is acceptable before the change.

- [ ] **Step 4: Derive in the view**

In `backend/learning_path/views.py`, add the import next to the existing services import:

```python
from .services.publishing import refresh_prerequisites
```

and in `topic_learning_path`, replace `return Response(_preview(topic))` with:

```python
    # Links are derived on every open, not only at publish: v4's criteria
    # call no model (measured ~25 ms per topic), and a teacher must see the
    # links and recommendations before publishing makes them the students'.
    refresh_prerequisites(topic)
    return Response(_preview(topic))
```

Replace the module docstring of `backend/learning_path/services/path_builder.py` with:

```python
"""The topic's learning path as the review screen previews it.

The preview uses the same ordering the publish step saves
(``publishing.order_with_links``) over the links stored for the topic --
``accepted`` and ``approved``. The review endpoint re-derives those links
(``publishing.refresh_prerequisites``) just before building this preview, so
what a teacher reviews is what publishing would save.
"""
```

- [ ] **Step 5: Update the two tests that plant derived rows the real criteria would now delete**

In `TopicPreviewTests.test_pending_and_rejected_links_do_not_shape_the_preview`, replace its body with:

```python
        self._link("Solid", "Matter", "rejected")
        with self._derive(("Liquid", "Matter", "pending")):
            path = self._path()

        self.assertEqual(path["steps"][0]["title"], "Matter")
        self.assertEqual(path["edges"], [])
```

In `TeacherLinkTests.test_approving_a_suggestion_makes_it_shape_the_order`, replace the first two lines of the body with:

```python
        link = self._link("Liquid", "Solid", "pending")
        with self._derive(("Liquid", "Solid", "pending")):
            before = self._steps(self.teacher.get(f"{self.base}/"))
```

(keep the rest of that test unchanged).

- [ ] **Step 6: Run the learning_path suite and the lessons tests that open the preview**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path lessons.test_regrouping lessons.test_stale_versions -v 1`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
cd /c/MAVIA
git add backend/learning_path/views.py backend/learning_path/services/path_builder.py backend/learning_path/tests.py
git commit -m "Derive prerequisite links when the learning path screen opens"
```

---

### Task 3: Plain-words reasons and source files on each step

**Files:**
- Create: `backend/learning_path/services/reasons.py`
- Create: `backend/learning_path/test_reasons.py`
- Modify: `backend/learning_path/services/criteria.py:165-205` (`passage_reference`)
- Modify: `backend/learning_path/services/path_builder.py` (link entries, steps)
- Modify: `backend/learning_path/test_evidence.py:179`, `backend/learning_path/test_criteria.py:184-187`
- Test: `backend/learning_path/tests.py` (`TopicPreviewTests`)

**Interfaces:**
- Consumes: `TopicFixture._derive` (Task 2).
- Produces:
  - `link_reason(evidence: dict, prerequisite_title: str, dependent_title: str) -> str`
  - `passage_reference` entries gain `passages_forward: int` (the dependent's passage count) and `passages_backward: int` (the prerequisite's).
  - Preview: every entry in `step["prerequisites"]` and `step["suggestions"]` gains `"reason": str`; every step gains `"source_materials": [{"id": int, "title": str}]` sorted by id.

- [ ] **Step 1: Write the failing reason tests**

Create `backend/learning_path/test_reasons.py`:

```python
"""The one-sentence reason a teacher reads beside each link."""

from django.test import SimpleTestCase

from .services.reasons import link_reason


def reference(forward, n, backward, p):
    return {"rule": "reference", "reference": {
        "prw_forward": forward, "prw_backward": backward, "prd": forward - backward,
        "theta": 0.05, "passages_forward": n, "passages_backward": p,
    }}


class LinkReasonTests(SimpleTestCase):
    def test_definition_quotes_the_sentence(self):
        evidence = {"rule": "definition", "definition": {"sentence": "Melting is when a solid turns into a liquid"}}

        self.assertEqual(
            link_reason(evidence, "Solid", "Melting"),
            "Melting's definition uses Solid: “Melting is when a solid turns into a liquid”",
        )

    def test_containment_names_the_heading(self):
        evidence = {"rule": "containment", "containment": {"heading": "matter"}}

        self.assertEqual(link_reason(evidence, "Matter", "Solid"), "Solid sits under the heading “Matter”.")

    def test_reference_counts_passages(self):
        self.assertEqual(
            link_reason(reference(0.8, 5, 0.0, 3), "Solid", "Comparing"),
            "Comparing's text names Solid in 4 of 5 passages; Solid's text never names Comparing.",
        )

    def test_reference_both_ways(self):
        self.assertEqual(
            link_reason(reference(1.0, 2, 0.5, 2), "Solid", "Comparing"),
            "Comparing's text names Solid in 2 of 2 passages; Solid's text names Comparing in 1 of 2.",
        )

    def test_reference_without_counts_still_reads(self):
        evidence = {"rule": "reference", "reference": {"prw_forward": 1.0, "prw_backward": 0.0}}

        self.assertEqual(
            link_reason(evidence, "Solid", "Comparing"),
            "Comparing's text names Solid more often than Solid's text names Comparing.",
        )

    def test_conflict(self):
        self.assertEqual(link_reason({"rule": "conflict"}, "A", "B"), "The lesson files point both ways; choose one.")

    def test_a_teacher_link_has_no_evidence(self):
        self.assertEqual(link_reason({}, "A", "B"), "Added by you.")
        self.assertEqual(link_reason(None, "A", "B"), "Added by you.")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path.test_reasons -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'learning_path.services.reasons'`.

- [ ] **Step 3: Implement `reasons.py`**

Create `backend/learning_path/services/reasons.py`:

```python
"""One plain sentence explaining a prerequisite link, for the review screen.

Built from the evidence ``criteria.decide_pairs`` stores on each derived row,
so the screen never needs to know the rules. A row with no evidence was made
by the teacher.
"""


def link_reason(evidence, prerequisite_title, dependent_title):
    a, b = prerequisite_title, dependent_title
    evidence = evidence or {}
    rule = evidence.get("rule")

    if rule == "definition":
        sentence = (evidence.get("definition") or {}).get("sentence", "")
        return f"{b}'s definition uses {a}: “{sentence}”"
    if rule == "containment":
        return f"{b} sits under the heading “{a}”."
    if rule == "reference":
        ref = evidence.get("reference") or {}
        n, p = ref.get("passages_forward"), ref.get("passages_backward")
        if not n:
            return f"{b}'s text names {a} more often than {a}'s text names {b}."
        k = round(ref.get("prw_forward", 0) * n)
        m = round(ref.get("prw_backward", 0) * (p or 0))
        back = f"{a}'s text never names {b}." if m == 0 else f"{a}'s text names {b} in {m} of {p}."
        return f"{b}'s text names {a} in {k} of {n} passages; {back}"
    if rule == "conflict":
        return "The lesson files point both ways; choose one."
    return "Added by you."
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path.test_reasons -v 2`
Expected: 7 PASS.

- [ ] **Step 5: Record passage counts in `passage_reference`**

In `backend/learning_path/services/criteria.py`, inside `passage_reference`, replace the dict written to `references[(a.id, b.id)]` with:

```python
            references[(a.id, b.id)] = {
                "prw_forward": round(forward, 6),
                "prw_backward": round(backward, 6),
                "prd": round(forward - backward, 6),
                # Passage counts, so a reason can say "4 of 5" not "0.8".
                "passages_forward": len(passages[b.id]),
                "passages_backward": len(passages[a.id]),
            }
```

and update its docstring's first line to
`"""R3: ``{(a id, b id): {prw_forward, prw_backward, prd, passages_forward, passages_backward}}`` for named pairs.`

Update the two exact-dict assertions:
- `backend/learning_path/test_evidence.py:179` →
  `self.assertEqual(references[(1, 2)], {"prw_forward": 1.0, "prw_backward": 0.0, "prd": 1.0, "passages_forward": 1, "passages_backward": 1})`
- `backend/learning_path/test_criteria.py:184-187` →

```python
        self.assertEqual(decided[(1, 2)]["evidence"], {
            "rule": "reference",
            "reference": {
                "prw_forward": 1.0, "prw_backward": 0.0, "prd": 1.0, "theta": PRD_THRESHOLD,
                "passages_forward": 1, "passages_backward": 1,
            },
        })
```

- [ ] **Step 6: Write the failing preview tests**

Add to `class TopicPreviewTests` in `backend/learning_path/tests.py`:

```python
    def test_a_suggestion_says_why_in_plain_words(self):
        with self._derive(("Liquid", "Solid", "pending")):
            path = self._path()

        solid = next(step for step in path["steps"] if step["title"] == "Solid")
        self.assertEqual(
            solid["suggestions"][0]["reason"],
            "Solid's text names Liquid in 1 of 1 passages; Liquid's text never names Solid.",
        )

    def test_a_teacher_link_says_the_teacher_added_it(self):
        self._link("Liquid", "Solid", "approved")

        solid = next(step for step in self._path()["steps"] if step["title"] == "Solid")

        self.assertEqual(solid["prerequisites"][0]["reason"], "Added by you.")

    def test_each_step_names_its_source_files(self):
        path = self._path()

        self.assertEqual(path["steps"][0]["source_materials"], [{"id": self.material.id, "title": "Lesson one"}])
```

- [ ] **Step 7: Run to verify they fail**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path.tests.TopicPreviewTests -v 2`
Expected: the three new tests FAIL with `KeyError: 'reason'` / `KeyError: 'source_materials'`.

- [ ] **Step 8: Add `reason` and `source_materials` in `build_topic_path`**

In `backend/learning_path/services/path_builder.py` add the import:

```python
from .reasons import link_reason
```

In the loop building `entry`, add a key after `"cross_section": row.cross_section,`:

```python
            "reason": link_reason(row.evidence, title[row.prerequisite_id], title[row.dependent_id]),
```

Add a helper above `steps = []`:

```python
    def sources(concept):
        # The files a step was assembled from, named for the details card.
        named = {member.material_id: member.material.title for member in concept.members}
        return [{"id": material_id, "title": named[material_id]} for material_id in sorted(named)]
```

and add to each step dict, after `"source_material_ids": concept.source_material_ids,`:

```python
            "source_materials": sources(concept),
```

- [ ] **Step 9: Run the whole learning_path suite**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path -v 1`
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
cd /c/MAVIA
git add backend/learning_path/services/reasons.py backend/learning_path/test_reasons.py backend/learning_path/services/criteria.py backend/learning_path/services/path_builder.py backend/learning_path/test_evidence.py backend/learning_path/test_criteria.py backend/learning_path/tests.py
git commit -m "Explain each prerequisite link in plain words and name each step's source files"
```

---

### Task 4: Undo records on link changes, and restore

**Files:**
- Modify: `backend/learning_path/services/teacher_links.py`
- Modify: `backend/learning_path/views.py` (`add_path_link`, `decide_path_link`, new `restore_path_links`)
- Modify: `backend/learning_path/urls.py`
- Create: `backend/learning_path/test_link_editing.py`

**Interfaces:**
- Consumes: `TopicFixture` (`backend/learning_path/tests.py`).
- Produces:
  - `add_link(node, prerequisite_id, dependent_id) -> list[UndoRecord]` (was: row)
  - `decide_link(node, link_id, status) -> list[UndoRecord]` (was: row)
  - `restore_links(node, records: list[UndoRecord]) -> None`, raises `LinkError`
  - `_snapshot(node, pairs: list[tuple[int, int]]) -> list[UndoRecord]`
  - `_refuse_loop(node, prerequisite, dependent, ignore_ids=())` (was `ignore_id=None`)
  - `UndoRecord = {"prerequisite_id": int, "dependent_id": int, "prior": None | {"status": str, "source": str, "decided_at": str | None}}`
  - Endpoints: add and decision responses gain `"undo": [UndoRecord]`; `POST /api/learning-path/topics/<id>/links/restore/` body `{"undo": [UndoRecord]}` → preview, 200; 400 `{"detail": …}` on error.

- [ ] **Step 1: Write the failing tests**

Create `backend/learning_path/test_link_editing.py`:

```python
"""Undo and move on the learning path review screen.

Every change a teacher confirms returns the prior state of each pair it
touched; restore puts exactly that back. See
docs/superpowers/specs/2026-09-29-learning-path-graph-screen-design.md, 5.3-5.4.
"""

from lessons.models import LearningObject, LearningObjectGroup, OutlineNode

from .models import ConceptPrerequisite
from .tests import TopicFixture


class LinkEditingFixture(TopicFixture):
    def setUp(self):
        super().setUp()
        self.teacher = self._client("TEACHER")
        self.base = f"/api/learning-path/topics/{self.topic.id}"

    def _post(self, path, body):
        return self.teacher.post(f"{self.base}/links/{path}", body, format="json")

    def _ids(self, before, after):
        return {"prerequisite_concept_id": self.groups[before].id, "dependent_concept_id": self.groups[after].id}

    def _row(self, before, after):
        return ConceptPrerequisite.objects.filter(
            prerequisite=self.groups[before], dependent=self.groups[after],
        ).first()

    def _state(self, before, after):
        row = self._row(before, after)
        return None if row is None else (row.status, row.source)


class UndoTests(LinkEditingFixture):
    def test_adding_returns_an_undo_that_deletes_the_new_link(self):
        response = self._post("", self._ids("Liquid", "Solid"))
        undo = response.json()["undo"]

        self.assertEqual(undo, [{
            "prerequisite_id": self.groups["Liquid"].id, "dependent_id": self.groups["Solid"].id, "prior": None,
        }])
        restored = self._post("restore/", {"undo": undo})
        self.assertEqual(restored.status_code, 200, restored.json())
        self.assertIsNone(self._row("Liquid", "Solid"))

    def test_undoing_an_approval_puts_the_suggestion_back(self):
        link = self._link("Liquid", "Solid", "pending")
        undo = self._post(f"{link.id}/decision/", {"status": "approved"}).json()["undo"]

        self._post("restore/", {"undo": undo})

        link.refresh_from_db()
        self.assertEqual((link.status, link.source, link.decided_at), ("pending", "derived", None))

    def test_undoing_a_removal_brings_the_link_back(self):
        link = self._link("Matter", "Solid", "accepted")
        undo = self._post(f"{link.id}/decision/", {"status": "rejected"}).json()["undo"]

        self._post("restore/", {"undo": undo})

        self.assertEqual(self._state("Matter", "Solid"), ("accepted", "derived"))

    def test_undo_recreates_a_link_deleted_in_between(self):
        link = self._link("Matter", "Solid", "accepted")
        undo = self._post(f"{link.id}/decision/", {"status": "rejected"}).json()["undo"]
        ConceptPrerequisite.objects.all().delete()

        response = self._post("restore/", {"undo": undo})

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(self._state("Matter", "Solid"), ("accepted", "derived"))

    def test_restore_refuses_a_loop_and_changes_nothing(self):
        self._link("Matter", "Liquid", "approved")
        records = [{
            "prerequisite_id": self.groups["Liquid"].id, "dependent_id": self.groups["Matter"].id,
            "prior": {"status": "approved", "source": "teacher", "decided_at": None},
        }]

        response = self._post("restore/", {"undo": records})

        self.assertEqual(response.status_code, 400)
        self.assertIn("loop", response.json()["detail"])
        self.assertIsNone(self._row("Liquid", "Matter"))

    def test_restore_refuses_a_concept_from_another_topic(self):
        other_topic = OutlineNode.objects.create(course=self.course, title="Other", order=1, depth=0)
        stranger = LearningObjectGroup.objects.create(outline_node=other_topic, label="Stranger")
        records = [{"prerequisite_id": stranger.id, "dependent_id": self.groups["Solid"].id, "prior": None}]

        response = self._post("restore/", {"undo": records})

        self.assertEqual(response.status_code, 400)
        self.assertIn("not part of this topic", response.json()["detail"])

    def test_restore_without_records_is_refused(self):
        response = self._post("restore/", {})

        self.assertEqual(response.status_code, 400)

    def test_students_cannot_restore(self):
        response = self._client("STUDENT").post(f"{self.base}/links/restore/", {"undo": []}, format="json")

        self.assertEqual(response.status_code, 403)

    def test_deciding_a_link_that_no_longer_exists_is_refused(self):
        response = self._post("999999/decision/", {"status": "approved"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("no longer exists", response.json()["detail"])
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path.test_link_editing -v 2`
Expected: undo tests FAIL (`KeyError: 'undo'`, 404 on `restore/`); `test_deciding_a_link_that_no_longer_exists_is_refused` PASSES already (it pins existing behaviour).

- [ ] **Step 3: Implement snapshot, loop helpers and restore in `teacher_links.py`**

In `backend/learning_path/services/teacher_links.py`:

Replace the imports block with:

```python
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from lessons.models import LearningObjectGroup

from ..models import ConceptPrerequisite, LearningPathStep
```

Replace `_loop_through`'s signature and its exclusion with:

```python
def _loop_through(node, prerequisite, dependent, ignore_ids=()):
    """Concept ids forming a loop if ``prerequisite -> dependent`` were added, else None."""
    successors = {}
    rows = ConceptPrerequisite.objects.filter(
        outline_node=node, status__in=ConceptPrerequisite.SHAPES_PATH,
    ).exclude(pk__in=list(ignore_ids))
```

(the rest of `_loop_through` unchanged). Replace `_refuse_loop`'s first two lines with:

```python
def _refuse_loop(node, prerequisite, dependent, ignore_ids=()):
    chain = _loop_through(node, prerequisite, dependent, ignore_ids)
```

Add after `_refuse_loop`:

```python
def _snapshot(node, pairs):
    """The state of each pair before a change: what Undo puts back.

    ``prior`` is None when the pair had no row.
    """
    rows = {
        (row.prerequisite_id, row.dependent_id): row
        for row in ConceptPrerequisite.objects.filter(outline_node=node)
    }
    records = []
    for prerequisite_id, dependent_id in pairs:
        row = rows.get((prerequisite_id, dependent_id))
        records.append({
            "prerequisite_id": prerequisite_id,
            "dependent_id": dependent_id,
            "prior": None if row is None else {
                "status": row.status,
                "source": row.source,
                "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            },
        })
    return records


def _has_loop(node):
    """True when the topic's path-shaping links contain a cycle (Kahn)."""
    successors, indegree = {}, {}
    for row in ConceptPrerequisite.objects.filter(outline_node=node, status__in=ConceptPrerequisite.SHAPES_PATH):
        successors.setdefault(row.prerequisite_id, []).append(row.dependent_id)
        indegree[row.dependent_id] = indegree.get(row.dependent_id, 0) + 1
        indegree.setdefault(row.prerequisite_id, 0)
    ready = [concept_id for concept_id, count in indegree.items() if count == 0]
    seen = 0
    while ready:
        current = ready.pop()
        seen += 1
        for following in successors.get(current, []):
            indegree[following] -= 1
            if indegree[following] == 0:
                ready.append(following)
    return seen < len(indegree)
```

In `add_link`, change the loop-check line and return the snapshot:

```python
    existing = ConceptPrerequisite.objects.filter(prerequisite=prerequisite, dependent=dependent).first()
    _refuse_loop(node, prerequisite, dependent, ignore_ids=[existing.id] if existing else [])
    undo = _snapshot(node, [(prerequisite.id, dependent.id)])

    ConceptPrerequisite.objects.update_or_create(
        prerequisite=prerequisite,
        dependent=dependent,
        defaults={
            "outline_node": node,
            "status": ConceptPrerequisite.Status.APPROVED,
            "source": ConceptPrerequisite.Source.TEACHER,
            "decided_at": timezone.now(),
        },
    )
    return undo
```

and update its docstring to `"""``dependent`` needs ``prerequisite`` first, by a teacher's decision. Returns the undo record."""`.

In `decide_link`, replace from the approve loop check to the end with:

```python
    if status == ConceptPrerequisite.Status.APPROVED:
        _refuse_loop(node, row.prerequisite, row.dependent, ignore_ids=[row.id])
    undo = _snapshot(node, [(row.prerequisite_id, row.dependent_id)])

    row.status = status
    row.source = ConceptPrerequisite.Source.TEACHER
    row.decided_at = timezone.now()
    row.save(update_fields=["status", "source", "decided_at", "updated_at"])
    return undo
```

and update its docstring to `"""Approve a suggestion, or reject (remove) any link. Returns the undo record."""`.

Add at the end of the module:

```python
_INVALID_UNDO = "That undo is not valid. Refresh the page."


@transaction.atomic
def restore_links(node, records):
    """Put each pair back exactly as an undo record says it was.

    A pair with ``prior: None`` had no row, so its row is deleted; any other
    pair gets its status, source and decision time back, re-created if the row
    was deleted meanwhile. Refused, with nothing changed, if the result loops.
    """
    if not isinstance(records, list) or not records:
        raise LinkError("Nothing to undo.")
    for record in records:
        try:
            prerequisite_id = int(record["prerequisite_id"])
            dependent_id = int(record["dependent_id"])
            prior = record["prior"]
        except (KeyError, TypeError, ValueError):
            raise LinkError(_INVALID_UNDO)
        prerequisite = _group(node, prerequisite_id)
        dependent = _group(node, dependent_id)

        if prior is None:
            ConceptPrerequisite.objects.filter(prerequisite=prerequisite, dependent=dependent).delete()
            continue
        if (
            not isinstance(prior, dict)
            or prior.get("status") not in ConceptPrerequisite.Status.values
            or prior.get("source") not in ConceptPrerequisite.Source.values
        ):
            raise LinkError(_INVALID_UNDO)
        ConceptPrerequisite.objects.update_or_create(
            prerequisite=prerequisite,
            dependent=dependent,
            defaults={
                "outline_node": node,
                "status": prior["status"],
                "source": prior["source"],
                "decided_at": parse_datetime(prior["decided_at"]) if prior.get("decided_at") else None,
            },
        )
    if _has_loop(node):
        raise LinkError("Undoing that would make a loop. Refresh the page to see the current path.")
```

- [ ] **Step 4: Return undo records from the views and add the restore endpoint**

In `backend/learning_path/views.py` change the teacher_links import to:

```python
from .services.teacher_links import LinkError, add_link, decide_link, restore_links
```

In `add_path_link` replace the `try` block and return with:

```python
    try:
        undo = add_link(
            topic,
            int(request.data.get("prerequisite_concept_id")),
            int(request.data.get("dependent_concept_id")),
        )
    except (TypeError, ValueError) as exc:
        detail = str(exc) if isinstance(exc, LinkError) else "Choose both concepts."
        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
    return Response({**_preview(topic), "undo": undo}, status=status.HTTP_201_CREATED)
```

In `decide_path_link` replace the `try` block and return with:

```python
    try:
        undo = decide_link(topic, link_id, request.data.get("status"))
    except LinkError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({**_preview(topic), "undo": undo})
```

Add before `published_learning_path`:

```python
@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def restore_path_links(request, node_id):
    """Undo a link change. Body: ``{"undo": [<record from the change's response>]}``."""
    topic = OutlineNode.objects.filter(pk=node_id).first()
    if topic is None:
        return Response({"detail": "Topic not found."}, status=status.HTTP_404_NOT_FOUND)
    try:
        restore_links(topic, request.data.get("undo"))
    except LinkError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_preview(topic))
```

In `backend/learning_path/urls.py` add to `urlpatterns` (before the `links/<int:link_id>/decision/` entry):

```python
    path("topics/<int:node_id>/links/restore/", views.restore_path_links, name="restore-path-links"),
```

- [ ] **Step 5: Run the tests**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path -v 1`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
cd /c/MAVIA
git add backend/learning_path/services/teacher_links.py backend/learning_path/views.py backend/learning_path/urls.py backend/learning_path/test_link_editing.py
git commit -m "Return undo records from link changes and add a restore endpoint"
```

---

### Task 5: Move a concept under another prerequisite

**Files:**
- Modify: `backend/learning_path/services/teacher_links.py` (add `move_link`)
- Modify: `backend/learning_path/views.py` (add `move_path_link`)
- Modify: `backend/learning_path/urls.py`
- Modify: `backend/learning_path/test_link_editing.py` (add `MoveTests`)

**Interfaces:**
- Consumes: `_group`, `_refuse_loop(..., ignore_ids)`, `_snapshot`, `LinkEditingFixture` (Task 4).
- Produces: `move_link(node, prerequisite_id, dependent_id) -> list[UndoRecord]`; `POST /api/learning-path/topics/<id>/links/move/` with body `{"prerequisite_concept_id", "dependent_concept_id"}` → `{...preview, "undo": [...]}`, 200.

- [ ] **Step 1: Write the failing tests**

Append to `backend/learning_path/test_link_editing.py`:

```python
class MoveTests(LinkEditingFixture):
    def setUp(self):
        super().setUp()
        group = LearningObjectGroup.objects.create(outline_node=self.topic, label="Gas")
        self.objects["Gas"] = LearningObject.objects.create(
            material=self.material, group=group, title="Gas", content="Gas is taught here.", order=3,
        )
        self.groups["Gas"] = group

    def test_moving_replaces_every_current_prerequisite(self):
        self._link("Matter", "Gas", "accepted")
        self._link("Solid", "Gas", "approved")

        response = self._post("move/", self._ids("Liquid", "Gas"))

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(self._state("Matter", "Gas"), ("rejected", "teacher"))
        self.assertEqual(self._state("Solid", "Gas"), ("rejected", "teacher"))
        self.assertEqual(self._state("Liquid", "Gas"), ("approved", "teacher"))

    def test_undoing_a_move_restores_both_halves(self):
        self._link("Matter", "Gas", "accepted")
        self._link("Solid", "Gas", "approved")
        undo = self._post("move/", self._ids("Liquid", "Gas")).json()["undo"]

        self._post("restore/", {"undo": undo})

        self.assertEqual(self._state("Matter", "Gas"), ("accepted", "derived"))
        self.assertEqual(self._state("Solid", "Gas"), ("approved", "teacher"))
        self.assertIsNone(self._row("Liquid", "Gas"))

    def test_a_move_that_would_loop_changes_nothing(self):
        self._link("Matter", "Gas", "accepted")
        self._link("Gas", "Liquid", "approved")

        response = self._post("move/", self._ids("Liquid", "Gas"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("loop", response.json()["detail"])
        self.assertEqual(self._state("Matter", "Gas"), ("accepted", "derived"))
        self.assertIsNone(self._row("Liquid", "Gas"))

    def test_moving_under_the_current_prerequisite_rejects_nothing(self):
        self._link("Matter", "Gas", "accepted")

        self._post("move/", self._ids("Matter", "Gas"))

        self.assertEqual(self._state("Matter", "Gas"), ("approved", "teacher"))
        self.assertFalse(ConceptPrerequisite.objects.filter(status="rejected").exists())

    def test_a_concept_cannot_move_under_itself(self):
        response = self._post("move/", self._ids("Gas", "Gas"))

        self.assertEqual(response.status_code, 400)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path.test_link_editing.MoveTests -v 2`
Expected: FAIL with 404 on `links/move/`.

- [ ] **Step 3: Implement `move_link`**

Add to `backend/learning_path/services/teacher_links.py` after `decide_link`:

```python
@transaction.atomic
def move_link(node, prerequisite_id, dependent_id):
    """``dependent`` needs ``prerequisite`` first, and nothing it needed before.

    Every other link shaping the path into ``dependent`` is rejected, and
    ``prerequisite -> dependent`` is approved, in one step. Returns the undo
    record covering both halves.
    """
    prerequisite = _group(node, prerequisite_id)
    dependent = _group(node, dependent_id)
    if prerequisite.id == dependent.id:
        raise LinkError("A concept cannot be its own prerequisite.")

    replaced = list(
        ConceptPrerequisite.objects.filter(
            outline_node=node, dependent=dependent, status__in=ConceptPrerequisite.SHAPES_PATH,
        ).exclude(prerequisite=prerequisite)
    )
    existing = ConceptPrerequisite.objects.filter(prerequisite=prerequisite, dependent=dependent).first()
    ignore = [row.id for row in replaced] + ([existing.id] if existing else [])
    _refuse_loop(node, prerequisite, dependent, ignore_ids=ignore)
    undo = _snapshot(
        node,
        [(row.prerequisite_id, row.dependent_id) for row in replaced] + [(prerequisite.id, dependent.id)],
    )

    now = timezone.now()
    for row in replaced:
        row.status = ConceptPrerequisite.Status.REJECTED
        row.source = ConceptPrerequisite.Source.TEACHER
        row.decided_at = now
        row.save(update_fields=["status", "source", "decided_at", "updated_at"])
    ConceptPrerequisite.objects.update_or_create(
        prerequisite=prerequisite,
        dependent=dependent,
        defaults={
            "outline_node": node,
            "status": ConceptPrerequisite.Status.APPROVED,
            "source": ConceptPrerequisite.Source.TEACHER,
            "decided_at": now,
        },
    )
    return undo
```

- [ ] **Step 4: Add the view and URL**

In `backend/learning_path/views.py` extend the import to
`from .services.teacher_links import LinkError, add_link, decide_link, move_link, restore_links`
and add after `add_path_link`:

```python
@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def move_path_link(request, node_id):
    """Make one concept the only prerequisite of another.

    Body: ``{"prerequisite_concept_id": <group>, "dependent_concept_id": <group>}``.
    """
    topic = OutlineNode.objects.filter(pk=node_id).first()
    if topic is None:
        return Response({"detail": "Topic not found."}, status=status.HTTP_404_NOT_FOUND)
    try:
        undo = move_link(
            topic,
            int(request.data.get("prerequisite_concept_id")),
            int(request.data.get("dependent_concept_id")),
        )
    except (TypeError, ValueError) as exc:
        detail = str(exc) if isinstance(exc, LinkError) else "Choose both concepts."
        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
    return Response({**_preview(topic), "undo": undo})
```

In `backend/learning_path/urls.py` add, next to the restore route:

```python
    path("topics/<int:node_id>/links/move/", views.move_path_link, name="move-path-link"),
```

- [ ] **Step 5: Run the tests**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path -v 1`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
cd /c/MAVIA
git add backend/learning_path/services/teacher_links.py backend/learning_path/views.py backend/learning_path/urls.py backend/learning_path/test_link_editing.py
git commit -m "Add moving a concept under a single new prerequisite"
```

---

### Task 6: Graph model (layout, highlighting, drop classification) with Vitest

**Files:**
- Modify: `web-app/package.json` (dependencies, `test` script)
- Create: `web-app/src/learning-path/graphModel.js`
- Create: `web-app/src/learning-path/graphModel.test.js`

**Interfaces:**
- Consumes: preview `steps` — each `{concept_id, position, title, kind, content, prerequisites: [{link_id, concept_id, title, status, reason}], suggestions: [same], source_materials}`.
- Produces (all named exports of `graphModel.js`):
  - `NODE_WIDTH = 210`, `NODE_HEIGHT = 64`
  - `pathEdges(steps) -> [{linkId, from, to}]`
  - `splitLinked(steps) -> {linked: Step[], unlinked: Step[]}` (both by `position`)
  - `highlightRoles(steps, selectedId) -> Map<conceptId, "is-selected"|"is-needed"|"is-leads">`
  - `buildGraph(steps, selectedId = null) -> {nodes, edges}` — React Flow nodes `{id: String(concept_id), type: "concept", position, data: {step, role}}` plus, when any unlinked, one `{id: "not-linked-label", type: "label", draggable: false, selectable: false, data: {text: "Not linked yet"}}`; edges `{id: "link-<link_id>", source, target, markerEnd: {type: "arrowclosed"}}`
  - `classifyDrop(steps, draggedId, targetId) -> {kind: "self"|"already"|"add"|"choose", current: PrerequisiteEntry[]}` — dragged is B (dependent), target is A (prerequisite)
  - `recommendations(steps) -> [{linkId, fromId, fromTitle, toId, toTitle, reason, crossSection}]` sorted by the dependent's position

- [ ] **Step 1: Install dependencies and add the test script**

```bash
cd /c/MAVIA/web-app
npm install @xyflow/react@^12 @dagrejs/dagre@^1
npm install -D vitest@^2
```

In `web-app/package.json` add to `"scripts"`: `"test": "vitest run"`.

- [ ] **Step 2: Write the failing tests**

Create `web-app/src/learning-path/graphModel.test.js`:

```js
import { describe, expect, it } from "vitest";

import { buildGraph, classifyDrop, highlightRoles, recommendations, splitLinked } from "./graphModel";

const link = (linkId, conceptId, title, extra = {}) => ({ link_id: linkId, concept_id: conceptId, title, ...extra });
const step = (id, position, title, prerequisites = [], suggestions = []) => ({
  concept_id: id, position, title, kind: "text", content: "", prerequisites, suggestions,
});

const STEPS = [
  step(1, 1, "Matter"),
  step(2, 2, "Solid", [link(10, 1, "Matter")]),
  step(3, 3, "Liquid", [link(11, 1, "Matter")], [link(20, 2, "Solid", { reason: "Liquid's text names Solid in 1 of 1 passages; Solid's text never names Liquid.", cross_section: true })]),
  step(4, 4, "Summary"),
];

const at = (graph, id) => graph.nodes.find((node) => node.id === String(id)).position;

describe("buildGraph", () => {
  it("puts a prerequisite above its dependent", () => {
    const graph = buildGraph(STEPS);
    expect(at(graph, 1).y).toBeLessThan(at(graph, 2).y);
  });

  it("puts siblings side by side on one row", () => {
    const graph = buildGraph(STEPS);
    expect(at(graph, 2).y).toBe(at(graph, 3).y);
    expect(at(graph, 2).x).not.toBe(at(graph, 3).x);
  });

  it("puts unlinked concepts in a labelled strip below the graph", () => {
    const graph = buildGraph(STEPS);
    expect(at(graph, 4).y).toBeGreaterThan(at(graph, 2).y);
    expect(graph.nodes.some((node) => node.id === "not-linked-label")).toBe(true);
  });

  it("draws one arrow per path link, prerequisite to dependent", () => {
    const graph = buildGraph(STEPS);
    expect(graph.edges).toHaveLength(2);
    expect(graph.edges[0]).toMatchObject({ id: "link-10", source: "1", target: "2" });
  });

  it("every concept sits in the strip when there are no links", () => {
    const bare = [step(1, 1, "A"), step(2, 2, "B")];
    const graph = buildGraph(bare);
    expect(graph.edges).toEqual([]);
    expect(at(graph, 1).y).toBe(at(graph, 2).y);
    expect(at(graph, 1).x).toBeLessThan(at(graph, 2).x);
  });

  it("dims every concept unrelated to the selection", () => {
    const graph = buildGraph(STEPS, 2);
    const role = (id) => graph.nodes.find((node) => node.id === String(id)).data.role;
    expect(role(2)).toBe("is-selected");
    expect(role(1)).toBe("is-needed");
    expect(role(4)).toBe("is-dimmed");
  });
});

describe("highlightRoles", () => {
  it("marks what builds on the selected concept", () => {
    const roles = highlightRoles(STEPS, 1);
    expect(roles.get(2)).toBe("is-leads");
    expect(roles.get(3)).toBe("is-leads");
  });

  it("is empty with nothing selected", () => {
    expect(highlightRoles(STEPS, null).size).toBe(0);
  });
});

describe("splitLinked", () => {
  it("keeps teaching order in both groups", () => {
    const { linked, unlinked } = splitLinked(STEPS);
    expect(linked.map((s) => s.concept_id)).toEqual([1, 2, 3]);
    expect(unlinked.map((s) => s.concept_id)).toEqual([4]);
  });
});

describe("classifyDrop", () => {
  it("ignores a concept dropped on itself", () => {
    expect(classifyDrop(STEPS, 2, 2).kind).toBe("self");
  });

  it("says so when the target already comes first", () => {
    expect(classifyDrop(STEPS, 2, 1).kind).toBe("already");
  });

  it("adds when the dragged concept has no prerequisite", () => {
    expect(classifyDrop(STEPS, 4, 1)).toEqual({ kind: "add", current: [] });
  });

  it("asks add-or-move when the dragged concept already has one", () => {
    const drop = classifyDrop(STEPS, 2, 3);
    expect(drop.kind).toBe("choose");
    expect(drop.current.map((entry) => entry.title)).toEqual(["Matter"]);
  });
});

describe("recommendations", () => {
  it("lists each pending link with its reason", () => {
    expect(recommendations(STEPS)).toEqual([{
      linkId: 20, fromId: 2, fromTitle: "Solid", toId: 3, toTitle: "Liquid",
      reason: "Liquid's text names Solid in 1 of 1 passages; Solid's text never names Liquid.",
      crossSection: true,
    }]);
  });
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd /c/MAVIA/web-app && npm test`
Expected: FAIL — `Failed to resolve import "./graphModel"`.

- [ ] **Step 4: Implement `graphModel.js`**

Create `web-app/src/learning-path/graphModel.js`:

```js
// Pure helpers behind the learning path graph: what to draw, where, and what a
// drop means. Nothing here renders or calls the server, so it is tested alone.
import dagre from "@dagrejs/dagre";

export const NODE_WIDTH = 210;
export const NODE_HEIGHT = 64;
const STRIP_GAP = 110;
const STRIP_COLUMNS = 5;
const COLUMN_STEP = NODE_WIDTH + 30;
const ROW_STEP = NODE_HEIGHT + 30;
const MARGIN = 20;

const byPosition = (steps) => [...steps].sort((a, b) => a.position - b.position);

// Links that shape the path, one per "learn first" entry on a step.
export function pathEdges(steps) {
  return steps.flatMap((step) =>
    (step.prerequisites || []).map((link) => ({ linkId: link.link_id, from: link.concept_id, to: step.concept_id })),
  );
}

// Concepts in the prerequisite graph, and those no link touches yet.
export function splitLinked(steps) {
  const touched = new Set();
  for (const edge of pathEdges(steps)) {
    touched.add(edge.from);
    touched.add(edge.to);
  }
  const ordered = byPosition(steps);
  return {
    linked: ordered.filter((step) => touched.has(step.concept_id)),
    unlinked: ordered.filter((step) => !touched.has(step.concept_id)),
  };
}

// Selecting a concept shows what must come before it and what builds on it.
export function highlightRoles(steps, selectedId) {
  const roles = new Map();
  if (selectedId === null || selectedId === undefined) return roles;
  for (const edge of pathEdges(steps)) {
    if (edge.to === selectedId) roles.set(edge.from, "is-needed");
    if (edge.from === selectedId) roles.set(edge.to, "is-leads");
  }
  roles.set(selectedId, "is-selected");
  return roles;
}

export function buildGraph(steps, selectedId = null) {
  const { linked, unlinked } = splitLinked(steps);
  const edges = pathEdges(steps);
  const roles = highlightRoles(steps, selectedId);
  const hasSelection = selectedId !== null && selectedId !== undefined;
  const roleOf = (id) => roles.get(id) || (hasSelection ? "is-dimmed" : "");

  // dagre returns centres; React Flow positions are top-left corners.
  const positions = new Map();
  let bottom = 0;
  if (linked.length) {
    const graph = new dagre.graphlib.Graph();
    graph.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 70, marginx: MARGIN, marginy: MARGIN });
    graph.setDefaultEdgeLabel(() => ({}));
    for (const step of linked) graph.setNode(String(step.concept_id), { width: NODE_WIDTH, height: NODE_HEIGHT });
    for (const edge of edges) graph.setEdge(String(edge.from), String(edge.to));
    dagre.layout(graph);
    for (const step of linked) {
      const { x, y } = graph.node(String(step.concept_id));
      positions.set(step.concept_id, { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 });
      bottom = Math.max(bottom, y + NODE_HEIGHT / 2);
    }
  }

  const stripTop = linked.length ? bottom + STRIP_GAP : MARGIN + 34;
  unlinked.forEach((step, index) => {
    positions.set(step.concept_id, {
      x: MARGIN + (index % STRIP_COLUMNS) * COLUMN_STEP,
      y: stripTop + Math.floor(index / STRIP_COLUMNS) * ROW_STEP,
    });
  });

  const nodes = byPosition(steps).map((step) => ({
    id: String(step.concept_id),
    type: "concept",
    position: positions.get(step.concept_id),
    data: { step, role: roleOf(step.concept_id) },
  }));
  if (unlinked.length) {
    nodes.push({
      id: "not-linked-label",
      type: "label",
      position: { x: MARGIN, y: stripTop - 34 },
      data: { text: "Not linked yet" },
      draggable: false,
      selectable: false,
    });
  }

  return {
    nodes,
    edges: edges.map((edge) => ({
      id: `link-${edge.linkId}`,
      source: String(edge.from),
      target: String(edge.to),
      markerEnd: { type: "arrowclosed" },
    })),
  };
}

// Dropping B (dragged) onto A (target) means "teach A before B".
export function classifyDrop(steps, draggedId, targetId) {
  if (draggedId === targetId) return { kind: "self", current: [] };
  const dragged = steps.find((step) => step.concept_id === draggedId);
  const current = dragged?.prerequisites || [];
  if (current.some((entry) => entry.concept_id === targetId)) return { kind: "already", current };
  if (!current.length) return { kind: "add", current };
  return { kind: "choose", current };
}

// Pending links for the right-hand panel, in the teaching order of the step they would change.
export function recommendations(steps) {
  return byPosition(steps).flatMap((step) =>
    (step.suggestions || []).map((entry) => ({
      linkId: entry.link_id,
      fromId: entry.concept_id,
      fromTitle: entry.title,
      toId: step.concept_id,
      toTitle: step.title,
      reason: entry.reason || "",
      crossSection: Boolean(entry.cross_section),
    })),
  );
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd /c/MAVIA/web-app && npm test`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /c/MAVIA
git add web-app/package.json web-app/package-lock.json web-app/src/learning-path/graphModel.js web-app/src/learning-path/graphModel.test.js
git commit -m "Add the learning path graph model with dagre layout and drop rules"
```

---

### Task 7: Graph-only path view with the details card (read-only behaviour)

**Files:**
- Create: `web-app/src/learning-path/PathGraph.jsx`
- Create: `web-app/src/learning-path/ConceptDetails.jsx`
- Create: `web-app/src/learning-path/pathGraph.css`
- Modify: `web-app/src/pages/LearningPathPage.jsx` (replace everything above `export default function LearningPathPage` with the new `MaterialPath`; keep `LearningPathPage` itself)

**Interfaces:**
- Consumes: `buildGraph` (Task 6); preview fields `reason`, `source_materials` (Task 3).
- Produces:
  - `PathGraph({steps, selectedId, onSelect(id|null), editable, onDrop(draggedId, targetId)})` — default export
  - `ConceptDetails({step, editable, onRemove(link, step), onClose})` — default export; renders nothing when `step` is null
  - `MaterialPath({path, topicId, editable, onPathData})` — same props as today; Task 8 adds editing inside it

After this task the editable screen shows the graph but cannot edit yet; Task 8 adds that. Do not merge between the two tasks.

- [ ] **Step 1: Confirm nothing else uses the helpers being removed**

Run: `cd /c/MAVIA/web-app && grep -rn "buildConceptMap\|findFloatingSteps\|ConceptMap\|LearnFirstPanel\|PathStats" src --include=*.jsx --include=*.js`
Expected: matches only in `src/pages/LearningPathPage.jsx`.

- [ ] **Step 2: Create `PathGraph.jsx`**

```jsx
// The learning path drawn as a prerequisite graph. Layout comes from
// graphModel.buildGraph; dragging is only turned on for the editable screen,
// and a drop is reported upward -- nothing here changes links itself.
import { useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { buildGraph } from "./graphModel";
import "./pathGraph.css";

function ConceptNode({ data }) {
  const { step, role } = data;
  const title = step.title || "Untitled concept";
  return (
    <div className={`pg-node ${role}`.trim()} title={title}>
      <Handle type="target" position={Position.Top} isConnectable={false} />
      <span className="pg-node-position">{step.position}</span>
      <span className="pg-node-title">{title}</span>
      {step.kind === "image" && <span className="pg-node-badge">Figure</span>}
      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
}

function LabelNode({ data }) {
  return <div className="pg-label">{data.text}</div>;
}

const NODE_TYPES = { concept: ConceptNode, label: LabelNode };

function Canvas({ steps, selectedId, onSelect, editable, onDrop }) {
  const layout = useMemo(() => buildGraph(steps, selectedId), [steps, selectedId]);
  const [nodes, setNodes, onNodesChange] = useNodesState(layout.nodes);
  const { getIntersectingNodes } = useReactFlow();

  useEffect(() => {
    setNodes(layout.nodes);
  }, [layout, setNodes]);

  function handleDragStop(_event, node) {
    const target = getIntersectingNodes(node).find(
      (other) => other.type === "concept" && other.id !== node.id,
    );
    // Positions are never kept: the box returns to its place in the layout.
    setNodes(layout.nodes);
    if (target) onDrop(Number(node.id), Number(target.id));
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={layout.edges}
      nodeTypes={NODE_TYPES}
      onNodesChange={onNodesChange}
      onNodeClick={(_event, node) => node.type === "concept" && onSelect(Number(node.id))}
      onPaneClick={() => onSelect(null)}
      onNodeDragStop={editable ? handleDragStop : undefined}
      nodesDraggable={editable}
      nodesConnectable={false}
      fitView
      minZoom={0.2}
    >
      <Background gap={24} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export default function PathGraph(props) {
  return (
    <div className="pg-canvas">
      <ReactFlowProvider>
        <Canvas {...props} />
      </ReactFlowProvider>
    </div>
  );
}
```

- [ ] **Step 3: Create `ConceptDetails.jsx`**

```jsx
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
```

- [ ] **Step 4: Create `pathGraph.css`**

```css
/* Learning path graph screen. Colours reuse the concept map's highlight
   palette (pipeline.css --cm-*) so selection reads the same as before. */
.pg-screen {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
.pg-screen.is-read-only { grid-template-columns: minmax(0, 1fr); }
.pg-graph-area { position: relative; }
.pg-canvas {
  height: 70vh;
  min-height: 420px;
  border: 1px solid var(--border, #dde5ee);
  border-radius: 12px;
  background: var(--bg, #f4f7fb);
}

.pg-node {
  width: 210px;
  min-height: 64px;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 0.2rem 0.5rem;
  padding: 0.5rem 0.65rem;
  border: 2px solid #1f2a37;
  border-radius: 10px;
  background: #fff;
  color: #1f2a37;
  font-size: 0.85rem;
  cursor: pointer;
}
.pg-node-position {
  display: inline-grid;
  place-items: center;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  background: #1f2a37;
  color: #fff;
  font-size: 0.72rem;
  font-weight: 700;
}
.pg-node-title {
  font-weight: 600;
  line-height: 1.25;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pg-node-badge {
  grid-column: 2;
  justify-self: start;
  padding: 0 0.4rem;
  border-radius: 999px;
  background: var(--accent-soft, #dfecfa);
  color: var(--accent, #1e5fa8);
  font-size: 0.7rem;
  font-weight: 700;
}
.pg-node.is-selected { box-shadow: 0 0 0 4px #1f2a37; }
.pg-node.is-needed { box-shadow: 0 0 0 4px #1d6a86; }
.pg-node.is-leads { box-shadow: 0 0 0 4px #2f7556; }
.pg-node.is-dimmed { opacity: 0.35; }
.pg-label {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted, #5c6b7c);
}

.pg-details {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 5;
  width: min(340px, calc(100% - 24px));
  max-height: calc(100% - 24px);
  overflow: auto;
  padding: 0.9rem;
  border: 1px solid var(--border-strong, #c6d2e0);
  border-radius: 12px;
  background: #fff;
  box-shadow: var(--shadow-sm, 0 4px 14px rgba(11, 42, 74, 0.06));
}
.pg-details-head { display: flex; justify-content: space-between; gap: 0.5rem; align-items: start; }
.pg-details-head h3 { margin: 0; font-size: 1rem; }
.pg-details-text { white-space: pre-line; font-size: 0.88rem; }
.pg-details-sources { font-size: 0.8rem; color: var(--muted, #5c6b7c); }
.pg-details h4 { margin: 0.75rem 0 0.35rem; font-size: 0.85rem; }
.pg-details-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.5rem; }
.pg-details-list li { display: flex; justify-content: space-between; gap: 0.5rem; align-items: start; }
.pg-details-list small { display: block; color: var(--muted, #5c6b7c); }

@media (max-width: 900px) {
  .pg-screen { grid-template-columns: minmax(0, 1fr); }
}
```

- [ ] **Step 5: Replace the list/map code in `LearningPathPage.jsx`**

In `web-app/src/pages/LearningPathPage.jsx`, replace everything from the first line down to (not including) `export default function LearningPathPage()` with:

```jsx
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

```

`LearningPathPage` below it stays as is (it already imports nothing else from this file's removed code). `topicId` and `onPathData` are unused until Task 8; leave them in the signature.

- [ ] **Step 6: Build and run the unit tests**

Run: `cd /c/MAVIA/web-app && npm test && npm run build`
Expected: tests PASS; build succeeds with no unresolved imports.

- [ ] **Step 7: Look at it in the browser**

Start both servers (backend: `cd /c/MAVIA/backend && python manage.py runserver`; frontend: `cd /c/MAVIA/web-app && npm run dev`), sign in as a teacher, open topic **Solid, Liquid and Gas** → review step 5 (Learning path). Check: Matter above Solid/Liquid/Gas on one row with arrows; unlinked concepts in the "Not linked yet" row; clicking a box highlights neighbours and opens the details card with text and source files; Close and Escape clear it; zoom and fit controls work.

- [ ] **Step 8: Commit**

```bash
cd /c/MAVIA
git add web-app/src/learning-path/PathGraph.jsx web-app/src/learning-path/ConceptDetails.jsx web-app/src/learning-path/pathGraph.css web-app/src/pages/LearningPathPage.jsx
git commit -m "Replace the learning path list with a prerequisite graph and details card"
```

---

### Task 8: Drag-and-drop editing, recommendations panel, confirm and undo

**Files:**
- Modify: `web-app/src/api.js` (add `movePathLink`, `restorePathLinks`)
- Create: `web-app/src/learning-path/ConfirmDialog.jsx`
- Create: `web-app/src/learning-path/RecommendationsPanel.jsx`
- Create: `web-app/src/learning-path/UndoBar.jsx`
- Modify: `web-app/src/learning-path/pathGraph.css` (append panel, dialog, undo styles)
- Modify: `web-app/src/pages/LearningPathPage.jsx` (`MaterialPath`)
- Modify: `web-app/src/pages/TopicDetailPage.jsx` (`LearningPathReviewPanel`: load error + Retry)

**Interfaces:**
- Consumes: `classifyDrop`, `recommendations` (Task 6); `PathGraph`, `ConceptDetails` (Task 7); `addPathLink(nodeId, prerequisiteId, dependentId)`, `decidePathLink(nodeId, linkId, status)` (existing, `api.js`); endpoints and `undo` field (Tasks 4–5).
- Produces:
  - `movePathLink(nodeId, prerequisiteConceptId, dependentConceptId) -> Promise<preview & {undo}>`
  - `restorePathLinks(nodeId, undo) -> Promise<preview>`
  - `ConfirmDialog({title, message, actions: [{label, primary, onClick}], cancelLabel = "Cancel", error, busy, onCancel})`
  - `RecommendationsPanel({steps, busy, onAccept(item), onReject(item)})`
  - `UndoBar({message, error, busy, onUndo, onClose})`, `UNDO_SECONDS = 10`

- [ ] **Step 1: Add the API calls**

In `web-app/src/api.js`, after `decidePathLink`, add:

```js
export function movePathLink(nodeId, prerequisiteConceptId, dependentConceptId) {
  return request(`/learning-path/topics/${nodeId}/links/move/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prerequisite_concept_id: prerequisiteConceptId,
      dependent_concept_id: dependentConceptId,
    }),
  });
}

// Puts back what a link change's `undo` record describes.
export function restorePathLinks(nodeId, undo) {
  return request(`/learning-path/topics/${nodeId}/links/restore/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ undo }),
  });
}
```

- [ ] **Step 2: Create `ConfirmDialog.jsx`**

```jsx
// Every change on the learning path is confirmed here first. A refusal from
// the server (a loop, a link that no longer exists) is shown in the dialog,
// which stays open so the teacher can read it.
import { useEffect } from "react";

export default function ConfirmDialog({ title, message, actions = [], cancelLabel = "Cancel", error, busy, onCancel }) {
  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && !busy && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onCancel]);

  return (
    <div className="pg-dialog-backdrop">
      <section className="pg-dialog" role="alertdialog" aria-modal="true" aria-labelledby="pg-confirm-title">
        <h3 id="pg-confirm-title">{title}</h3>
        {message && <p>{message}</p>}
        {error && <p className="pg-dialog-error" role="alert">{error}</p>}
        <div className="pg-dialog-actions">
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={onCancel}>
            {cancelLabel}
          </button>
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              className={`btn ${action.primary ? "btn-primary" : "btn-secondary"}`}
              disabled={busy}
              onClick={action.onClick}
            >
              {action.label}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Create `UndoBar.jsx`**

```jsx
// Shown for ten seconds after each confirmed change. A failed undo stays up
// with its reason until dismissed.
import { useEffect } from "react";

export const UNDO_SECONDS = 10;

export default function UndoBar({ message, error, busy, onUndo, onClose }) {
  useEffect(() => {
    if (error) return undefined;
    const timer = setTimeout(onClose, UNDO_SECONDS * 1000);
    return () => clearTimeout(timer);
  }, [message, error, onClose]);

  return (
    <div className="pg-undo" role="status">
      <span>{error ? `Couldn't undo: ${error}. Refresh to see the current path.` : message}</span>
      {!error && (
        <button type="button" className="btn btn-small btn-secondary" disabled={busy} onClick={onUndo}>
          Undo
        </button>
      )}
      <button type="button" className="pg-undo-close" aria-label="Dismiss" onClick={onClose}>
        ×
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Create `RecommendationsPanel.jsx`**

```jsx
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
```

- [ ] **Step 5: Append the panel, dialog and undo styles to `pathGraph.css`**

```css
.pg-panel {
  max-height: 70vh;
  overflow: auto;
  padding: 0.9rem;
  border: 1px solid var(--border, #dde5ee);
  border-radius: 12px;
  background: #fff;
}
.pg-panel h4 { margin: 0 0 0.6rem; font-size: 0.95rem; }
.pg-cards { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.6rem; }
.pg-card {
  display: grid;
  gap: 0.35rem;
  padding: 0.65rem;
  border: 1px solid var(--border, #dde5ee);
  border-radius: 10px;
  font-size: 0.85rem;
}
.pg-card p { margin: 0; color: var(--muted, #5c6b7c); }
.pg-card-actions { display: flex; gap: 0.4rem; }
.pg-flag {
  justify-self: start;
  padding: 0 0.4rem;
  border-radius: 999px;
  background: #fdf1dc;
  color: var(--warning, #9a5b00);
  font-size: 0.72rem;
  font-weight: 700;
}

.pg-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  background: rgba(18, 33, 47, 0.35);
}
.pg-dialog {
  width: min(460px, calc(100vw - 32px));
  padding: 1.1rem;
  border-radius: 12px;
  background: #fff;
  box-shadow: var(--shadow, 0 18px 45px rgba(11, 42, 74, 0.12));
}
.pg-dialog h3 { margin: 0 0 0.5rem; font-size: 1.05rem; }
.pg-dialog-error { color: var(--danger, #c0392b); }
.pg-dialog-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem; }

.pg-undo {
  position: fixed;
  left: 50%;
  bottom: 24px;
  z-index: 60;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  max-width: calc(100vw - 32px);
  padding: 0.6rem 0.9rem;
  border-radius: 10px;
  background: #12212f;
  color: #fff;
}
.pg-undo-close { border: 0; background: transparent; color: #fff; font-size: 1.1rem; cursor: pointer; }
```

- [ ] **Step 6: Wire editing into `MaterialPath`**

In `web-app/src/pages/LearningPathPage.jsx`, change the imports at the top to:

```jsx
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { addPathLink, decidePathLink, fetchTopicLearningPath, movePathLink, restorePathLinks } from "../api";
import ConceptDetails from "../learning-path/ConceptDetails";
import ConfirmDialog from "../learning-path/ConfirmDialog";
import { classifyDrop } from "../learning-path/graphModel";
import PathGraph from "../learning-path/PathGraph";
import RecommendationsPanel from "../learning-path/RecommendationsPanel";
import UndoBar from "../learning-path/UndoBar";
```

Replace the whole `MaterialPath` function with:

```jsx
export function MaterialPath({ path, topicId = null, editable = false, onPathData = null }) {
  const steps = path.steps || [];
  const canEdit = editable && topicId !== null;
  const [selectedId, setSelectedId] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [confirmError, setConfirmError] = useState("");
  const [busy, setBusy] = useState(false);
  const [undo, setUndo] = useState(null);

  const selected = steps.find((step) => step.concept_id === selectedId) || null;
  const titleOf = (id) => steps.find((step) => step.concept_id === id)?.title || "Untitled concept";
  const linkCount = steps.reduce((count, step) => count + (step.prerequisites || []).length, 0);
  const clearSelection = useCallback(() => setSelectedId(null), []);
  const closeUndo = useCallback(() => setUndo(null), []);
  const closeConfirm = useCallback(() => setConfirm(null), []);

  useEffect(() => {
    if (selectedId !== null && !selected) setSelectedId(null);
  }, [selectedId, selected]);

  function ask(next) {
    setConfirmError("");
    setConfirm(next);
  }

  // Runs a confirmed change; on success the preview is replaced and Undo offered.
  async function apply(call, message) {
    setBusy(true);
    setConfirmError("");
    try {
      const data = await call();
      if (onPathData) onPathData(data);
      setConfirm(null);
      setUndo(data.undo?.length ? { message, records: data.undo, error: "" } : null);
    } catch (error) {
      setConfirmError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleUndo() {
    if (!undo) return;
    setBusy(true);
    try {
      const data = await restorePathLinks(topicId, undo.records);
      if (onPathData) onPathData(data);
      setUndo(null);
    } catch (error) {
      setUndo((current) => current && { ...current, error: error.message });
    } finally {
      setBusy(false);
    }
  }

  // Dropping B (dragged) onto A (target): teach A before B.
  function handleDrop(draggedId, targetId) {
    const b = titleOf(draggedId);
    const a = titleOf(targetId);
    const drop = classifyDrop(steps, draggedId, targetId);
    if (drop.kind === "self") return;
    if (drop.kind === "already") {
      ask({ title: `${a} is already taught before ${b}.`, actions: [], cancelLabel: "OK" });
      return;
    }
    const add = () => apply(() => addPathLink(topicId, targetId, draggedId), `${a} is now taught before ${b}.`);
    if (drop.kind === "add") {
      ask({ title: `Teach ${a} before ${b}?`, actions: [{ label: "Yes", primary: true, onClick: add }] });
      return;
    }
    const current = drop.current.map((entry) => entry.title).join(", ");
    ask({
      title: `${b} already comes after ${current}. What do you want?`,
      actions: [
        { label: `Add ${a} as another prerequisite`, onClick: add },
        {
          label: `Move: ${a} replaces ${current}`,
          primary: true,
          onClick: () => apply(() => movePathLink(topicId, targetId, draggedId), `${b} now comes only after ${a}.`),
        },
      ],
    });
  }

  function handleAccept(item) {
    ask({
      title: `Teach ${item.fromTitle} before ${item.toTitle}?`,
      actions: [{
        label: "Yes",
        primary: true,
        onClick: () => apply(
          () => decidePathLink(topicId, item.linkId, "approved"),
          `${item.fromTitle} is now taught before ${item.toTitle}.`,
        ),
      }],
    });
  }

  function handleReject(item) {
    ask({
      title: `Don't teach ${item.fromTitle} before ${item.toTitle}?`,
      message: "It won't be suggested again.",
      actions: [{
        label: "Yes",
        primary: true,
        onClick: () => apply(
          () => decidePathLink(topicId, item.linkId, "rejected"),
          `${item.fromTitle} → ${item.toTitle} won't be suggested again.`,
        ),
      }],
    });
  }

  function handleRemove(link, step) {
    ask({
      title: `${link.title} no longer has to come before ${step.title}?`,
      message: "It won't be suggested again.",
      actions: [{
        label: "Yes",
        primary: true,
        onClick: () => apply(
          () => decidePathLink(topicId, link.link_id, "rejected"),
          `${link.title} no longer has to come before ${step.title}.`,
        ),
      }],
    });
  }

  return (
    <section className="path-material">
      <header className="path-material-head">
        <h3>{path.topic_title || "Learning path"}</h3>
      </header>

      {linkCount === 0 && steps.length > 0 && (
        <p className="muted-text path-ordering-note">
          Ordered as your lesson files present it. Nothing has to be learned before anything else yet
          {canEdit ? " — drag a concept onto the one that must come before it" : ""}.
        </p>
      )}

      {editable && path.diagnostics?.changed_since_publish && (
        <p className="path-changed-note" role="status">
          You changed what must be learned first after the last publish. Students still follow
          the published path until you publish again.
        </p>
      )}

      <div className={canEdit ? "pg-screen" : "pg-screen is-read-only"}>
        <div className="pg-graph-area">
          <PathGraph
            steps={steps}
            selectedId={selectedId}
            onSelect={setSelectedId}
            editable={canEdit && !busy}
            onDrop={handleDrop}
          />
          <ConceptDetails step={selected} editable={canEdit} onRemove={handleRemove} onClose={clearSelection} />
        </div>
        {canEdit && (
          <RecommendationsPanel steps={steps} busy={busy} onAccept={handleAccept} onReject={handleReject} />
        )}
      </div>

      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          actions={confirm.actions}
          cancelLabel={confirm.cancelLabel}
          error={confirmError}
          busy={busy}
          onCancel={closeConfirm}
        />
      )}

      {undo && (
        <UndoBar message={undo.message} error={undo.error} busy={busy} onUndo={handleUndo} onClose={closeUndo} />
      )}
    </section>
  );
}
```

- [ ] **Step 7: Show a Retry when the path fails to load (spec section 7)**

In `web-app/src/pages/TopicDetailPage.jsx`, `LearningPathReviewPanel` (around line 3393):

Add two state hooks after `const [loadingPath, setLoadingPath] = useState(true);`:

```jsx
  const [loadError, setLoadError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
```

In `loadPath`, clear the error when starting and keep it when failing — replace the body of `loadPath` with:

```jsx
      setLoadingPath(true);
      setLoadError("");
      try {
        const data = await fetchTopicLearningPath(topicId);
        if (!cancelled) setPathData(data);
      } catch (err) {
        if (!cancelled) {
          setLoadError(err.message);
          onError(err.message);
        }
      } finally {
        if (!cancelled) setLoadingPath(false);
      }
```

and change that effect's dependency list from `[topicId]` to `[topicId, reloadKey]`.

Replace the empty-state block `{!loadingPath && !paths.length && (` … `)}` (around line 3554) with:

```jsx
      {!loadingPath && loadError && !pathData && (
        <div className="error-banner" role="alert">
          Couldn't load the learning path: {loadError}{" "}
          <button type="button" className="btn btn-small btn-secondary" onClick={() => setReloadKey((key) => key + 1)}>
            Retry
          </button>
        </div>
      )}

      {!loadingPath && !loadError && !paths.length && (
        <div className="review-queue-empty">
          No path yet. Each step is a concept, so confirm the learning objects in
          your lesson files first — grouping is what turns them into concepts.
        </div>
      )}
```

Add `web-app/src/pages/TopicDetailPage.jsx` to this task's commit.

- [ ] **Step 8: Build and run the unit tests**

Run: `cd /c/MAVIA/web-app && npm test && npm run build`
Expected: tests PASS; build succeeds.

- [ ] **Step 9: Walk through every action in the browser**

With both servers running, open topic **Solid, Liquid and Gas** → review step 5, and check each, noting pass/fail:
1. Right panel lists recommendations with reasons; the graph takes about three quarters of the width.
2. Drag **As a general rule** onto **Gas** → "Teach Gas before As a general rule?" → Yes → arrow appears; undo bar shows; **Undo** removes it.
3. Drag **Solid** onto **Liquid** (Solid already after Matter) → choose dialog → **Move** → Matter→Solid gone, Liquid→Solid present; **Undo** restores both.
4. Same drag → **Add** → Solid has two arrows in.
5. Drag **Solid** onto **Matter** → "Matter is already taught before Solid." [OK].
6. Drag **Matter** onto **Solid** after step 4 → the dialog shows the loop message and stays open.
7. Accept one recommendation → it leaves the panel and becomes an arrow; **Undo** returns it to the panel.
8. Reject one → it leaves the panel; **Undo** returns it.
9. Click **Solid** → details card → **Remove** a prerequisite → confirm → arrow gone; **Undo** restores.
10. Wait 10 s after a change → undo bar disappears.
11. Review Focus 5: the long figure title ("Particle arrangement in solids, liquids, and gases" / "The main parts of a flower involved in reproduction") shows on two lines in its box, full on hover and in the details card; boxes do not overlap.
12. Open the standalone Learning Path page for the same topic → graph only, no panel, no dragging, no Remove.
13. Repeat 2 and 7 on topic **Reproduction Among Flowering Plants**.
14. Stop the backend and reload review step 5 → "Couldn't load the learning path: …" with **Retry**; start the backend, press Retry → the graph appears.

Fix anything that fails before committing.

- [ ] **Step 10: Commit**

```bash
cd /c/MAVIA
git add web-app/src/api.js web-app/src/learning-path/ConfirmDialog.jsx web-app/src/learning-path/RecommendationsPanel.jsx web-app/src/learning-path/UndoBar.jsx web-app/src/learning-path/pathGraph.css web-app/src/pages/LearningPathPage.jsx web-app/src/pages/TopicDetailPage.jsx
git commit -m "Edit the learning path by drag and drop with confirm, undo and recommendations"
```

---

### Task 9: Full regression run and log

**Files:**
- Modify: `docs/AGENT_LOG.md`

**Interfaces:**
- Consumes: everything above.
- Produces: a log entry; no code.

- [ ] **Step 1: Run the backend suites that touch the learning path**

Run: `cd /c/MAVIA/backend && python manage.py test learning_path lessons adaptive -v 1`
Expected: all PASS. If a `lessons` or `adaptive` test fails, check whether it planted derived `ConceptPrerequisite` rows and then opened `GET /api/learning-path/topics/<id>/`; if so, wrap that GET in a `patch.object(publishing.criteria, "decide_pairs", ...)` returning the planted decisions (as `TopicFixture._derive` does), and re-run.

- [ ] **Step 2: Run the frontend checks**

Run: `cd /c/MAVIA/web-app && npm test && npm run build`
Expected: PASS and a successful build.

- [ ] **Step 3: Add an entry to `docs/AGENT_LOG.md`**

Append under the log's latest-date heading (create `## 2026-09-29` if absent):

```markdown
- **Learning path review screen is graph-first** (branch `learning-path-graph-screen`,
  spec `docs/superpowers/specs/2026-09-29-learning-path-graph-screen-design.md`).
  List view removed; React Flow + dagre graph at 75% with recommended links at 25%;
  drag B onto A = A before B (add or move when B already has prerequisites); every
  change confirmed and undoable for 10 s via `links/restore/`; links now derived when
  the screen opens and derived link ids are stable. Old `.cm-*`, `.lf-*`, `.path-step*`
  and `.ps-*` rules in `web-app/src/styles/pipeline.css` are now unused and can be
  deleted in a cleanup pass. — Claude Code, 2026-09-29
```

- [ ] **Step 4: Commit**

```bash
cd /c/MAVIA
git add docs/AGENT_LOG.md
git commit -m "Log the graph-first learning path screen"
```
