# MAVIA — shared agent log

A running record of what each coding agent changed, and the place where agents
leave notes for each other. The user switches between agents (Claude Code and
Codex), so this file is the handover.

Read `docs/PROJECT_CONTEXT.md` first for what the project is and how it works.
This file is only *what happened and what is pending*.

## How to use this file

- **Append at the bottom.** Newest entry last. Never rewrite or delete someone
  else's entry; if they got something wrong, say so in your own entry.
- **Log a session, not every command.** One entry per working session, written
  when you finish or when you hand back.
- **Record what would surprise the next agent**: decisions you made on the
  user's behalf, things you deliberately did not do, and anything you changed
  in the live database.
- **Open questions go in `## Open threads`** near the bottom, and are removed by
  whoever resolves them (noting the resolution in their entry).
- Be honest about what you did not verify. "Tests pass" and "I reasoned it
  through" are different claims.

### Entry template

```markdown
### YYYY-MM-DD — <agent> — <one-line summary>

**Branch / commits:** jean-latest, <sha>..<sha>
**Tests:** <what you ran, and the result>
**Changed:** <files or areas, and why>
**Live database:** <anything you changed, or "untouched">
**Decisions I made:** <choices the user did not explicitly approve, and the cost if wrong>
**Not done / watch out:** <what you left, and what could bite>
```

---

## Log

### 2026-09-21 — Claude Code — concept bundles land; run-through fixes; docs for handover

**Branch / commits:** `jean-latest`, `f7596d7..c769e3e` (57 commits over several
sessions). Merge-era code preserved on `current-with-merge-function` (pushed).

**Tests:** `python manage.py test -v 1` → 796 passing. Gold paths unchanged:
topic 62 10/10, topic 79 4/8 with the four recorded `known_missing` gaps, no
forbidden edges, both orders matching. `npm run build` clean.

**Changed (six pieces of work):**

1. **Grouping merges + revised learning-path criteria** (spec
   `2026-09-17-grouping-merge-and-learning-path-design.md`). RefD key-term
   reference replaced name-to-text similarity; Examples concepts excluded and
   ordered last; numbered labels normalised; head-word mentions and section
   containment added; cross-section cap removed; uploaded PDFs now deleted with
   their rows (436 orphans → 0). Gold went 0/10 and 1/8 → 10/10 and 4/8.
2. **Concept bundles** (spec `2026-09-20-concept-bundles-design.md`, plan
   `2026-09-20-concept-bundles.md`). The manual merge step is gone; a concept
   holds an ordered bundle per PDF, formed automatically when another PDF
   corroborates it, with a card for uncertain cases. Version roles moved onto
   the group; generated versions are written per object; the review screen
   shows one block per PDF with Move out / Move to… / ↑ / ↓.
3. **Fixes from the user's real run-through (same day):** single-object bundles
   keep their own title (three concepts were all being named "Matter");
   overlapping row controls; images need label corroboration before grouping
   automatically; the figure-description prompt rewritten as ROLE / TASK /
   CONTEXT / FORMAT with a no-preamble rule, 2–4 sentences (6 max), and an
   instruction not to restate the lesson text it is given as context.

**Live database:** backed up to `db.sqlite3.pre-repair.20260921`, then:
12 concept labels corrected in place by a new `repair_bundle_labels` command;
topic 152's over-grouped figure concept split so each figure stands alone; two
`LearningObjectMatchSuggestion` rows deleted because a repair script had
recorded its own splits as *teacher* decisions. Figure descriptions were **not**
regenerated. Neither topic is published.

**Decisions I made:**

- Kept the three-criterion vote and its paper lineage rather than replacing the
  approach, because the manuscript commits to it. Cost if wrong: the criteria
  remain weaker on process-type lessons than a different method might be.
- Stopped calibrating after two runs at 14/18 required edges and recorded the
  four gaps in the fixtures instead of tuning them away. Cost if wrong: the
  adaptive engine has no remediation link for those four.
- A rejected suggestion, a locked label and a teacher-provenance role outrank
  every automatic path. Cost if wrong: a teacher has to redo a connection
  manually that the system could have made.
- Bundles are derived, not stored (no new table). Cost if wrong: every consumer
  must go through one helper, which is a convention, not a constraint.
- A concept takes its heading as a name only for a 2+ object bundle. Cost if
  wrong: a single-object concept with a poor title keeps it.

**Not done / watch out:**

- **Publishing is blocked by the environment**, not by code:
  `Edge TTS failed: Cannot connect to host speech.platform.bing.com`. The gate
  now refuses rather than shipping a silent lesson.
- **31 empty `LearningObjectGroup` rows** remain from deleted materials. The
  delete endpoint never calls `remove_empty_learning_object_groups`. This
  matters because a stale group carries `version_selection`, so a re-upload can
  inherit a role or a locked name for text that no longer exists. Fix proposed,
  awaiting the user.
- **Two consumers broke silently** when PDF-supplied `LessonVariant` rows were
  retired: the publish gate and audio generation. Both fixed, both invisible to
  a green suite. If you change version storage, check `topic_publish.py` and
  `audio_generator.py` by hand.
- The chatter strip in `image_describer.py` deliberately **under-reaches**:
  some chatter survives rather than risk deleting a real sentence. Keep that
  direction if you touch it.
- No frontend test runner, so the bundle controls have no automated coverage.

### 2026-09-21 — Claude Code — a read stops deciding roles; Gemma's broken JSON recovered; TTS retries a lossy link; whole bundles reach the path and the review screens

**Branch / commits:** `jean-latest`, uncommitted on top of `2d3eacd`. The user
asked for the log entry only, so nothing is staged or committed.

**Tests:** `python manage.py test -v 1` → **827 passing** (800 before, plus 27
new). Gold paths re-run on their own: topic 62 and topic 79 both `ok`, so
10/10 and 4/8 with the recorded `known_missing` gaps, no forbidden edges, both
orders matching. `npm run build` clean.

**Changed (three pieces of work):**

1. **Step 1 no longer classifies.** The user noticed a concept already showing
   Simplified/Elaborated in the grouping step. It was real: the review payload
   calls `assign_group_versions` on every load, and that call *wrote* a
   readability-derived role (provenance `heuristic`) into `version_selection`
   before Gemma or the teacher had ruled on anything. Now only a run that was
   asked to classify writes a role; a read still returns the proposal so a
   caller could show it as a suggestion, but records nothing. The role badge
   and its `bundleRoleLabel` helper are gone from the step-1 concept cards,
   and the dead CSS from both mirrored stylesheets.

   **One regression this would have caused, caught by a test and fixed:** when
   a teacher moves a bundle into a slot another bundle holds, the displaced one
   is not meant to become an Extra — it takes the primary slot its wording
   actually fits (decided 2026-09-20). That re-derivation was being *persisted
   by the next page load*. With reads inert it would have stayed EXTRA and its
   wording would have been regenerated instead of used. The re-derivation now
   happens in `assign_source_to_slot`, with the decision that causes it.

2. **Gemma's unparseable reply is recovered.** Publishing topic 152 failed on
   "Comparing the Three States" with "Gemma did not return valid JSON", three
   attempts, every time. Reproduced 3/3 with an identical mechanism: both
   variants come back correct and inside their word limits, but the model
   closes the `elaborated` string with a typographic right quote (U+201D)
   instead of `"`. The string never terminates, the constrained decoding never
   sees the object close, generation runs to `num_predict` (`done_reason:
   length`) and the tail fills with the prompt's own word limits echoed back
   ("52 words. 48 words. 27 words." repeating). `_parse_response` now repairs
   the *delimiters* and keeps the result only when it then parses; the model's
   own wording, including a curly apostrophe mid-sentence, is untouched. A
   reply with genuine curly quotes parses first time and never reaches the
   repair. Verified against the live model on the real object: recovered on
   the first attempt, 17 and 25 words against limits of 27 and 48.

3. **Edge TTS retries a dropped connection.** The host was never blocked. A
   10-shot probe put the TLS handshake at **2 successes in 10** on the user's
   link, with the other 8 reset immediately (WinError 10054). Because
   `_synthesize_text_to_mp3_with_edge` made a single attempt and raised, one
   dropped clip aborted the publish for every clip after it -- which is why
   the same run kept failing while the media directory filled up (293 files in
   `audio_versions`, 21 in `audio_lessons`; material 28's playlist was already
   10/10). Each clip is now attempted up to `EDGE_TTS_ATTEMPTS` times (default
   20, `EDGE_TTS_RETRY_DELAY` 1.5s between), and a partial file from a dropped
   stream is deleted before the retry so a truncated clip cannot be mistaken
   for a finished one. Verified against the live link: 3 of 3 clips
   synthesized, 5-9s each, 4 retries consumed across them.

4. **The published learning path served only a concept's bundle lead.**
   Found by answering a question from the user -- "are the bundled learning
   objects really included in the literal learning path?" They are not, and it
   was two bugs in `learning_path/services/published.py::_versions`:

   - Normal was read as `representative.content`, which is the bundle's *lead*
     and drops every object after it. On the real topic, the concept
     "Comparing the Three States" served **77 characters of 326** -- object
     298 alone -- while Volume, Particle arrangement and Flow appeared nowhere
     in the payload.
   - Simplified and Elaborated were read from `LessonVariant` rows only, and a
     version another PDF *supplies* has no such row by design. So that PDF's
     wording never reached the path at all; a generated variant was served
     instead, including one generated before the teacher connected the two
     bundles and never invalidated by the regroup.

   **15 of 22 concepts across the two live topics were affected -- all 10 of
   topic 169.** The lesson package (`course/services._build_chunk`) had it
   right all along, so the two readers disagreed: for the same concept the
   package served 326 / 698 / 503 characters where the path served 77 / 66 /
   105.

   `_versions` now reads through `normal_bundle_for` and `version_bundles`,
   and imports `_generated_versions` / `_version_from_segments` from
   `course.services` rather than copying them -- the rule that a generated
   version short of its bundle is reported missing instead of half-served is
   safety-critical and must not exist in two places. Each version also now
   carries `segments` alongside `text` and `audio_url`: a four-object version
   has four clips, and a single `audio_url` is only the first of them, so a
   reader playing it alone would give a learner a quarter of the version with
   no way to tell. The two documented keys are unchanged, so existing readers
   are unaffected.

   Verified on the live database: **0 concepts short** on both topics, and
   objects 299, 300, 301, 316 and 317 -- previously reachable through no
   learner-facing path at all -- now appear.

5. **The final-review screen described a concept as "lead + leftovers".**
   The user could not trace whether the screen was behaving correctly, which
   is how this was found. It rendered the concept's representative object with
   its own text as "Normal", and every other member as "Other variation" --
   the pre-bundle model. Three consequences, all visible on topic 152:

   - Normal was the lead's text, so three of the four objects of "Comparing
     the Three States" were shown as variations of themselves.
   - A generated version showed only the lead's segment -- one of the four
     that had actually been written and were sitting in the database.
   - A version a PDF supplies was printed in full AND again object by object,
     so every word appeared twice with nothing saying they were the same.

   The payload now carries **Normal as a slot of its own** (it was absent
   entirely, which is why the screen fell back to the lead), gathers **every
   segment** of a generated version across the Normal bundle, refuses to offer
   a generated version **short of its bundle**, and tells each slot's `source`
   (`pdf`/`generated`), its material and the objects it is made of -- a
   generated segment carrying the wording that was *written*, not the object
   it was written from. The screen renders one block per role; every object
   appears exactly once, under the role it plays. The header counts versions
   and files instead of objects, so "6 variations" became "3 versions from
   2 files".

6. **Step 1's row controls were named after the data, not the decision.**
   "Move out" and "Move to..." both read as "move" while one makes a new
   concept and the other joins an existing one, and the reorder arrows sat
   beside them looking as though they changed concepts too. The four controls
   are now two labelled groups -- **Wrong concept?** (Give it its own concept
   / Move into another concept...) and **Order in this file** (up/down) -- and
   the panel's intro says plainly that the arrows never move an object between
   concepts. `aria-disabled` rather than `disabled`, the aria-labels naming the
   object and its file, and the focus-restore refs are all unchanged.

**Live database:** **untouched.** Every query was a read; the two model probes
went straight to Ollama and to edge-tts without going through the ORM. Checked
afterwards: **0 groups carry a `heuristic` role**, so no repair is needed for
roles written by past page loads.

**What I found in the live database (2026-09-21, after the user re-uploaded):**

- Topics 152 and 169, two PDFs each, 50 learning objects, 31 groups, **none
  empty** — the re-upload refilled the 31 empty ones from last session. The
  delete-endpoint bug behind them is still there; the stale-`version_selection`
  risk showed up for real, with group 326 inheriting its old `auto_label`.
- Topic 169: all 10 concepts paired across both PDFs, every role
  `llm_validated`. **0 concepts missing a version** — it is content-complete
  and only TTS blocks it.
- Topic 152: only Solid/Liquid/Gas are cross-PDF. **4 suggestion cards are
  pending the teacher** (ids 145–148), all heading-object/figure pairs that
  extraction split inside one PDF.
- `ConceptPrerequisite` and `LearningPathStep` are both 0: neither topic has
  ever been published, so the derived path has still never been compared with
  the gold standard.

**Decisions I made:**

- Scoped the role change to the *write*, not the computation: a read still
  returns the proposal. Cost if wrong: a caller could still surface a
  heuristic role as though it were decided.
- Put the displacement re-derivation in `assign_source_to_slot` rather than
  keeping any write on the read path. Cost if wrong: two teacher roles written
  straight to the record (not reachable through the endpoint) would no longer
  be resolved in storage, only in the returned value.
- Repaired the JSON delimiters rather than loosening the grounding checks or
  rewriting the prompt. The prompt is content generation, which is the
  groupmate's area, and the model's output was *correct* — only its envelope
  was malformed. Cost if wrong: a reply needing its own quotes rewritten is
  still refused, which is the deliberate under-reach direction.
- Changed three existing tests that built their state through a read
  (`test_a_pdf_supplied_version_stores_no_copied_text`,
  `test_a_displaced_automatic_role_keeps_its_own_provenance`,
  `test_two_teacher_roles_for_one_slot_are_settled_by_recency`) plus
  `BundleGenerationTests.setUp`. Each now classifies first, which is how
  production reaches that state, and each carries a dated comment saying why.

**Not done / watch out:**

- **`backend/course/variant_generator.py` is one of the two files the user
  keeps uncommitted work in.** It was clean in git when I edited it. The new
  tests went into a new file, `course/test_variant_parsing.py`, so
  `course/tests.py` still holds only the user's own changes. Nothing staged.
- **The Edge TTS host is lossy, not blocked — I got this wrong at first.**
  Earlier in this session I read the resets as a per-hostname block, because
  `bing.com`, `google.com` and `api.github.com` completed while
  `speech.platform.bing.com` and `huggingface.co` were reset. Repeating the
  probe 10 times showed 2 successes, so the host is reachable and the link
  just drops most handshakes. The retry above is the fix; the earlier
  network-switching advice was chasing the wrong thing.
- `AUDIO_TTS_PROVIDER=auto` falls back to Windows SAPI and was verified
  working here (95,710-byte wav), but **the user chose to keep the Edge voice
  and .mp3 output** rather than change the audio the manuscript describes. Do
  not switch the provider without asking them.
- The retry defaults (20 attempts, 1.5s apart) are sized for a link at roughly
  20% success. On a healthy connection the first attempt wins and nothing
  changes; on a dead one a clip now takes ~30s to give up instead of ~1s.
- The four pending suggestions on topic 152 were ruled on by the teacher
  after this entry was first written: 147, 148 and 145 accepted, 146 rejected.
  Required edges on topic 152 went 6/10 → 9/10 and 20 concepts became 12. One
  **forbidden** edge appeared with it (`Solid → Gas`); see
  `docs/learning_path_revision_2026-09-17.md` for the evidence and why a
  threshold will not fix it.
- **A published step is still titled after its bundle's lead**, not the
  concept. The step for "Comparing the Three States" is titled "Shape". I
  deliberately did not change it with the versions fix -- it is the same
  family of defect (the path speaking for a bundle through its lead) but a
  separate change, and `title` is part of the documented payload shape. The
  review screens no longer have this problem; only the published payload does.
- **The two "Changing From One State to Another" concepts are still split**
  (objects 318 and 319, both from the same PDF). No card was raised because
  the other PDF has no matching section, so they need **Move into another
  concept...** by hand. That is the last required edge missing from topic 152.
- The review screens now have **no automated coverage of their rendering** --
  the payload is tested, the JSX is not, because there is still no frontend
  test runner.
- **`course/services.py` now has two importers of its private helpers**
  (`_generated_versions`, `_version_from_segments`). That was the deliberate
  choice over duplicating the half-served rule, but if those helpers move,
  `learning_path/services/published.py` moves with them.

### 2026-09-22 — Claude Code — parallel concepts stop borrowing each other's words; a gold fixture that holds the pipeline's own grouping

**Branch / commits:** `jean-jure-latest`, uncommitted on top of `3820565`.
Nothing staged or committed.

**Tests:** `python manage.py test -v 1` → **845 passing** (837 before, plus 8).
`test_gold_paths` runs three lessons now and all three are `ok`. The new one was
confirmed **failing before the fix**, on
`forbidden_accepted: [["solid","gas"]]`, which is why it exists.

**Live database: untouched.** Every number below was re-derived read-only by
running `concepts_for_topic` + `criteria.decide_pairs` — which is exactly what
`publish_learning_path` does, so these *are* the numbers a republish would
store. I did not republish 152/163: the stored rows are stale, but re-deriving
answers the question without writing, and publishing is the teacher's action.

**What was wrong, and what I did about it**

The task was that edges are accepted on evidence that is a single ordinary
English word, with `Solid → Gas` (topic 152) and 20 cross-lesson edges
(topic 163) as the live consequences. The recorded candidate fix was to stop
non-technical and rendering vocabulary counting as distinctive.

1. **That candidate direction does not work, and I measured it rather than
   arguing it.** A filter built to the stated principle — words describing the
   medium or the prose rather than the science, written deliberately *not* to
   spare any particular edge — takes **gold topic 62 from 10/10 to 9/10**. It
   loses `comparing → changing`, which is carried by `["explain", "four",
   "outline"]` at `ref_forward` 0.0441: no name, no head word, no section
   containment. That is the *same evidence class* as the four words carrying
   `Solid → Gas`. Any vocabulary filter honest enough to catch "drawn" and
   "spaced" also catches "explain" and "outline". The acceptance test and the
   proposed fix are incompatible, so I did not ship a curated list that spares
   one edge — that is the lesson-specific word list the 2026-09-17 calibration
   decided against.

2. **What shipped is structural.** `contained_in` already reads section
   structure downward (a passage under "Matter" builds on Matter). The sideways
   reading is that two passages under **one** heading, neither of which is what
   that heading names, are **coordinate siblings** — Solid, Liquid and Gas under
   "Matter". Between two siblings an edge now needs a reference that *names* its
   target (the name, a head word, or section containment) rather than merely
   sharing vocabulary with it, because parallel passages share vocabulary by
   construction: the author describes each state the same way, which is what
   "drawn as evenly spaced dots" and "drawn as widely spaced dots" are.
   `criteria.presented_in_parallel` / `criteria.names_the_target`. **No constant
   moved.** This is not the removed sibling rule — that keyed on the words of
   the topic *title*, this keys on the documents' own headings.

   | | gold 62 | gold 79 | live 152 | live 169 | live 163 |
   |---|---|---|---|---|---|
   | Required accepted | 10/10 | 4/8 | 9/10 | 4/8 | — |
   | New gaps / gaps closed | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — |
   | Forbidden | 0 | 0 | **0** (was 1) | 0 | — |
   | Order matches | yes | yes | yes | yes | — |
   | Accepted total | — | — | 19 (was 20) | 8 | 39 (was 41) |

3. **Topic 163 is a data-modelling problem, not a criteria problem, and now
   there is a number for it.** Re-derived with each of its three PDFs as its
   **own topic**: 41 accepted edges → **22, none crossing lessons**, and all 22
   are plausible. The coordinate-sibling rule prunes 2 of its edges and none of
   the 20 that cross lessons — concepts from different PDFs share no heading, so
   it could not. **Topic 163 should be three topics.** That is a teacher action
   in the UI; I did not do it.

4. **A third gold fixture, and the reason it is worth more than the fix.** The
   recorded blind spot was "the fixtures hold older text". That turned out to be
   only half of it. I first exported topic 152 through the existing
   `export_gold_concepts`, which writes the **teacher's** grouping with today's
   text: 7 concepts, 8/10 required, and **0 forbidden edges** — it cannot see
   `Solid → Gas` at all. The denominator is why: `REF_MAX_DF_RATIO` allows a
   term in at most `floor(n × 0.34)` concepts, the diagram vocabulary sits in 3
   concepts either way, so at n=7 the cap is 2 and the words are dropped, at
   n=14 the cap is 4 and they survive. **The teacher's ideal grouping hides the
   failure the teacher sees.**

   So the new fixture freezes the shape a publish actually derives.
   `export_live_concepts` (new command) writes `concepts_for_topic` output and
   labels each concept with the teacher's concept it belongs to.
   `gold.py` grew two things the older fixtures could not express: **several
   concepts may share a key** (the pipeline split what the teacher keeps whole —
   an edge between two such concepts is a grouping result, not a prerequisite
   claim, and is not scored), and **a concept may carry no key** (3 of topic
   152's 14; they still take part in the derivation because they change document
   frequencies and the order, but nothing is scored against them).

**Changed:**

- `learning_path/services/criteria.py` — `named_sections`,
  `presented_in_parallel`, `names_the_target`, and the veto in `decide_pairs`.
- `learning_path/services/gold.py` — shared/absent keys, order collapsed over
  them, `unkeyed_concepts` in the report. Behaviour on 62 and 79 is unchanged
  (every key there is unique and non-null).
- `learning_path/management/commands/export_live_concepts.py` — new.
- `learning_path/fixtures/gold_map_152.json`, `gold_topic_152.json` — new.
- `learning_path/test_gold_paths.py` — third lesson.
- `learning_path/test_criteria.py` — `ParallelPresentationTests` (7).
- `learning_path/CRITERIA.md`, `docs/learning_path_revision_2026-09-17.md`,
  `docs/PROJECT_CONTEXT.md` §4/§6/§7.

**Decisions I made:**

- **Abandoned the recorded candidate fix** instead of curating it into a list
  that keeps 62 at 10/10. Cost if wrong: the rendering vocabulary still counts
  as distinctive everywhere the two concepts are not siblings, so a lesson that
  puts its diagrams under different headings could still produce this.
- **Reconstructed the teacher's concept map for topic 152** from `gold_map_62`
  (same lesson) plus the merges the revision doc records the teacher applying.
  Five of the seven member counts match 62 exactly (matter 4, solid 4, liquid 5,
  gas 4, comparing 6); `changing` has 2 objects today against 3, and `examples`
  4 against 3, because extraction chunked differently. Cost if wrong: the
  fixture asserts a grouping the teacher did not actually specify. **Worth a
  teacher's eye before this is quoted in the manuscript.**
- **Recorded `comparing → changing` as topic 152's one `known_missing`** rather
  than treating it as a criteria failure. It is the same-name veto doing its job
  over two split concepts (318/319). When the teacher joins them the gap closes
  and the test will fail *on the gap closing* — which is the intended behaviour,
  and it needs `known_missing` emptied and the fixture re-exported.
- **Did not republish 152 or 163.** Re-deriving gives identical numbers without
  writing, and their stored rows are still stale.

**Not done / watch out:**

- **Topic 163 still needs splitting into three topics** — 20 of its 21 wrong
  edges go away with no code. Nothing in this session fixed 163.
- **`gold_topic_152.json` is a snapshot of the 2026-09-21 upload.** Re-uploading
  that lesson changes the live concepts but not the fixture. Re-export with
  `export_live_concepts` and say in the log that the numbers moved because the
  fixture moved.
- **Head words can be ordinary adjectives.** `Small intestine → Spine` is
  accepted at 0.5 because "small intestine" lends "small" a full name-weight
  reference. `head_words` checks only that a head word is unambiguous among the
  concept *names*, not that it is a term. Untouched, now recorded in §7.
- **"Comparing the Three States" is also split on topic 152** (331 and 403),
  the same defect as 318/319, and not in the earlier notes.
- The old `gold_map_*.json` / `gold_topic_*.json` pair for 62 and 79 still comes
  from `export_gold_concepts`. Both commands are now live and they write
  **different shapes**; the fixture's `concept_keys` key tells them apart.
- I did not touch `backend/course/tests.py` (the user's uncommitted work) or
  `frontend/`.

### 2026-09-22 — Claude Code — merge `mavia-latest`: the adaptive engine is real now, and three docs said otherwise

**Branch / commits:** `jean-jure-latest`, `3963207` (criteria work) then
`23eb3df` (merge of `origin/mavia-latest` @ `6eea641`). Clean merge, **no
conflicts** — `mavia-latest` had already merged this branch's base (`3820565`)
at `e4e74f1`, so only three of their commits were new.

**Tests:** `python manage.py test -v 1` on the merged tree → **889 passing** (845 ours before the merge; their adaptive suites added, `adaptive_portal`'s 260 lines and `user/test_email_verification.py` removed with them). All three `test_gold_paths` lessons still `ok`, so the criteria work survived the merge intact.

**Live database: untouched by me.** But note that the merge brings **six new
`adaptive` migrations** (through `0006_decision_log_and_concept_mastery`), so
`backend/db.sqlite3` is behind the models until someone runs `migrate`. I did
not run it. Backups are beside it.

**What the merge actually brings**

The user asked whether our dead adaptive code could now be deleted. **It
cannot, because it is no longer dead — and the part that genuinely was dead has
already been deleted by the groupmate.** Specifically:

- **`adaptive/` is now the implementation, not a stub.** `services.py`
  271 → 882 lines, `models.py` 73 → 249, `views.py` → 403, plus
  `PATH_MODE.md` and three new test modules (`test_path_mode.py` 738,
  `test_mobile_traversal.py` 376, `test_decision_log.py` 174).
- **BKT is real.** `adaptive/services.py::_bkt_update`, reading
  `adaptive_config.AdaptiveConfig` for `p_guess` / `p_slip` / `starting_mastery`.
  `adaptive_config` had a docstring saying "when that engine is ported into
  mavia, its scorer should read `AdaptiveConfig.load()`" — it now does, so that
  app stopped being speculative too.
- **`adaptive_portal/` is gone**, all 13 files. That was the old flat
  PDF-order walker and it was the genuinely dead one.
- **DQN is still not wired into serving.** The RL work is in `notebook/mavia_rl/`
  (env, agent, train, evaluate, validate); nothing under `backend/` imports it.
  Checked, not assumed.
- `frontend/` is renamed to **`web-app/`**. A `frontend/` directory survives on
  disk holding only `node_modules/` and is no longer tracked.

**Changed (docs only — I wrote no code this half of the session):**

Four stale statements, each of which the merge turned from true into
false, and each of which would have misled the next agent:

1. `learning_path/CRITERIA.md` §"Not done yet" — said the student apps
   "still walk learning objects in PDF order and have not been switched to it",
   naming `adaptive_portal/services.py`, which no longer exists.
2. `learning_path/HANDOFF.md` §6 — same claim, same dead module. Both now say
   the path contract *is* read, and point at `adaptive/PATH_MODE.md`. This one
   matters beyond tidiness: `HANDOFF.md` documents the published payload, and
   the adaptive engine now depends on it, so changes to it are no longer free.
3. `docs/PROJECT_CONTEXT.md` §2 item 7 — said "BKT + DQN ... **do not exist in
   the codebase yet**. Do not assume they are there." Half of that is now
   backwards. Rewritten to say what path mode does, that BKT is implemented and
   tunable, and that DQN specifically is still notebook-only.
4. `docs/PROJECT_CONTEXT.md` §"Tech stack" and §"Running things" — **found while
   checking the other three, not in the original list.** Every frontend path was
   `frontend/`, and `npm run build` in a directory that now has no
   `package.json`. Also described an `index.css` mirror that no longer exists;
   `web-app/src/main.jsx` imports `styles/mavia.css` and `styles/pipeline.css`.

**Decisions I made:**

- **Merged rather than rebased**, keeping the criteria commit separate from the
  merge. Cost if wrong: an extra merge commit in the history.
- **Did not run `migrate`.** The live database is the teacher's working copy and
  the six new adaptive migrations are the groupmate's; running them is a state
  change nobody asked for. Cost if wrong: anyone starting the server hits
  "Your models have changes that are not yet reflected in a migration" or a
  missing-table error until they migrate.
- **Fixed a fourth stale doc** beyond the three asked for, because it was the
  same defect from the same merge and would have sent the next agent to a
  directory with no `package.json`.
- **Did not delete the leftover `frontend/` directory.** It is untracked and
  holds only `node_modules/`; deleting several hundred MB the user did not ask
  about is their call, and it is recorded in §"Tech stack".

**Not done / watch out:**

- **`backend/db.sqlite3` needs `python manage.py migrate`** before the server
  runs against the merged models. Not done deliberately (above).
- **`backend/course/tests.py` still holds the user's uncommitted work** and was
  never staged, before or after the merge.
- The merged tree has a `web-app/` and a stale `frontend/node_modules/`; the
  latter can be deleted whenever convenient.
- I reviewed the adaptive code only far enough to check the four doc claims
  (BKT present, `AdaptiveConfig` read, `adaptive_portal` gone, DQN not wired).
  **I did not review the groupmate's adaptive work for correctness**, and this
  entry should not be read as saying it is sound.

---

### 2026-09-22 — Claude Code — removed BloomClassifier's rule fallback; rewrote thesis Theoretical Background to match implementation

**Branch / commits:** `jean-jure-latest`, uncommitted (working tree changes, not committed).

**Tests:** None run for the classifier change — no test file exercises `BloomClassifier` or `bloom_classifier.py` at all (confirmed by grep across `backend/`), so there was nothing to run and nothing to break. `PIPELINE.md` doc example updated to match.

**Changed:**

1. **`question_generation/services/bloom_classifier.py`**: deleted `_classify_rules` (the third-tier keyword-cue fallback) and the `"rules"` backend branch in `__init__`/`classify`. The user asked for the reasoning first, and I said the rule tier was already broken — its loop returns `"understand"` after checking only the first (`create`) cue group instead of falling through the other five, so in practice it never distinguished more than two of the six Bloom levels. The user agreed to drop it rather than fix it, on the grounds that a hand-picked keyword list can't cover the space of ways a question can ask for recall vs. analysis, whereas the SVM tier is at least data-driven. `BloomClassifier` is now a two-tier RoBERTa → SVM cascade; `_load_svm` now raises naturally if the SVM artifact is also missing, instead of silently degrading further.
2. **This is a direct user override of a prior standing note in agent memory** ("classifier is authoritative for difficulty labels; do not modify bloom_classifier.py" — see `mavia-architecture-ownership` memory, dated 2026-07-19, tied to the RoBERTa weights being shared out-of-band with the groupmate). I surfaced the conflict before editing; the user confirmed it's theirs to change and did not flag a need to coordinate with the groupmate first. Memory updated to reflect the new state.
3. **`MAVIA MANUSCRIPT.docx`** (thesis, not code — root of `C:\MAVIA`): rewrote the Chapter 1 "Theoretical Background" section (previously generic BKT/RL/Bloom/prerequisite theory not grounded in the actual backend) to describe what the codebase actually does: BKT's fixed global constants in `adaptive/services.py` (`P_GUESS=0.20`, `P_SLIP=0.10`, `P_LEARN=0.15`, `STARTING_MASTERY=0.30`) instead of the illustrative numbers the draft had invented; the RL/DQN section reframed around the MDP state/action space the deterministic threshold engine already implements today, with the DQN described as the trained component the design calls for (tied to the existing cold-start/simulated-pretraining language already in the manuscript's Limitations — deliberately *not* mentioning the project's development-completion percentage, per the user's explicit instruction); the Bloom section rewritten to match the two-tier cascade above; the Prerequisite section rewritten around the actual RefD/key-term/three-criterion-vote/Kahn's-algorithm implementation in `learning_path/services/criteria.py` and `publishing.py`, replacing a generic "directed graph" description. A backup of the pre-edit manuscript was left in this session's scratchpad only (not in the repo).

**Live database:** untouched.

**Decisions I made:**

- Dropped the rule-fallback tier entirely rather than fixing its indentation bug, per the user's explicit direction after I explained the tradeoff. Cost if wrong: if the SVM artifact (`bloom_svm_pipeline.joblib`) is ever missing alongside the RoBERTa checkpoint, question classification now hard-fails instead of degrading to a keyword guess — which the user judged an acceptable (even preferable) failure mode over a silently near-broken fallback.
- Did not touch `RoBERTa` weights, the SVM artifact, or any other part of the generation pipeline — scoped strictly to the fallback-cascade logic the user asked about.
- Wrote the manuscript changes directly into the `.docx` via python-docx XML manipulation (clone-and-retext existing paragraphs) rather than handing back prose for the user to paste in themselves, since they'd asked for the section "output... below" in an earlier turn and then asked me to apply further edits directly. Validated the result against the pre-edit file with the docx skill's `validate.py` (paragraph-count delta and structural checks passed) before overwriting.

**Not done / watch out:**

- **The groupmate has not been notified** that `bloom_classifier.py` changed, despite the prior memory note tying that file to a shared-weights arrangement with her. The user said this was fine to proceed on, but did not say they'd already told her.
- **No test coverage was added** for the two-tier cascade — there was none before either, but this is now a good time to add a test that `_classify_svm`'s exception (not `_classify_rules`, which no longer exists) actually propagates instead of being silently swallowed somewhere upstream in `pipeline.py`.
- **The manuscript edit is uncommitted and untracked by git** (`MAVIA MANUSCRIPT.docx` shows as `??` in `git status`) — it was never under version control before this session either, so nothing changed about that, but there is no repo history to diff against if the user wants to see exactly what changed beyond the scratchpad backup.

---

### 2026-09-23 — Claude Code — dropped the unused GeneratedQuestion.difficulty field; corrected the thesis's RL/DQN and Bloom sections against the real path-mode engine

**Branch / commits:** `jean-jure-latest`, uncommitted.

**Tests:** `python manage.py test -v 1` from `backend/` → **892 tests, all passing** after the field removal and every call-site fix below (ran the full suite, not just the touched apps, since the field crossed four apps).

**Changed:**

1. **Removed `GeneratedQuestion.difficulty` and `BLOOM_TO_DIFFICULTY` entirely**, at the user's direction, prompted by two things surfacing together: (a) their thesis coordinator said difficulty is not soundly derivable from Bloom's level, and (b) I'd already confirmed in the prior session's entry that the adaptive engine never reads `difficulty` — so keeping a field that contradicts the coordinator's stated position, for no functional reason, was a liability rather than dead weight. New migration `question_generation/migrations/0007_remove_unused_difficulty_field.py`. Fixed every call site this broke, which turned out to span four apps, not just `question_generation`:
   - `question_generation/services/bloom_classifier.py` — `classify()` no longer returns `"difficulty"`; `_normalize_level`'s membership check switched from `BLOOM_TO_DIFFICULTY` to `BLOOM_TO_CATEGORY` (same six keys).
   - `question_generation/services/pipeline.py`, `serializers.py`, `views.py` — stopped setting/serializing/returning `difficulty`.
   - `lessons/services/question_workflow.py` — two call sites (`enriched_question_values`, `sync_question_to_adaptive`, and the `mirror_generated_questions` `Question.objects.create(...)` call) were reading `classification["difficulty"]` / `generated.difficulty`, which would have raised `KeyError`/`AttributeError` the moment either path ran. **`lessons.Question.difficulty` itself was left in place** — it's a separately-migrated field (`lessons/migrations/0014`), out of the scope the user gave me, and it's still read by `learning_resource_linker.py` and serialized in `lessons/serializers.py`. It will now always be blank for new questions since nothing populates it anymore; I did not chase that further.
   - `learning_path/services/published.py` — `_questions()` was putting `question.difficulty` into the payload the adaptive engine reads at runtime; this was the one that actually crashed tests (`AttributeError` in `resolve_learning_start`), not just a serialization nicety.
   - Test fixtures across `lessons/test_generated_question_safety.py`, `adaptive/test_mobile_traversal.py`, `adaptive/test_path_mode.py`, `learning_path/tests.py` were constructing `GeneratedQuestion` rows with a `difficulty=` kwarg; stripped.
   - `question_generation/PIPELINE.md` — fixed the two doc blocks that directly quoted the now-deleted table, and added a note flagging that the rest of that doc (Steps 10–12, describing `intended_difficulty`/`difficulty_match`/`_difficulty_shortfall`) was **already stale against `pipeline.py`'s actual current shape before this session** — it documents an older pipeline structure I did not attempt to reconcile; a real audit of that doc is a separate task.
2. **Corrected a second, unrelated inaccuracy in the manuscript that surfaced from the user's own questions**, not from anything I'd have caught otherwise: the RL/DQN section (written last session) described the adaptive engine's state as including "position within the four-tier question sequence" and "the active difficulty level." Neither is true of the current engine. I had read `adaptive/services.py` earlier in the *same* conversation and gotten a `TIER_BUCKETS`/`_step_down_difficulty`-based legacy engine from it; by this session the file — 882 lines, unchanged in git history since 2026-09-17 — visibly contains a different, path-mode engine instead (`_ordered_step_questions`, `AdaptiveEngine.evaluate_path`, `VARIANT_ORDER = ["normal", "simplified", "elaborated"]`), and grep confirms `category` and `difficulty` are never read by it at all. I don't know whether I misread the file the first time or read a genuinely different version of it; either way, **I should have re-verified before writing more manuscript text off an earlier read**, and didn't, until the user asked. Rewrote the RL/DQN section's state/action description and worked example around the real mechanics (mastery + path position + content variant; escalate variant on a miss → reroute to nearest prerequisite → reroute to an alternate chunk, in that order, per `AdaptiveEngine._reroute`), and rewrote the Bloom section to stop implying the four-tier category feeds sequencing — it doesn't; LOT/HOT does, via `_ordered_step_questions`' sort. Both now state plainly that the four-tier scheme is a content-organization classification (satisfies the thesis's Objective 2, consumed by the Course Builder's item-bank view) while LOT/HOT is the sequencing axis (consumed by generation-time quota balancing and by the adaptive engine at runtime) — separate purposes, not two labels racing to do the same job.
3. Confirmed via grep that **`TIER_BUCKETS` on `GeneratedQuestion` is now dead** — referenced nowhere except a comment in `adaptive/services.py` pointing at it as what the legacy engine used to use. Left it alone; out of scope for what was asked, flagged below.

**Live database:** untouched (migration not yet run against it — `db.sqlite3` still has the old schema until `manage.py migrate` runs).

**Decisions I made:**

- Fixed every downstream break the field removal caused rather than stopping at `question_generation`, because leaving `lessons/services/question_workflow.py` or `learning_path/services/published.py` broken would have failed silently until someone hit the exact code path (confirmed by the fact that the full test suite, not just `question_generation`'s own tests, was what caught the `published.py` one).
- Left `lessons.Question.difficulty` in the schema rather than also removing it, since the user scoped the request to `GeneratedQuestion`/the classifier specifically, and removing it would touch `learning_resource_linker.py`, `serializers.py`, and its own migration — a bigger, separate decision.
- Did not run `python manage.py migrate` against the live `db.sqlite3` — same standing policy as the prior session's entry (it's the teacher's working copy; migrating is the user's call, not mine to make silently).

**Not done / watch out:**

- **`python manage.py migrate` still needs to run** before this branch's code and the live database schema agree — `GeneratedQuestion.difficulty` still exists in the database until then.
- **`lessons.Question.difficulty` is now permanently blank for every new question** — it still exists in the schema and is still read in a couple of places, but nothing populates it anymore. Worth a follow-up decision on whether to remove it too, or repurpose it.
- **`question_generation/PIPELINE.md` needs a real audit**, not the two spot-fixes made here — it describes `intended_difficulty`/`difficulty_match`/`_difficulty_shortfall` machinery that doesn't match `pipeline.py`'s current functions, and that mismatch predates this session.
- **`GeneratedQuestion.TIER_BUCKETS` is dead code** (confirmed by grep, not removed — out of scope for what was asked).
- **The manuscript's RL/DQN section is now grounded in `adaptive/services.py` as of this session's read.** Given that I've now been burned once by trusting an earlier read of this exact file without re-verifying, whoever touches this section next should re-grep it fresh rather than trusting this entry or the manuscript text as ground truth.

### 2026-09-26 — Claude Code — a corrective-RAG grounding gate on question generation; pipeline flowchart corrected

**Branch / commits:** mavia-latest, uncommitted
**Tests:** `python manage.py test question_generation` — 87 tests, OK (30 new in
`test_grounding.py`). Also ran the gate live against the published topic 276.
**Changed:**
- **New** `question_generation/services/grounding.py` — three-stage validation of
  every draft question against the topic's own PDF text: lexical grounding,
  MiniLM vector retrieval over chunked raw `extracted_text`, then an
  LLM-as-judge entailment check. Failures are deleted and their reasons fed
  back into a bounded corrective regeneration pass.
- `services/pipeline.py` — gate phase between drafting and finalization;
  index built once per run; `ungrounded`/`unverified` added to run stats.
- `services/question_generator.py` — `generate_questions(..., correction=...)`
  threads rejection feedback into the prompt.
- `config/settings.py` + `.env.example` — six `QUESTION_VALIDATION_*` /
  `QUESTION_JUDGE_*` settings. No migration needed: `GenerationEvent.event_type`
  is already `CharField(64)` from the pending `0008`.
- `docs/MAVIA_PIPELINE_FLOWCHART.svg` — stage 8 rewritten for the gate, and
  four stale claims corrected (see below).

**Why this exists (measured, not assumed):** on the published topic 276, 61 of
76 final questions used content words absent from all three PDFs, and Q107/Q109
marked **"plasma"** correct where the source says "gas" and "solid". The source
text was already in the prompt both times. This is why the gate checks whether
the model *used* its context, not whether it *had* it — retrieval alone would
not have caught any of it.

**Live database:** backed up to `db.sqlite3.pre-grounding-gate.20260926`.
Topic 276's question bank was regenerated through the gate (no learner
responses existed, so nothing of a student's was lost).

**Decisions I made:**
- **Retrieval is scoped to the topic's materials, not a global PDF index.** The
  user's plan said "a local raw PDF index"; a global one would let the judge
  validate a question about particle arrangement against a passage on melting.
  Flagged before building, built scoped.
- **The lexical stage is kept as a non-bypassable first gate** rather than
  relying on the judge alone. Measured reason below.
- **Default `QUESTION_JUDGE_MODEL` is `llama3.2:3b`, not the larger model.**

**Watch out — the bigger judge is the worse judge.** With the lexical stage
bypassed, `llama3.2:3b` correctly rejected both "plasma" questions;
`gemma3:4b` passed both as "supported". Re-measure before changing
`QUESTION_JUDGE_MODEL`; a weak judge is worse than an obvious gap because it
looks like verification. `gemma2:9b` (which the user's plan named) is not
pulled on this machine.

**Also watch out — killing a background run does not kill its Python child.**
Stopping the first regeneration left PID 24460 alive and writing to
`db.sqlite3` while a second run started, which silently corrupted a
before/after comparison (76 rows became 72 mid-measurement). Kill by PID and
verify with `Get-CimInstance Win32_Process` before trusting any DB numbers.

**Flowchart corrections beyond stage 8** (all verified against code, all were
stale): the question model is `llama3.2:3b` not `gemma3:4b`; `/api/generate` is
called **streaming** with a JSON schema, not non-streaming; prompts are keyed by
**thinking order**, not difficulty (the `difficulty` field was removed in
migration 0007); there is no "strict re-prompt on pass 2" and no multi-round
"quota rebalancing" — both were replaced by overgeneration inside a single call;
and the adaptive step now notes that the published path serves **one LOT + one
HOT per step**, which the diagram did not say.

**Two defects the live run found in the gate itself** (both fixed, both were
mine, and neither would have shown without running it on real material):
1. *Exact word matching rejected grounded questions.* The lesson says
   "depicts"; a question said "depicted"; the vocabulary had no way to see they
   are one word. Fixed by matching inflection **variants** rather than one
   canonical stem — no single stem works, since stripping "-ing" gives "mov",
   which no rule turns "move" into, so both forms are emitted and allowed to
   meet. Verified it does not blunt the gate: "plasma", "temperature",
   "pressure" and "intermolecular" each still yield only themselves.
2. *Scanning every MCQ option punished good distractors.* A wrong option is
   wrong on purpose, and wrong often means vocabulary the lesson never uses.
   The gate rejected "What is the arrangement of particles in a solid?" —
   stem and key both straight from the source — because one distractor said
   "none". The lexical stage now scans **the stem and the option marked
   correct only**. This loses nothing: "plasma" was the *correct answer* on
   Q107 and Q109 and sat in Q114's stem, so all four original defects are
   still caught. Lexical rejection on the published bank fell 61/76 → 49/76.

**Not done:**
- The `EXTRA` bundle problem from this session's audit is untouched: lo557/558/559
  are extracted, grouped and described but unreachable by any learner.
- `LessonDetailView` still returns `correct_answer` to students (76 of 93 legacy
  rows on topic 276 have one). Raised as an open thread below.
- The judge is not calibrated. There is no labelled set of supported/unsupported
  questions, so its accuracy is anecdotal — two questions, one model comparison.


### 2026-09-27 — Claude Code — generation-time grounding: the bank goes 18 -> 41 with nothing ungrounded

**Branch:** `question-revisions` (11 commits). **`mavia-latest` was rewound to
`f9c8937`** at the user's request and holds none of this work. Nothing pushed.

**Tests:** `python manage.py test question_generation` — 130, OK. Verified in a
clean `git worktree`, not only the working tree (see the Critical below).

**What this session did.** The previous entry added a corrective-RAG gate after
generation. This one fixed *generation*, because the user's call was right: the
gate should stay strict and the generator should meet it, not the reverse.
Five changes, each measured on topic 276:

1. **Questions are written from every telling of a concept**, not the Normal
   bundle alone (`concept_source_text`). Solid 32 -> 220 words. A learner on a
   remediation rung was being asked about text they were never read.
2. **The prompt forbids outside knowledge.** It had no prohibition at all, and
   the HOT template actively said "do NOT ask for a fact stated word-for-word",
   which pushed the model off-source with nowhere to go but its own knowledge.
3. **`_validate_question` actually validates** — it accepted any answer letter
   present in the choices, which is how `D) plasma` shipped.
4. **Each format gets its own whole schema shape via `anyOf`.** This was the
   big one. One merged shape had to leave `choices` optional, and Ollama
   compiles the schema into a decoding grammar, so optional meant the model
   skipped the options *every time*. HOT was MCQ-only, so every HOT call
   produced nothing usable and the HOT bucket was filled by accident from LOT
   output the Bloom classifier relabelled.
5. **Stopped generating banks that are deleted on arrival.** 22 of 42 objects
   generated a bank that `finalize_node_questions` deletes moments later.

**Measured, topic 276:**

| | gate only | + generator fixes | + anyOf |
|---|---|---|---|
| questions | 27 | 18 | **41** |
| HOT | 5 | 5 | **12** |
| ungrounded | 0 | 0 | **0** |
| gate rejections | 228 | 40 | 100 |
| runtime | 117 min | 44 min | 66 min |

(The 27 -> 18 dip is not a regression: the 27 included banks attached to
non-lead objects that survived only by finishing last.)

**Live database:** topic 276's bank regenerated several times. Backups:
`db.sqlite3.pre-grounding-gate.20260926` (76 questions, no gate),
`db.sqlite3.baseline-strict-gate-old-generator.20260927` (27),
`db.sqlite3.pre-anyof.20260927` (18). No learner responses existed at any point.

**Decisions made on the user's behalf:**
- Retrieval is scoped to the topic's materials, not a global PDF index. A
  global one would let the judge validate a question against a passage the
  learner never hears.
- The lexical stage scans the stem and the *marked answer only*, not the
  distractors. A wrong option is wrong on purpose and often uses unfamiliar
  words; scanning them rejected questions whose stem and key were both
  straight from the source.
- Only the requested formats are offered in the schema. Left free the model
  reaches for true/false — asked for two MCQ and one TF it returned three TF.

**Watch out:**
- **`anyOf` support depends on the model's grammar conversion.** Verified on
  `llama3.2:3b` only. Re-test before switching `QUESTION_LLM_MODEL`, which the
  user is considering (`gemma3:4b`, to run one model across MAVIA). Note also
  that `gemma3:4b` was measured as a *worse* judge than `llama3.2:3b` — it
  passed both "plasma" questions that llama rejected.
- **Killing a background run does not kill its Python child.** Stopping one
  regeneration left a process writing to `db.sqlite3` while a second started,
  silently corrupting a measurement. Kill by PID and verify with
  `Get-CimInstance Win32_Process`.
- A whole-branch review found that `grounding.py` had never been committed
  while `pipeline.py` imported it — the branch did not run on a fresh
  checkout, and every green test result had been measured against a working
  tree that differed from `HEAD`. Fixed; verify in a worktree, not the tree
  you are editing.

**Uncommitted and not mine:** PostgreSQL work in `backend/config/settings.py`,
the web-app changes, and both IEEE manuscript `.docx` files. A broad `git add`
had staged all of it at one point; it was unstaged before committing. Check
`git status` before the next commit.

**Not done:** the user ended the session mid-decision on the True/False-in-MCQ
defect below.

### 2026-09-29 — Claude Code — Learning path review screen is graph-first

**Branch / commits:** `learning-path-graph-screen` (from `learning-path-criteria-v4`), b97586e..HEAD.
Spec `docs/superpowers/specs/2026-09-29-learning-path-graph-screen-design.md`,
plan `docs/superpowers/plans/2026-09-29-learning-path-graph-screen.md`.
**Tests:** `python manage.py test` → 1212 OK; `cd web-app && npm test` → 14 OK;
`npm run build` OK. Playwright walkthrough of every editing action on topics 340
and 357 (add, move, add-vs-move choice, "already", loop refusal, accept, reject,
remove, undo of each, 10 s undo timeout, read-only page, load-failure Retry).
**Changed:**
- Review step 5 is now a React Flow + dagre prerequisite graph (75%) with a
  recommended-links panel (25%); list view and the heading-column concept map
  removed. Drag B onto A = A before B; when B already has prerequisites the
  confirm offers Add or Move. Every change is confirmed and undoable for 10 s.
- Links are derived when the screen opens (`GET /api/learning-path/topics/<id>/`
  calls `refresh_prerequisites`), no longer only at publish.
- `refresh_prerequisites` keeps derived link ids stable and tolerates two opens
  deriving at once (found live: IntegrityError 500 on concurrent first loads).
- New `links/move/` and `links/restore/`; add/decide/move return an `undo` record.
- Each link carries a plain-words `reason`; each step names its `source_materials`;
  R3 evidence records passage counts.
**Live database:** links for topics 340 and 357 were derived by opening the
screen (derived rows only). Every walkthrough change was undone; both topics'
link rows were compared before/after and are identical.
**Decisions I made:** listed as `Ruling:` lines in the run ledger and in the
hand-back message (in-place branch not worktree; `_path` test client reuse;
arrow styling; key fix; Retry banner replaces the page-wide error for failed
path loads).
**Not done / watch out:**
- Old `.cm-*`, `.lf-*`, `.path-step*`, `.ps-*` rules in
  `web-app/src/styles/pipeline.css` are now unused; delete in a cleanup pass.
- Entering the Versions step auto-POSTs `generate-all-versions` for topic 357
  (pre-existing); anyone driving the UI to step 5 triggers it.
- The details card sits over the graph's top-left and can cover highlighted
  neighbours on small topics.
- Opening the screen now writes (derived links); it is teacher-only.

**Addendum 2026-09-30 (same branch, commits 0385758, 8a97d2b):** per the user,
the recommendations panel is gone -- the graph is full width, pending links sit
in the dependent concept's card as yellow rows, and concepts with pending links
are marked yellow with a count. A "Topic published!" dialog now follows a
successful publish, playing each concept's Normal narration in path order
(multi-part concepts play back to back; no Play all). Verified in a headless
browser with the publish simulated in the browser (no real publish, no model
calls); topic 340's links identical before/after. Note: the dev server serves
media without Range support, so audio cannot be seeked (pre-existing).


### 2026-09-30 — Claude Code (Opus 5.5) — Learning-path criteria v5: relatedness + two evidence families

**Branch / commits:** learning-path-graph-screen, e75429b..HEAD (spec, plan, Tasks 1–10, 12). Not pushed.
**Tests:** `python manage.py test` 1225/1225 OK; `learning_path` 200 OK; web-app vitest 19/19, build OK.
**Changed:** replaced v4 criteria with v5 (`backend/learning_path/CRITERIA.md`): sentence-embedding relatedness gate, clues name/terms/meaning (content) and heading/PDF order (structure), accepted only when the families agree; Kahn with weakest-link cycle breaking; redundant links hidden on the graph. Removed `concepts.py`, v4 text helpers, `evaluate_edges.py`. Added `calibrate_learning_path` and `calibration/weights.json`. Gold 62/79/152 no longer mark examples structural (user decision).
**Live database:** untouched (read-only exports only).
**Decisions I made:** see the ledger rulings in the final report — notably Kahn ties by PDF order (build-on-latest measured worse), and meaning clue kept despite being at chance on direction.
**Not done / watch out:** topic 357's key encoded from the user's AI recommendation and measured (8 → 20 of 20 after amendment 2 — the chain as pending suggestions; 0 forbidden); calibration now uses 62/79/152/340/357. 340 shows 62 pending suggestions — a lot for one screen. First v5 build accepted forbidden links (overviews read backwards); spec §14 records the fix. A `git stash pop` mistake briefly applied the user's `stash@{0}` (LATEST-with-bugs) here; the four touched files were restored to HEAD and the stash is intact.

---

## Open threads

- **True/false questions wearing an MCQ costume.** 2 of 14 MCQs in topic 276's
  bank are propositions padded to four options: Q621 "A book and a balloon both
  occupy space but have different shapes." with `{A: True, B: False, C: "It
  doesn't matter", D: "This statement is irrelevant"}`, and Q616 padded with
  `liquid`/`gas`. Cause: with `anyOf` the model commits to the MCQ branch while
  decoding, and that shape requires A-D, so a model that wanted a proposition
  must invent two options. Both are HOT, the bucket changed from MCQ-only to a
  mixed split. **Decision left open:** reject them, or convert them to real TF
  items (better for a thin bank, but means rewriting model output). Note the
  detection rule — "options offer True and False as the answer frame" — is
  structural and holds across science lessons, but would wrongly reject a
  legitimate programming MCQ like "what does `print(3 > 2)` output?". Say so in
  the comment rather than claim it is universal. — raised by Claude Code,
  2026-09-27
- **The gate now rejects more than it accepts:** 100 rejections against 76
  drafts on the last run, and MCQ is hit far harder than TF (14 MCQ vs 27 TF
  survive, though generation produces ~55% MCQ). Plausibly because the lexical
  stage scans the marked answer, and an MCQ's answer is a phrase where a TF's
  is just "True". Unmeasured — the rejections are in `GenerationEvent` with
  their stage and reason, so it is directly answerable. — raised by Claude
  Code, 2026-09-27
- **Five concepts still have no questions** (Melting, Freezing, Condensation,
  "Matter usually exists...", the changes-of-state figure). They are the short
  ones, but a reliability harness got 6/6 from Melting in isolation, so the
  questions are generated and then rejected by the gate. Path mode advances to
  the next step *with* a question, so an empty concept is never taught. —
  raised by Claude Code, 2026-09-27
- **The four-category spread is very uneven** — Skills 24, Facts 9, Meaning 7,
  Outcome 1 — because `category` is a fixed lookup on `bloom_level`
  (`BLOOM_TO_CATEGORY`), not a prediction. Worth stating that way in the
  manuscript: a panel asking "how is category predicted?" has a sharp question
  and the answer is "it isn't". — raised by Claude Code, 2026-09-27
- **Students are served the answer key.** `adaptive.views.LessonDetailView`
  (permission `IsStudent`) returns `lessons.Question.correct_answer` via
  `lessons/services/lesson_package.py::_lesson_questions`. On topic 276 that is
  76 of 93 rows with a populated answer, sent to any enrolled learner's device.
  Path mode is careful about this (`adaptive.services.student_safe_step`); this
  endpoint is not. — raised by Claude Code, 2026-09-26
- **Three learning objects are unreachable by any learner.** lo557/558/559
  (material 48's *Everyday Examples* telling) sit in group 574's `EXTRA` bundle.
  `_versions` skips `EXTRA`, `represented_by` disqualifies them as alternates,
  and they are the only 3 of topic 276's 45 objects with no audio in any
  playlist. Decide what `EXTRA` is for, or stop generating it. — raised by
  Claude Code, 2026-09-26
- **The question judge is uncalibrated.** `QUESTION_JUDGE_MODEL` decides what
  reaches a learner, and its accuracy rests on two questions and one model
  comparison (`llama3.2:3b` caught the "plasma" answers, `gemma3:4b` did not).
  A labelled set of supported/unsupported questions is wanted before the
  lexical stage's tolerance (`QUESTION_VALIDATION_MAX_NOVEL_TERMS`) is relaxed
  from 0. — raised by Claude Code, 2026-09-26
- **A bundle with no assigned version role still feeds the prompt.** The EXTRA
  exclusion in `concept_source_text` only fires once a role is stored, and
  nothing orders the versions step before question generation. A teacher who
  generates before opening the versions screen, then publishes, can serve a
  question written from a bundle later marked EXTRA. The run trace names them;
  regenerating on a role change was not implemented. Zero unclassified bundles
  on topic 276 today. — raised by Claude Code, 2026-09-27

- **Students are served the answer key.** `adaptive.views.LessonDetailView`
  (permission `IsStudent`) returns `lessons.Question.correct_answer` via
  `lessons/services/lesson_package.py::_lesson_questions`. On topic 276 that is
  76 of 93 rows with a populated answer, sent to any enrolled learner's device.
  Path mode is careful about this (`adaptive.services.student_safe_step`); this
  endpoint is not. — raised by Claude Code, 2026-09-26
- **Three learning objects are unreachable by any learner.** lo557/558/559
  (material 48's *Everyday Examples* telling) sit in group 574's `EXTRA` bundle.
  `_versions` skips `EXTRA`, `represented_by` disqualifies them as alternates,
  and they are the only 3 of topic 276's 45 objects with no audio in any
  playlist. Decide what `EXTRA` is for, or stop generating it. — raised by
  Claude Code, 2026-09-26
- **The question judge is uncalibrated.** `QUESTION_JUDGE_MODEL` decides what
  reaches a learner, and its accuracy rests on two questions and one model
  comparison (`llama3.2:3b` caught the "plasma" answers, `gemma3:4b` did not).
  A labelled set of supported/unsupported questions is wanted before the
  lexical stage's tolerance (`QUESTION_VALIDATION_MAX_NOVEL_TERMS`) is relaxed
  from 0. — raised by Claude Code, 2026-09-26

- **Regenerate figure descriptions** with the new RTCF prompt (needs Ollama's
  vision model). Clears the model's chatter from lesson text and from one
  concept's name. A before/after measurement (length, preamble, overlap with
  the lesson) would turn the prompt rewrite into a measured claim for the
  manuscript; not yet run. — raised by Claude Code, 2026-09-21
- **Split topic 163 into three topics**, one per organ system, in the UI. It is
  three lessons in one topic, and every criterion assumes a topic *is* a lesson.
  Measured 2026-09-22: 41 accepted edges → 22, and all 20 cross-lesson edges
  disappear, with no code. This is the single largest remaining wrong-edge
  source and nothing in the criteria can reach it. — raised by Claude Code,
  2026-09-22
- **Have the teacher check `gold_map_152.json`.** Its concept map was
  reconstructed from `gold_map_62` (same lesson) plus the merges the revision
  doc records, not stated by the teacher for today's objects. Five of seven
  member counts match 62 exactly; `changing` and `examples` differ because
  extraction chunked differently. It is now an acceptance test, so it should be
  confirmed before the manuscript quotes it. — raised by Claude Code, 2026-09-22
- **Join topic 152's split concepts** (318/319 "Changing From One State to
  Another", and 331/403 "Comparing the Three States") with **Move into another
  concept…**. Joining 318/319 closes `comparing → changing`, topic 152's last
  missing required edge. When it closes, empty `known_missing` in
  `gold_map_152.json` and re-export the fixture, or `test_gold_paths` fails on
  the gap closing — which is what that assertion is for. — raised by Claude
  Code, 2026-09-22
- **Empty-group cleanup on material delete** — proposed, awaiting the user's
  go-ahead. Less urgent than it looked: the re-upload refilled all 31, so none
  are empty now. The underlying bug stands, and group 326 did inherit a stale
  `auto_label`, which is exactly the risk described. — raised by Claude Code,
  2026-09-21
- **A third lesson** is what the learning-path criteria actually need; they are
  currently fitted to the same two lessons the gold standard came from. Re-run
  `python manage.py evaluate_gold_paths` when one exists. — raised by Claude
  Code, 2026-09-21. *Partly addressed 2026-09-22*: `test_gold_paths` now runs a
  third fixture, but it is the **same lesson** as topic 62 in the shape the
  pipeline derives today, so it tests a different failure mode, not a different
  lesson. A genuinely unseen lesson is still wanted. Note also that
  `evaluate_gold_paths` still sweeps only topics 62 and 79.
- **Head words can be ordinary adjectives.** `Small intestine → Spine` is
  accepted at `ref_forward` 0.5 because "small intestine" lends "small" a full
  name-weight reference to anything saying "small". `head_words` only checks
  that a head word is unambiguous among the concept *names*, not that it is a
  term at all. Cheap to fix, not measured, not attempted. — raised by Claude
  Code, 2026-09-22
