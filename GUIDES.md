# Guide to the project's Markdown files

Every guide in this repository, what it is for, and whether it describes the
system as it is now. Markdown inside `node_modules/`, `.venv/` and other
installed packages is not listed.

**Status key**

| Status | Meaning |
|---|---|
| **Current** | Describes the code as it is. Kept up to date. |
| **Record** | A dated note of a past state or decision. Read for history, not for how things work today. |
| **Superseded** | A record whose subject has since been replaced or removed. Its top banner points to the current guide. |
| **Not reviewed** | Not checked against the code during the 2026-09-15 documentation pass; may be out of date. |

Last reviewed: 2026-09-15.

---

## Start here

| File | What it is for | Status |
|---|---|---|
| [README.md](README.md) | Project overview: what MAVIA does, how matching and content versions work, the main guides, and the commands to verify a build. | Current |
| [GUIDES.md](GUIDES.md) | This file: an index of every guide. | Current |

---

## Learning path

| File | What it is for | Status |
|---|---|---|
| [backend/learning_path/HANDOFF.md](backend/learning_path/HANDOFF.md) | **For whoever builds the adaptive rules.** How to read a subtopic's published learning path (API or Python), what every field means, how to remediate through prerequisites, and what the path does and does not guarantee. | Current |
| [backend/learning_path/CRITERIA.md](backend/learning_path/CRITERIA.md) | **How the learning path is built.** Merging the PDFs' orders, how prerequisite links adjust it, the three voting criteria, vetoes, the cross-section rule with its hand-check evidence, link statuses, and teacher control on review step 5. | Current |
| [backend/learning_path/README.md](backend/learning_path/README.md) | Short overview of the `learning_path` app: pipeline, endpoints, management commands. Points to HANDOFF and CRITERIA. | Current |

---

## Content preparation (extraction, grouping, versions, publishing)

| File | What it is for | Status |
|---|---|---|
| [docs/SEMANTIC_GROUPING.md](docs/SEMANTIC_GROUPING.md) | How learning objects from different PDFs are grouped as the same concept: teacher workflow, thresholds, what Separate/Connect do, and how edited groups are reviewed. | Current |
| [backend/lessons/REGROUPING.md](backend/lessons/REGROUPING.md) | *Review grouping changes* for edited, already grouped objects, and the fix for content-version links left behind when an object changes group. | Current |
| [docs/TEACHER_PUBLISHING_VALIDATION.md](docs/TEACHER_PUBLISHING_VALIDATION.md) | Acceptance checks for the teacher workflow (upload to publish, including the learning path), the evaluation still required before claiming accuracy, and known boundaries. | Current |
| [backend/lessons/features/pdf_processing/README.md](backend/lessons/features/pdf_processing/README.md) | Code layout of the PDF-processing feature (serializers, use cases, services) and the chunk-balancing settings. | Not reviewed |
| [docs/GROUPING_STATUS_2026-09-13.md](docs/GROUPING_STATUS_2026-09-13.md) | Seven extraction and grouping changes made on 2026-09-13 (section headings, chunking, label corroboration), with the evidence for each. A banner lists what changed afterwards. | Record |
| [docs/CONTENT_VERSIONS_STATUS.md](docs/CONTENT_VERSIONS_STATUS.md) | How Normal/Simplified/Elaborated versions are sourced, and the bugs found in the first publish run (2026-09-10). Its bug list has not been re-checked; its notes for the learning path were corrected. | Record |

---

## Design specs and plans (`docs/superpowers/`)

Written before implementation. They record intent and reasoning; the code may
have moved on, and each marks where.

| File | What it is for | Status |
|---|---|---|
| [specs/2026-09-10-learning-object-versions-design.md](docs/superpowers/specs/2026-09-10-learning-object-versions-design.md) | Design for giving every learning object Normal, Simplified and Elaborated versions from teacher text first, the model second. | Record |
| [plans/2026-09-10-learning-object-versions.md](docs/superpowers/plans/2026-09-10-learning-object-versions.md) | Step-by-step implementation plan for the design above. | Record |
| [specs/2026-09-12-grouping-and-parent-headings-design.md](docs/superpowers/specs/2026-09-12-grouping-and-parent-headings-design.md) | Design for keeping parent headings during extraction, plural label matching, and margin-gated grouping suggestions. | Record |
| [specs/2026-09-10-prerequisite-redesign-design.md](docs/superpowers/specs/2026-09-10-prerequisite-redesign-design.md) | Per-PDF prerequisite design with strong/medium/weak evidence. Removed from the code. | Superseded |
| [specs/2026-09-10-edge-scoring-design.md](docs/superpowers/specs/2026-09-10-edge-scoring-design.md) | Per-PDF multi-criteria edge scoring. Removed from the code. | Superseded |
| [specs/2026-09-13-prerequisite-criteria-v3-design.md](docs/superpowers/specs/2026-09-13-prerequisite-criteria-v3-design.md) | The v3 criteria (temporal order, semantic reference, inbound/outbound ratio). Implemented, but several checks were later removed or changed; see its banner. | Superseded (partly) |
| [docs/EDGE_SCORING_FOR_REVIEW.md](docs/EDGE_SCORING_FOR_REVIEW.md) | A write-up of the per-PDF edge scoring, prepared for outside review. Despite its title it is not the current design. | Superseded |

---

## Adaptive learning, integration and project history

| File | What it is for | Status |
|---|---|---|
| [GAPS.md](GAPS.md) | Loose ends around the adaptive engine and course review: what was closed (knowledge tracing, student APIs, web/mobile split) and what was still open. | Not reviewed |
| [INTEGRATION_NOTES.md](INTEGRATION_NOTES.md) | Notes from merging the `mavia-latest` branch locally: what was preserved and integrated, startup commands, and database backup details. | Not reviewed |
| [VILLEGAS_DEFENSE_NOTES.md](VILLEGAS_DEFENSE_NOTES.md) | Defense notes for Villegas's part: turning uploaded lesson and outline PDFs into accessible learning objects, and how to explain it. | Not reviewed |

---

## Mobile apps

Three mobile projects exist. **`mobile-app/` is the current student app**; the
other two are earlier prototypes.

| File | What it is for | Status |
|---|---|---|
| [mobile-app/README.md](mobile-app/README.md) | The student app (Expo + React Native): screens, auth flow, and how it talks to the backend. | Not reviewed |
| [mobile-app/RUNNING.md](mobile-app/RUNNING.md) | Running the student app on a phone over USB or Wi-Fi. Its paths (`k:\STUDIO\...`) are from another machine. | Not reviewed |
| [mobile/README.md](mobile/README.md) | An earlier student-app scaffold running on mock data. | Not reviewed |
| [mavia-mobile/README.md](mavia-mobile/README.md) | The default Expo starter README of an earlier prototype. | Not reviewed |
| [mobile/AGENTS.md](mobile/AGENTS.md), [mavia-mobile/AGENTS.md](mavia-mobile/AGENTS.md) | One-line instruction for AI coding assistants: read the Expo v57 docs before writing code. | Not reviewed |
| [mobile/CLAUDE.md](mobile/CLAUDE.md), [mavia-mobile/CLAUDE.md](mavia-mobile/CLAUDE.md) | Points Claude Code at the matching `AGENTS.md`. | Not reviewed |

---

## Keeping this index useful

- **Adding a guide:** add a row here, in the section it belongs to.
- **Replacing a guide's subject:** don't rewrite the old record. Add a short
  *Superseded* banner at its top pointing to the current guide, and update its
  status here.
- **Current guides** should be updated in the same change as the code they
  describe.
