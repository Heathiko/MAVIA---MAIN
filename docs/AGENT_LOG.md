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

**Changed (three pieces of work):**

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

---

## Open threads

- **Regenerate figure descriptions** with the new RTCF prompt (needs Ollama's
  vision model). Clears the model's chatter from lesson text and from one
  concept's name. A before/after measurement (length, preamble, overlap with
  the lesson) would turn the prompt rewrite into a measured claim for the
  manuscript; not yet run. — raised by Claude Code, 2026-09-21
- **Publish both topics** once TTS is reachable, then compare the derived paths
  with the gold standard and append the result to
  `docs/learning_path_revision_2026-09-17.md`. — raised by Claude Code, 2026-09-21
- **Empty-group cleanup on material delete** — proposed, awaiting the user's
  go-ahead. — raised by Claude Code, 2026-09-21
- **A third lesson** is what the learning-path criteria actually need; they are
  currently fitted to the same two lessons the gold standard came from. Re-run
  `python manage.py evaluate_gold_paths` when one exists. — raised by Claude
  Code, 2026-09-21
