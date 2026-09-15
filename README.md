# MAVIA

The local `mavia-latest` merge includes `web-app`, `mobile-app`, and a compatible
enrollment-based backend alongside the original system. See
[INTEGRATION_NOTES.md](INTEGRATION_NOTES.md) for startup commands, API separation,
database backup details, and validation limits.

Course-outline and lesson-PDF processing for accessible science content.

## Current scope

- Validates that the first PDF is a course outline before extracting its hierarchy.
- Validates lesson PDFs against the selected outline topic.
- Extracts accessible text and image learning objects while preserving source metadata.
- Keeps questions separate from narration content and links confirmed questions to concept groups.
- Connects equivalent learning objects from different PDFs without assigning difficulty levels.
- Provides one-at-a-time teacher review for uncertain object and question pairs.
- Lets teachers review where edited, already grouped objects now belong (*Review grouping changes*).
- Generates lesson audio from confirmed learning-object content and teacher image descriptions.
- Builds one learning path per subtopic: concepts merged across PDFs, ordered by the
  lesson files and by "learn first" links that teachers can add, approve or remove.
  The path is saved at each successful publish and served to the adaptive rules.

## Matching approach

Learning-object matching uses configurable title/content TF-IDF, character n-grams,
keyword overlap, and document-structure evidence. An exact title is evidence, but it
does not override the content score. Object matches at 50% or above are connected
automatically only when the content evidence also reaches 30% against every member
of the destination group. Matches from 30% through 49% require teacher review, and
lower scores are ignored. Question pairing uses configurable TF-IDF, source-block
proximity, and same-page evidence. High-confidence question pairs can be automatic;
uncertain or unmatched pairs require a teacher decision.

The paragraph above describes the optional legacy matcher. The default semantic
mode uses `sentence-transformers/all-MiniLM-L6-v2` to shortlist groups and
`cross-encoder/stsb-roberta-base` to compare their members. Defaults are 0.60
cross-encoder similarity, 0.60 minimum SBERT cosine, and 0.05 winner margin for
automatic grouping; 0.30 starts the review range. Environment settings override
these defaults. Scores are not accuracy percentages. Model availability and
performance on real teacher-labeled content must be verified separately.

Teacher content versions use Gemma to propose a Normal baseline and source roles.
Readability checks gate automatic Simplified/Elaborated assignments. Teachers can
correct assignments; displaced sources remain under Other source versions.
Publishing reports failure when required content or audio generation fails.
Normal narration and active Simplified/Elaborated audio are prepared by the
backend, with reuse for unchanged text and voice settings.

See [Teacher publishing validation](docs/TEACHER_PUBLISHING_VALIDATION.md) for
the milestone scope and evaluation still needed before making accuracy claims.

## Guides

Every Markdown file in the repository is listed, with its purpose and status, in
[GUIDES.md](GUIDES.md). The main ones:

| Guide | Covers |
|---|---|
| [backend/learning_path/HANDOFF.md](backend/learning_path/HANDOFF.md) | Using the published learning path from the adaptive rules: API, response shape, remediation |
| [backend/learning_path/CRITERIA.md](backend/learning_path/CRITERIA.md) | How the learning path is built: ordering, prerequisite criteria, hand-check evidence, teacher control |
| [backend/lessons/REGROUPING.md](backend/lessons/REGROUPING.md) | Review grouping changes, and version links when objects change groups |
| [docs/SEMANTIC_GROUPING.md](docs/SEMANTIC_GROUPING.md) | Cross-PDF grouping of learning objects |
| [docs/TEACHER_PUBLISHING_VALIDATION.md](docs/TEACHER_PUBLISHING_VALIDATION.md) | Acceptance checks and evaluation still required |

Files under `docs/superpowers/specs/`, and dated status notes in `docs/`, are
design and status records; each marks where it has been superseded.

## Verification

```powershell
& .\.venv\Scripts\python.exe backend\manage.py migrate
& .\.venv\Scripts\python.exe backend\manage.py test
& .\.venv\Scripts\python.exe backend\manage.py show_learning_path
cd frontend
npm.cmd run build
```
