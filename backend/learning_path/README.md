# learning_path

One learning path per **subtopic**: the order its concepts are taught in, and
which concepts must come before others. The path is saved when a teacher
publishes the subtopic, and read by the adaptive rules.

| Read this | For |
|---|---|
| `HANDOFF.md` | **Using the path** — the API, the response shape, how to remediate with it |
| `CRITERIA.md` | **How the path is built** — ordering rules, the three voting criteria, vetoes, the hand-check evidence |

## Pipeline

```
Groups of learning objects across a subtopic's PDFs
   -> concepts, split passages merged, merged document order   (services/concept_units.py)
   -> proposed prerequisite links: TemO + CSR + IOLR, vetoes,  (services/criteria.py)
      cross-section links held back as pending
   -> at a successful publish:                                  (services/publishing.py)
        store links, keeping every teacher decision            -> ConceptPrerequisite
        order that respects accepted + approved links          -> LearningPathStep
   -> read by the adaptive rules                                (services/published.py,
                                                                 GET topics/<id>/published/)
```

The review screen previews the same order before publishing
(`services/path_builder.py`, `GET topics/<id>/`), using links already stored;
it never runs the criteria itself, because that calls the sentence encoder.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/learning-path/topics/<id>/` | teacher review screen | preview of the path |
| GET | `/api/learning-path/topics/<id>/published/` | signed-in users | the saved path; answers for teachers/admins only |

## Commands

```bash
python manage.py show_learning_path [topic_id] [--preview] [--links]
python manage.py import_hand_check docs/learning_path_hand_check_2026-09-14.json [--dry-run]
```

## History

The first version ordered each PDF separately, with its own strong/medium/weak
evidence rules and a `PrerequisiteEdge` table between learning objects. It was
removed on 2026-09-14 once the subtopic-level path replaced it; see git history
for that design.
