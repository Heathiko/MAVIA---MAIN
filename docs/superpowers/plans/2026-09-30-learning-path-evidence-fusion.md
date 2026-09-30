# Learning-path criteria v5 (evidence fusion) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the v4 keyword/heading criteria with a relatedness gate from sentence embeddings, four direction clues fused by learned weights, and Kahn's topological sort with confidence-aware cycle breaking and a "builds on the latest step" tie-break.

**Architecture:** Five new focused modules under `backend/learning_path/services/` (`concept_text`, `embeddings`, `relatedness`, `clues`, `fusion`) plus `calibration` for stored weights and cutoffs. `criteria.decide_pairs` keeps its signature and output, so storage (`publishing.refresh_prerequisites`), teacher decisions and the adaptive engine are unchanged. `publishing.order_with_links` stays Kahn's algorithm with a new tie-break and weakest-link cycle breaking.

**Tech Stack:** Django 5 / Python, numpy, sentence-transformers (pinned `all-MiniLM-L6-v2`), NLTK Porter stemmer, React + vitest (one graph helper).

**Spec:** `docs/superpowers/specs/2026-09-30-learning-path-evidence-fusion-design.md`

## Global Constraints

- Branch `learning-path-graph-screen`. Commit per task. **Do not push, merge or open a PR** — the user decides.
- Only these paths change: `backend/learning_path/**`, `backend/requirements.txt`, `web-app/src/learning-path/graphModel.js` and its test, `docs/**`. Never `lessons/`, `adaptive/`, `question_generation/`, `course/`.
- No generative model. The only outside parts are the pinned encoder (`sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`) and NLTK's Porter stemmer.
- No keyword or label lists. Stopwords are general English only (no "example", "part", "one", "two", "three", "use", "make", "take", "call").
- Topics 340 and 357 are the **test set**: never change a constant because of their numbers. Development set: gold 62, 79, 152.
- Constants fixed by the spec: minimum sentence 4 words; minimum term 3 letters; name at most 6 terms; G² ≥ 3.84; null percentile 95; accept at confidence ≥ 0.5 with ≥ 2 supporting clues; agreement capped at 0.95; PDF-order weight ≤ half the smallest content weight; default cutoffs `related_cutoff = 0.25`, `meaning_cutoff = 0.30` (measured 2026-09-30, topics 340 × 357).
- The PDF-order clue alone never creates a link (not even pending).
- Naming (spec §11): short descriptive names, no single letters or maths names (`w_k`, `θ`, `s`, `X`) even in loops, no `compute_`/`get_`/`handle_` prefixes, no `helper`/`utils`/`manager`/`v2`/`enhanced`/`robust`. Pairs are `prerequisite`/`dependent`, or `first`/`second` before direction is known. Docstrings: one or two lines, what and why, no "This function …".
- Backend tests run from `backend/`: `python manage.py test learning_path`. Frontend: `cd web-app && npm test`.

**Spec deviations (small, recorded here so reviewers are not surprised):** PDF positions are computed by `concept_text.material_positions(concepts)` from concepts rather than by exposing `concept_units._material_positions` (which works on internal records); calibration lives in its own module `calibration.py` (`load_calibration`, `calibrate`) instead of `fusion.load_weights`, to avoid an import cycle; `clues.py` also holds `pair_votes`, `clue_records` and `meaning_cutoff`; `clues.MEANING_MATCHES` (default 1) is the C3 size fallback switch the spec defines.

## Review Focus

1. **A concept with no full sentence** (a figure whose description is one short line, or empty content) — expected: no crash, no link to or from it. Test in Task 7.
2. **The encoder cannot load** (model not downloaded, offline) — expected: links still derived, all PENDING, evidence `semantic: false`, reason says the meaning check was unavailable. Tests in Tasks 7 and 8.
3. **Rows stored by v4** (evidence without `confidence`, rule `containment`/`reference`) — expected: path still orders, such a row is the first broken in a loop, reason text still renders. Tests in Task 6.
4. **Two concepts with the same title** ("Comparing the Three States" twice) — expected: the name clue abstains, no crash. Test in Task 4.
5. **A missing or malformed `weights.json`** — expected: defaults used, a warning logged, derivation still runs. Test in Task 5.

---

### Task 1: Kendall's τ in the gold report, and the v4 baseline

**Files:**
- Modify: `backend/learning_path/services/gold.py`
- Test: `backend/learning_path/test_gold_report.py`
- Create: `docs/learning-path-v4-baseline-2026-09-30.json`

**Interfaces:**
- Produces: `gold.kendall_tau(order: list[str], expected: list[str]) -> float | None`; report key `"kendall_tau"`.

- [ ] **Step 1: Write the failing tests** — append to `GoldReportTests` in `test_gold_report.py`:

```python
    def test_kendall_tau_is_one_in_order_and_minus_one_reversed(self):
        from .services.gold import kendall_tau

        self.assertEqual(kendall_tau(["a", "b", "c"], ["a", "b", "c"]), 1.0)
        self.assertEqual(kendall_tau(["c", "b", "a"], ["a", "b", "c"]), -1.0)
        self.assertIsNone(kendall_tau(["a"], ["a", "b"]))

    def test_the_report_carries_kendall_tau(self):
        report = gold_report(self.data, self.concepts, [])

        self.assertEqual(report["kendall_tau"], 1.0)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_gold_report`
Expected: FAIL — `ImportError: cannot import name 'kendall_tau'` and `KeyError: 'kendall_tau'`.

- [ ] **Step 3: Implement** — in `gold.py`, add above `gold_report`:

```python
def kendall_tau(order, expected):
    """Agreement between two orders over the keys both contain: 1 same, -1 reversed.

    Replaces the all-or-nothing order match, which fails on a single swap and
    says nothing about how close a path is. ``None`` below two shared keys.
    """
    rank = {}
    for index, key in enumerate(order):
        rank.setdefault(key, index)
    shared = [key for key in expected if key in rank]
    if len(shared) < 2:
        return None
    concordant = discordant = 0
    for index, earlier in enumerate(shared):
        for later in shared[index + 1:]:
            if rank[earlier] < rank[later]:
                concordant += 1
            else:
                discordant += 1
    return (concordant - discordant) / (concordant + discordant)
```

and in the returned dict of `gold_report`, after `"order_matches"`:

```python
        "kendall_tau": kendall_tau(order, data["expected_order"]),
```

- [ ] **Step 4: Run to verify they pass**

Run: `python manage.py test learning_path.test_gold_report`
Expected: PASS.

- [ ] **Step 5: Record the v4 baseline** (v4 is still the live criteria at this point)

Run: `python manage.py evaluate_gold_paths --topics 62 79 152 340 > ../docs/learning-path-v4-baseline-2026-09-30.json`
Expected: a JSON list of four reports, each with `kendall_tau`, `reachable_count`, `forbidden_accepted`.

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/services/gold.py backend/learning_path/test_gold_report.py docs/learning-path-v4-baseline-2026-09-30.json
git commit -m "Report Kendall's tau in the gold report and record the v4 baseline"
```

---

### Task 2: Concept text — sentences, terms, names, PDF positions

**Files:**
- Modify: `backend/requirements.txt` (add `nltk>=3.8`)
- Create: `backend/learning_path/services/concept_text.py`
- Create: `backend/learning_path/testing.py` (test stand-ins, used by later tasks)
- Test: `backend/learning_path/test_concept_text.py`

**Interfaces:**
- Produces:
  - `split_sentences(text: str) -> list[str]`
  - `terms(text: str) -> list[str]` (Porter stems, duplicates kept)
  - `name_terms(title: str) -> tuple[str, ...]` (empty when not a name)
  - `strip_numbering(title: str) -> str`
  - `ConceptText` dataclass: `concept`, `sentences: list[str]`, `pdfs: list`, `sentence_terms: list[list[str]]`, `passages: list[list[str]]`, `name: tuple`, `spelling: dict[str, str]`, `vectors: numpy.ndarray | None`; property `id`.
  - `prepare(concepts, embed=None) -> list[ConceptText]` (`embed(list[str]) -> ndarray` called once for all sentences)
  - `material_positions(concepts) -> dict[material_id, dict[concept_id, int]]`
  - `testing.member(...)`, `testing.concept(id, title, *members, **extra)`, `testing.word_vectors(sentences) -> ndarray`

- [ ] **Step 1: Add the dependency** — append to `backend/requirements.txt`:

```text
nltk>=3.8
```

Run: `python -c "from nltk.stem import PorterStemmer; print(PorterStemmer().stem('fertilization'))"`
Expected: `fertil`

- [ ] **Step 2: Write the failing tests** — create `test_concept_text.py`:

```python
"""Sentences, terms, names and PDF positions the clues read (spec section 4)."""

from django.test import SimpleTestCase

from .services.concept_text import (
    material_positions,
    name_terms,
    prepare,
    split_sentences,
    terms,
)
from .testing import concept, member, word_vectors


class SentenceTests(SimpleTestCase):
    def test_fragments_under_four_words_are_dropped(self):
        text = "Solid. A solid keeps its shape. Particles vibrate in place."

        self.assertEqual(split_sentences(text), ["A solid keeps its shape.", "Particles vibrate in place."])

    def test_line_breaks_split_sentences(self):
        self.assertEqual(
            split_sentences("Melting turns ice to water\nFreezing turns water to ice"),
            ["Melting turns ice to water", "Freezing turns water to ice"],
        )


class TermTests(SimpleTestCase):
    def test_verb_and_noun_forms_share_a_stem(self):
        self.assertEqual(terms("fertilized"), terms("fertilization"))

    def test_general_stopwords_are_dropped(self):
        self.assertEqual(terms("The pollen is carried to the stigma"), terms("pollen carried stigma"))

    def test_lesson_words_are_not_stopwords(self):
        self.assertEqual(len(terms("example part one")), 3)


class NameTests(SimpleTestCase):
    def test_numbering_and_part_suffix_do_not_count(self):
        self.assertEqual(name_terms("7. Everyday Examples (Part 1 of 2)"), tuple(terms("Everyday Examples")))

    def test_a_sentence_like_title_is_not_a_name(self):
        self.assertEqual(name_terms("Matter usually exists in one of three everyday states"), ())


class PrepareTests(SimpleTestCase):
    def test_sentences_remember_their_pdf_and_get_vectors(self):
        solid = concept(
            1, "Solid",
            member("A solid keeps its shape.", material_id=10),
            member("Solid particles vibrate in place.", material_id=11),
        )

        [text] = prepare([solid], embed=word_vectors)

        self.assertEqual(text.pdfs, [10, 11])
        self.assertEqual(text.vectors.shape[0], 2)
        self.assertEqual(len(text.passages), 2)
        self.assertEqual(text.id, 1)

    def test_spelling_keeps_a_readable_word_per_stem(self):
        [text] = prepare([concept(1, "Stamen", "The anther produces tiny pollen grains.")])

        self.assertEqual(text.spelling[terms("anther")[0]], "anther")

    def test_a_concept_with_no_full_sentence_has_no_vectors_rows(self):
        [text] = prepare([concept(1, "Figure", "Solid")], embed=word_vectors)

        self.assertEqual(text.sentences, [])
        self.assertEqual(text.vectors.shape[0], 0)


class PositionTests(SimpleTestCase):
    def test_positions_are_renumbered_per_pdf(self):
        matter = concept(1, "Matter", member("x", material_id=10, order=4), member("x", material_id=11, order=9))
        solid = concept(2, "Solid", member("x", material_id=10, order=7))

        self.assertEqual(material_positions([solid, matter]), {10: {1: 0, 2: 1}, 11: {1: 0}})
```

- [ ] **Step 3: Run to verify they fail**

Run: `python manage.py test learning_path.test_concept_text`
Expected: FAIL — `ModuleNotFoundError: No module named 'learning_path.services.concept_text'`.

- [ ] **Step 4: Implement** — create `services/concept_text.py`:

```python
"""What the learning-path clues read from a concept: sentences, terms, vectors, PDFs.

Nothing here decides anything; it turns grouped learning objects into the
material the relatedness gate and the four clues compare (spec section 4).
"""

import re
from dataclasses import dataclass, field

import numpy as np
from nltk.stem import PorterStemmer

from .text_signals import strip_part_suffix

MIN_SENTENCE_WORDS = 4
MIN_TERM_LETTERS = 3
MAX_NAME_TERMS = 6

# General English only. Words shaped by our lessons ("example", "part", "one")
# are left out on purpose: a list fitted to the lessons we test on is the kind
# of rule v5 removes.
STOP_WORDS = frozenset("""
a about above after again against all also am an and any are as at be because been
before being below between both but by can cannot could did do does doing down
during each few for from further had has have having he her here hers herself him
himself his how i if in into is it its itself just me more most my myself no nor not
now of off on once only or other others our ours ourselves out over own same she
should so some such than that the their theirs them themselves then there these they
this those through to too under until up very was we were what when where which while
who whom why will with would you your yours yourself yourselves
""".split())

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[a-z]+")
_LEADING_NUMBER = re.compile(r"^\s*\d+(?:\.\d+)*\s*[.):-]*\s*")
_stemmer = PorterStemmer()


def split_sentences(text):
    """Sentences of at least four words; shorter fragments are leftover headings."""
    return [
        sentence.strip()
        for sentence in _SENTENCE_BREAK.split(text or "")
        if len(sentence.split()) >= MIN_SENTENCE_WORDS
    ]


def _kept_words(text):
    return [
        word for word in _WORD.findall((text or "").lower())
        if word not in STOP_WORDS and len(word) >= MIN_TERM_LETTERS
    ]


def terms(text):
    """Porter stems of the content words, repeats kept: "fertilized" -> "fertil"."""
    return [_stemmer.stem(word) for word in _kept_words(text)]


def strip_numbering(title):
    """Drop a heading's list number: "7. Everyday Examples" -> "Everyday Examples"."""
    return _LEADING_NUMBER.sub("", title or "").strip()


def name_terms(title):
    """The stems a concept can be named by, or ``()`` when its title is a sentence."""
    stems = tuple(terms(strip_numbering(strip_part_suffix(title or ""))))
    return stems if 0 < len(stems) <= MAX_NAME_TERMS else ()


@dataclass
class ConceptText:
    concept: object
    sentences: list
    pdfs: list
    sentence_terms: list
    passages: list
    name: tuple
    spelling: dict = field(default_factory=dict)
    vectors: object = None

    @property
    def id(self):
        return self.concept.id


def _members(concept):
    return getattr(concept, "members", None) or (concept,)


def prepare(concepts, embed=None):
    """One ``ConceptText`` per concept; ``embed`` is called once for every sentence."""
    texts = []
    for concept in concepts:
        sentences, pdfs, passages, spelling = [], [], [], {}
        for member in _members(concept):
            content = getattr(member, "content", "") or ""
            passages.append(terms(content))
            for word in _kept_words(content):
                spelling.setdefault(_stemmer.stem(word), word)
            for sentence in split_sentences(content):
                sentences.append(sentence)
                pdfs.append(getattr(member, "material_id", None))
        texts.append(ConceptText(
            concept=concept,
            sentences=sentences,
            pdfs=pdfs,
            sentence_terms=[terms(sentence) for sentence in sentences],
            passages=passages,
            name=name_terms(concept.title),
            spelling=spelling,
        ))
    if embed is not None:
        vectors = np.asarray(embed([sentence for text in texts for sentence in text.sentences]))
        start = 0
        for text in texts:
            count = len(text.sentences)
            text.vectors = vectors[start:start + count] if count else np.zeros((0, vectors.shape[1] if vectors.ndim == 2 else 0))
            start += count
    return texts


def material_positions(concepts):
    """``{material id: {concept id: position}}`` -- each PDF's own order of the concepts it teaches."""
    first_seen = {}
    for concept in concepts:
        for member in getattr(concept, "members", None) or ():
            spot = (member.order, getattr(member, "id", 0) or 0)
            seen = first_seen.setdefault(member.material_id, {})
            if concept.id not in seen or spot < seen[concept.id]:
                seen[concept.id] = spot
    return {
        material_id: {concept_id: position for position, concept_id in enumerate(sorted(seen, key=seen.get))}
        for material_id, seen in first_seen.items()
    }
```

Note on the empty-vector case: when no concept in the call has a sentence, `embed([])` must return a 2-D array; `embeddings.embed` and `testing.word_vectors` both do.

- [ ] **Step 5: Create the test stand-ins** — `backend/learning_path/testing.py`:

```python
"""Stand-ins shared by the learning-path tests: concepts, members, a fake encoder."""

import hashlib
from types import SimpleNamespace

import numpy as np

from .services.concept_text import terms

FAKE_DIMENSIONS = 256


def member(content, material_id=1, order=0, title="", section_title=""):
    return SimpleNamespace(
        content=content, material_id=material_id, order=order, title=title, section_title=section_title,
    )


def concept(id, title, *members, **extra):
    """A concept stub; a plain string member becomes one passage in PDF 1."""
    members = tuple(item if not isinstance(item, str) else member(item) for item in members)
    fields = {
        "id": id,
        "title": title,
        "order": extra.pop("order", 0),
        "kind": "text",
        "section_title": members[0].section_title if members else "",
        "content": members[0].content if members else "",
        "member_text": "\n".join(item.content for item in members),
        "members": members,
    }
    fields.update(extra)
    return SimpleNamespace(**fields)


def word_vectors(sentences):
    """A fake encoder: sentences sharing stemmed words get similar vectors."""
    rows = np.zeros((len(sentences), FAKE_DIMENSIONS), dtype="float32")
    for row, sentence in zip(rows, sentences):
        for term in terms(sentence):
            row[int(hashlib.md5(term.encode("utf-8")).hexdigest(), 16) % FAKE_DIMENSIONS] += 1.0
        norm = np.linalg.norm(row)
        if norm:
            row /= norm
    return rows
```

- [ ] **Step 6: Run to verify they pass**

Run: `python manage.py test learning_path.test_concept_text`
Expected: PASS (11 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/learning_path/services/concept_text.py backend/learning_path/testing.py backend/learning_path/test_concept_text.py
git commit -m "Add concept text preparation for the v5 learning-path clues"
```

---

### Task 3: Our own sentence encoder with a cache

**Files:**
- Create: `backend/learning_path/services/embeddings.py`
- Test: `backend/learning_path/test_embeddings.py`

**Interfaces:**
- Produces: `MODEL`, `REVISION`, `DIMENSIONS = 384`, `EncoderUnavailable(RuntimeError)`, `load_encoder()` (cached), `embed(sentences, encoder=None, cache_path=None) -> ndarray (n, dim)`.

- [ ] **Step 1: Write the failing tests** — `test_embeddings.py`:

```python
"""The learning path's own encoder loader and vector cache (spec section 4)."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase

from .services import embeddings


class FakeEncoder:
    def __init__(self):
        self.calls = []

    def encode(self, sentences, **options):
        self.calls.append(list(sentences))
        return np.array([[1.0, 0.0] if "solid" in sentence else [0.0, 1.0] for sentence in sentences])


class EmbedTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cache = Path(folder.name) / "vectors.sqlite3"

    def test_one_row_per_sentence_in_order(self):
        vectors = embeddings.embed(["a solid", "a gas", "a solid"], encoder=FakeEncoder(), cache_path=self.cache)

        self.assertEqual(vectors.tolist(), [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]])

    def test_a_second_call_reads_the_cache(self):
        encoder = FakeEncoder()
        embeddings.embed(["a solid"], encoder=encoder, cache_path=self.cache)
        embeddings.embed(["a solid"], encoder=encoder, cache_path=self.cache)

        self.assertEqual(encoder.calls, [["a solid"]])

    def test_no_sentences_give_an_empty_matrix(self):
        self.assertEqual(embeddings.embed([], encoder=FakeEncoder(), cache_path=self.cache).shape, (0, embeddings.DIMENSIONS))


class LoadTests(SimpleTestCase):
    def test_a_model_that_cannot_load_is_reported(self):
        embeddings.load_encoder.cache_clear()
        self.addCleanup(embeddings.load_encoder.cache_clear)
        with patch.dict(os.environ, {"LEARNING_PATH_ALLOW_MODEL_DOWNLOAD": "0"}), \
                patch("sentence_transformers.SentenceTransformer", side_effect=OSError("no weights")):
            with self.assertRaises(embeddings.EncoderUnavailable):
                embeddings.load_encoder()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_embeddings`
Expected: FAIL — `ImportError: cannot import name 'embeddings'`.

- [ ] **Step 3: Implement** — `services/embeddings.py`:

```python
"""The sentence encoder the learning path reads meaning with.

The same pinned model grouping uses (lessons/services/semantic_grouping.py),
loaded here so the two pipelines can change independently. CPU only, offline
once downloaded. Vectors are normalised, so a dot product is the cosine.
"""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path

import numpy as np
from django.conf import settings

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
DIMENSIONS = 384
_QUERY_CHUNK = 500


class EncoderUnavailable(RuntimeError):
    """The encoder could not be loaded; the learning path falls back to pending links."""


@lru_cache(maxsize=1)
def load_encoder():
    """Load the pinned model from disk, downloading it only when allowed."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EncoderUnavailable("sentence-transformers is not installed") from exc
    allow_download = os.getenv("LEARNING_PATH_ALLOW_MODEL_DOWNLOAD", "True").lower() in {"1", "true", "yes"}
    failure = None
    for local_only in (True, False):
        if not local_only and not allow_download:
            break
        try:
            return SentenceTransformer(MODEL, revision=REVISION, device="cpu", local_files_only=local_only)
        except Exception as exc:  # noqa: BLE001 -- any load failure means "unavailable"
            failure = exc
    raise EncoderUnavailable(f"Could not load {MODEL}") from failure


def _cache_path():
    return Path(settings.BASE_DIR) / "semantic_cache" / "learning_path.sqlite3"


def _key(sentence):
    return hashlib.sha256(f"{MODEL}@{REVISION}:{sentence}".encode("utf-8")).hexdigest()


def embed(sentences, encoder=None, cache_path=None):
    """One normalised vector per sentence, read from the cache where possible."""
    sentences = list(sentences)
    if not sentences:
        return np.zeros((0, DIMENSIONS), dtype="float32")
    path = Path(cache_path) if cache_path else _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = [_key(sentence) for sentence in sentences]
    with closing(sqlite3.connect(path, timeout=10)) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        found = {}
        unique = list(dict.fromkeys(keys))
        for start in range(0, len(unique), _QUERY_CHUNK):
            chunk = unique[start:start + _QUERY_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            rows = connection.execute(f"SELECT key, value FROM vectors WHERE key IN ({placeholders})", chunk)
            found.update((key, json.loads(value)) for key, value in rows)
        missing = [(key, sentence) for key, sentence in dict(zip(keys, sentences)).items() if key not in found]
        if missing:
            encoder = encoder or load_encoder()
            vectors = encoder.encode(
                [sentence for _, sentence in missing],
                batch_size=32, normalize_embeddings=True, show_progress_bar=False,
            )
            fresh = {key: [float(value) for value in vector] for (key, _), vector in zip(missing, vectors)}
            connection.executemany(
                "INSERT OR REPLACE INTO vectors VALUES (?, ?)",
                [(key, json.dumps(vector)) for key, vector in fresh.items()],
            )
            connection.commit()
            found.update(fresh)
    return np.array([found[key] for key in keys], dtype="float32")
```

- [ ] **Step 4: Run to verify they pass**

Run: `python manage.py test learning_path.test_embeddings`
Expected: PASS (4 tests).

- [ ] **Step 5: Check the real model loads** (not a test; the model is cached on this machine)

Run: `python manage.py shell -c "from learning_path.services.embeddings import embed; print(embed(['A solid keeps its shape.']).shape)"`
Expected: `(1, 384)`

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/services/embeddings.py backend/learning_path/test_embeddings.py
git commit -m "Add the learning path's own sentence encoder and vector cache"
```

---

### Task 4: Relatedness and the four direction clues

**Files:**
- Create: `backend/learning_path/services/relatedness.py`
- Create: `backend/learning_path/services/clues.py`
- Test: `backend/learning_path/test_clues.py`

**Interfaces:**
- Consumes: `ConceptText` (`id`, `vectors`, `sentence_terms`, `passages`, `name`, `spelling`) from Task 2.
- Produces:
  - `relatedness.UNRELATED_PERCENTILE = 95`, `best_match_average(first_vectors, second_vectors) -> float`, `relatedness(first, second) -> float`, `related_cutoff(unrelated_pairs) -> float | None`
  - `clues.SIGNIFICANT_G2 = 3.84`, `clues.MEANING_MATCHES = 1`
  - `clues.log_likelihood(count_inside, total_inside, count_outside, total_outside) -> float`
  - `clues.find_term_owners(texts) -> dict[str, concept_id]`
  - `clues.name_vote(prerequisite, dependent) -> (int, dict)`, `term_vote(prerequisite, dependent, term_owners)`, `meaning_vote(prerequisite, dependent, meaning_cutoff)`, `order_vote(prerequisite, dependent, positions)` — each `(vote in {-1, 0, 1}, record)`, vote `+1` meaning "prerequisite first"
  - `clues.meaning_cutoff(unrelated_pairs) -> float | None`
  - `clues.pair_votes(texts, term_owners, positions, related_cutoff, meaning_cutoff, semantic=True)` yielding `{"first", "second", "relatedness", "related", "votes": {"name", "terms", "meaning", "order"}}`
  - `clues.clue_records(prerequisite, dependent, term_owners, positions, meaning_cutoff, semantic=True) -> dict`

- [ ] **Step 1: Write the failing tests** — `test_clues.py`:

```python
"""Relatedness and the four direction clues, each on its own (spec sections 5-6)."""

from types import SimpleNamespace

import numpy as np
from django.test import SimpleTestCase

from .services import clues
from .services.clues import (
    SIGNIFICANT_G2,
    find_term_owners,
    log_likelihood,
    meaning_cutoff,
    meaning_vote,
    name_vote,
    order_vote,
    pair_votes,
    term_vote,
)
from .services.concept_text import prepare, terms
from .services.relatedness import best_match_average, related_cutoff, relatedness
from .testing import concept, member, word_vectors


def vectors(*rows):
    return SimpleNamespace(vectors=np.array(rows, dtype="float32"))


class RelatednessTests(SimpleTestCase):
    def test_best_match_average_takes_each_sentences_closest_match(self):
        self.assertAlmostEqual(best_match_average(np.array([[1.0, 0.0]]), np.array([[1.0, 0.0], [0.0, 1.0]])), 1.0)

    def test_relatedness_is_symmetric(self):
        first, second = vectors([1.0, 0.0], [0.0, 1.0]), vectors([1.0, 0.0])

        self.assertAlmostEqual(relatedness(first, second), relatedness(second, first))

    def test_a_concept_without_sentences_is_related_to_nothing(self):
        self.assertEqual(relatedness(vectors([1.0, 0.0]), SimpleNamespace(vectors=np.zeros((0, 2)))), 0.0)

    def test_the_cutoff_is_the_95th_percentile_of_unrelated_pairs(self):
        pairs = [(vectors([1.0, 0.0]), vectors([np.cos(angle), np.sin(angle)])) for angle in np.linspace(0, 1.5, 21)]

        self.assertAlmostEqual(related_cutoff(pairs), float(np.percentile([relatedness(*pair) for pair in pairs], 95)))
        self.assertIsNone(related_cutoff([]))


class NameVoteTests(SimpleTestCase):
    def test_a_concept_whose_text_names_another_comes_after_it(self):
        stamen, pollination = prepare([
            concept(1, "Stamen", "The stamen makes pollen grains."),
            concept(2, "Pollination", "Pollen leaves the stamen on the wind."),
        ])

        self.assertEqual(name_vote(stamen, pollination)[0], 1)
        self.assertEqual(name_vote(pollination, stamen)[0], -1)

    def test_two_concepts_with_one_title_do_not_vote(self):
        first, second = prepare([
            concept(1, "Comparing the Three States", "Comparing the three states shows shape."),
            concept(2, "Comparing the Three States", "Comparing the three states shows volume."),
        ])

        self.assertEqual(name_vote(first, second)[0], 0)


class TermOwnerTests(SimpleTestCase):
    def setUp(self):
        self.stamen, self.pollination, self.pistil = prepare([
            concept(1, "Stamen", "The anther makes pollen grains. " * 8),
            concept(2, "Pollination", "Pollen travels from an anther to a stigma."),
            concept(3, "Pistil", "The stigma is sticky and holds the style. " * 8),
        ])
        self.owners = find_term_owners([self.stamen, self.pollination, self.pistil])

    def test_log_likelihood_needs_real_evidence(self):
        self.assertGreater(log_likelihood(10, 100, 10, 1000), SIGNIFICANT_G2)
        self.assertLess(log_likelihood(1, 6, 1, 9), SIGNIFICANT_G2)

    def test_a_term_belongs_where_it_is_over_represented(self):
        self.assertEqual(self.owners[terms("anther")[0]], 1)
        self.assertEqual(self.owners[terms("stigma")[0]], 3)

    def test_using_a_term_another_explains_puts_that_concept_first(self):
        vote, record = term_vote(self.stamen, self.pollination, self.owners)

        self.assertEqual(vote, 1)
        self.assertIn("anther", record["owned"])


class MeaningVoteTests(SimpleTestCase):
    def test_sentences_about_another_concept_put_it_first(self):
        stamen = vectors([1.0, 0.0], [0.0, 1.0])
        pollination = vectors([1.0, 0.0])

        vote, record = meaning_vote(stamen, pollination, 0.5)

        self.assertEqual(vote, 1)
        self.assertEqual((record["use"], record["use_back"]), (1.0, 0.5))

    def test_the_cutoff_comes_from_unrelated_sentences(self):
        pairs = [(vectors([1.0, 0.0]), vectors([0.0, 1.0], [0.6, 0.8]))]

        self.assertAlmostEqual(meaning_cutoff(pairs), float(np.percentile([0.6, 0.0, 0.6], 95)))

    def test_two_best_matches_can_be_averaged(self):
        self.addCleanup(setattr, clues, "MEANING_MATCHES", clues.MEANING_MATCHES)
        clues.MEANING_MATCHES = 2
        holder, target = vectors([1.0, 0.0]), vectors([1.0, 0.0], [0.0, 1.0])

        self.assertEqual(clues.meaning_use(holder, target, 0.6), 0.0)


class OrderVoteTests(SimpleTestCase):
    def test_all_pdfs_agreeing_votes(self):
        positions = {10: {1: 0, 2: 1}, 11: {1: 3, 2: 5}}

        self.assertEqual(order_vote(SimpleNamespace(id=1), SimpleNamespace(id=2), positions)[0], 1)

    def test_one_pdf_never_votes(self):
        self.assertEqual(order_vote(SimpleNamespace(id=1), SimpleNamespace(id=2), {10: {1: 0, 2: 1}})[0], 0)

    def test_pdfs_that_disagree_do_not_vote(self):
        positions = {10: {1: 0, 2: 1}, 11: {1: 1, 2: 0}}

        self.assertEqual(order_vote(SimpleNamespace(id=1), SimpleNamespace(id=2), positions)[0], 0)


class PairVoteTests(SimpleTestCase):
    def test_every_pair_is_voted_once_as_first_before_second(self):
        texts = prepare([
            concept(1, "Stamen", "The stamen makes pollen grains."),
            concept(2, "Pollination", "Pollen leaves the stamen on the wind."),
            concept(3, "Fruit", "A fruit grows around the seed."),
        ], embed=word_vectors)

        pairs = list(pair_votes(texts, {}, {}, related_cutoff=0.1, meaning_cutoff=0.3))

        self.assertEqual([(pair["first"].id, pair["second"].id) for pair in pairs], [(1, 2), (1, 3), (2, 3)])
        self.assertEqual(pairs[0]["votes"]["name"], 1)
        self.assertEqual(set(pairs[0]["votes"]), {"name", "terms", "meaning", "order"})

    def test_without_the_encoder_every_pair_passes_and_meaning_abstains(self):
        texts = prepare([concept(1, "Stamen", "The stamen makes pollen grains."), concept(2, "Fruit", "A fruit grows around the seed.")])

        [pair] = pair_votes(texts, {}, {}, related_cutoff=0.25, meaning_cutoff=0.3, semantic=False)

        self.assertTrue(pair["related"])
        self.assertIsNone(pair["relatedness"])
        self.assertEqual(pair["votes"]["meaning"], 0)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_clues`
Expected: FAIL — `ImportError: cannot import name 'clues'`.

- [ ] **Step 3: Implement relatedness** — `services/relatedness.py`:

```python
"""Relatedness between two concepts (spec section 5).

Symmetric, so it says whether two concepts can be connected, never which comes
first. Best-match averaging, as BERTScore does over tokens: one shared idea
between two broader concepts still counts.
"""

import numpy as np

UNRELATED_PERCENTILE = 95


def _has_rows(vectors):
    return vectors is not None and len(vectors) > 0


def best_match_average(first_vectors, second_vectors):
    """Mean, over the first concept's sentences, of each one's closest sentence in the second."""
    if not (_has_rows(first_vectors) and _has_rows(second_vectors)):
        return 0.0
    return float((first_vectors @ second_vectors.T).max(axis=1).mean())


def relatedness(first, second):
    return (
        best_match_average(first.vectors, second.vectors)
        + best_match_average(second.vectors, first.vectors)
    ) / 2


def related_cutoff(unrelated_pairs):
    """The 95th percentile of relatedness between concepts known to be unrelated."""
    scores = [relatedness(first, second) for first, second in unrelated_pairs]
    return float(np.percentile(scores, UNRELATED_PERCENTILE)) if scores else None
```

- [ ] **Step 4: Implement the clues** — `services/clues.py`:

```python
"""The four direction clues (spec section 6).

Each looks at one pair and votes +1 (prerequisite first), -1 (dependent first)
or 0, with the numbers behind the vote. A clue votes whenever its evidence
differs at all; how far to trust it is fusion's job, so no clue has a threshold
that could be fitted to a lesson.
"""

import math
from collections import Counter

import numpy as np

from .relatedness import UNRELATED_PERCENTILE, relatedness

# Chi-squared with one degree of freedom at p < 0.05 (Dunning 1993).
SIGNIFICANT_G2 = 3.84
# How many best matches the meaning clue averages; 2 is the size fallback the
# spec defines, switched on only if the development set shows a size bias.
MEANING_MATCHES = 1


def _sign(difference):
    return (difference > 0) - (difference < 0)


def name_use(holder, target):
    """Share of the holder's sentences containing every stem of the target's name."""
    if not target.name or not holder.sentence_terms:
        return 0.0
    needed = set(target.name)
    return sum(1 for stems in holder.sentence_terms if needed <= set(stems)) / len(holder.sentence_terms)


def name_vote(prerequisite, dependent):
    use, use_back = name_use(dependent, prerequisite), name_use(prerequisite, dependent)
    return _sign(use - use_back), {"use": round(use, 3), "use_back": round(use_back, 3)}


def log_likelihood(count_inside, total_inside, count_outside, total_outside):
    """Dunning's G2 for "this term is characteristic of the inside text"."""
    total = total_inside + total_outside
    used = count_inside + count_outside
    observed = (count_inside, total_inside - count_inside, count_outside, total_outside - count_outside)
    expected = (
        total_inside * used / total, total_inside * (total - used) / total,
        total_outside * used / total, total_outside * (total - used) / total,
    )
    return 2 * sum(seen * math.log(seen / guess) for seen, guess in zip(observed, expected) if seen > 0)


def find_term_owners(texts):
    """``{stem: concept id}`` for terms significantly over-represented in one concept.

    Only terms at least two concepts use can link anything, so only those are owned.
    """
    counts = {text.id: Counter(term for passage in text.passages for term in passage) for text in texts}
    sizes = {concept_id: sum(counter.values()) for concept_id, counter in counts.items()}
    grand_total = sum(sizes.values())
    owners = {}
    for term in {term for counter in counts.values() for term in counter}:
        users = [concept_id for concept_id in counts if counts[concept_id][term]]
        if len(users) < 2:
            continue
        total_use = sum(counts[concept_id][term] for concept_id in users)
        best_score, best_owner = SIGNIFICANT_G2, None
        for concept_id in users:
            inside = counts[concept_id][term]
            outside_size = grand_total - sizes[concept_id]
            if not outside_size or inside / sizes[concept_id] <= (total_use - inside) / outside_size:
                continue
            score = log_likelihood(inside, sizes[concept_id], total_use - inside, outside_size)
            if score >= best_score:
                best_score, best_owner = score, concept_id
        if best_owner is not None:
            owners[term] = best_owner
    return owners


def term_use(holder, target, term_owners):
    """Share of the holder's passages using a term the target owns."""
    passages = [passage for passage in holder.passages if passage]
    if not passages:
        return 0.0
    return sum(1 for passage in passages if any(term_owners.get(term) == target.id for term in passage)) / len(passages)


def term_vote(prerequisite, dependent, term_owners):
    use = term_use(dependent, prerequisite, term_owners)
    use_back = term_use(prerequisite, dependent, term_owners)
    owned = sorted({
        dependent.spelling.get(term, term)
        for passage in dependent.passages for term in passage
        if term_owners.get(term) == prerequisite.id
    })
    return _sign(use - use_back), {"owned": owned, "use": round(use, 3), "use_back": round(use_back, 3)}


def meaning_use(holder, target, meaning_cutoff):
    """Share of the holder's sentences whose closest match in the target clears the cutoff."""
    if holder.vectors is None or target.vectors is None or not len(holder.vectors) or not len(target.vectors):
        return 0.0
    similarity = holder.vectors @ target.vectors.T
    matches = min(MEANING_MATCHES, similarity.shape[1])
    closest = np.sort(similarity, axis=1)[:, -matches:].mean(axis=1)
    return float((closest > meaning_cutoff).mean())


def meaning_vote(prerequisite, dependent, meaning_cutoff):
    use = meaning_use(dependent, prerequisite, meaning_cutoff)
    use_back = meaning_use(prerequisite, dependent, meaning_cutoff)
    return _sign(use - use_back), {"use": round(use, 3), "use_back": round(use_back, 3)}


def meaning_cutoff(unrelated_pairs):
    """The 95th percentile of a sentence's closest match in an unrelated concept."""
    matches = []
    for first, second in unrelated_pairs:
        if first.vectors is None or second.vectors is None or not len(first.vectors) or not len(second.vectors):
            continue
        similarity = first.vectors @ second.vectors.T
        matches.extend(similarity.max(axis=1).tolist())
        matches.extend(similarity.max(axis=0).tolist())
    return float(np.percentile(matches, UNRELATED_PERCENTILE)) if matches else None


def order_vote(prerequisite, dependent, positions):
    """PDF order, only when two or more PDFs teach both and all agree."""
    shared = [spots for spots in positions.values() if prerequisite.id in spots and dependent.id in spots]
    first_count = sum(1 for spots in shared if spots[prerequisite.id] < spots[dependent.id])
    record = {"pdfs": len(shared), "agree": max(first_count, len(shared) - first_count)}
    if len(shared) < 2:
        return 0, record
    if first_count == len(shared):
        return 1, record
    if first_count == 0:
        return -1, record
    return 0, record


def pair_votes(texts, term_owners, positions, related_cutoff, meaning_cutoff, semantic=True):
    """Relatedness and the four votes for every pair, each read as "first before second"."""
    for index, first in enumerate(texts):
        for second in texts[index + 1:]:
            score = relatedness(first, second) if semantic else None
            yield {
                "first": first,
                "second": second,
                "relatedness": score,
                "related": (not semantic) or score >= related_cutoff,
                "votes": {
                    "name": name_vote(first, second)[0],
                    "terms": term_vote(first, second, term_owners)[0],
                    "meaning": meaning_vote(first, second, meaning_cutoff)[0] if semantic else 0,
                    "order": order_vote(first, second, positions)[0],
                },
            }


def clue_records(prerequisite, dependent, term_owners, positions, meaning_cutoff, semantic=True):
    """The numbers behind each clue for "prerequisite before dependent", for the stored evidence."""
    records = {
        "name": name_vote(prerequisite, dependent)[1],
        "terms": term_vote(prerequisite, dependent, term_owners)[1],
        "order": order_vote(prerequisite, dependent, positions)[1],
    }
    if semantic:
        records["meaning"] = meaning_vote(prerequisite, dependent, meaning_cutoff)[1]
    return records
```

- [ ] **Step 5: Run to verify they pass**

Run: `python manage.py test learning_path.test_clues`
Expected: PASS (17 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/services/relatedness.py backend/learning_path/services/clues.py backend/learning_path/test_clues.py
git commit -m "Add the relatedness gate and the four direction clues"
```

---

### Task 5: Fusion, calibration and the calibrate command

**Files:**
- Create: `backend/learning_path/services/fusion.py`
- Create: `backend/learning_path/services/calibration.py`
- Create: `backend/learning_path/management/commands/calibrate_learning_path.py`
- Test: `backend/learning_path/test_fusion.py`

**Interfaces:**
- Consumes: Task 4's `pair_votes`, `find_term_owners`, `meaning_cutoff`, `related_cutoff`; Task 2's `prepare`, `material_positions`; Task 3's `embed`, `MODEL`, `REVISION`; `gold.load_gold`.
- Produces:
  - `fusion.CLUES = ("name", "terms", "meaning", "order")`, `fusion.CONTENT_CLUES`, `fusion.ACCEPTED/PENDING/PARALLEL` (`"accepted"`, `"pending"`, `"parallel"`)
  - `fusion.learn_weights(vote_rows: list[dict]) -> (weights: dict, agreement: dict)`
  - `fusion.combine(votes, weights) -> (score: float, confidence: float)`
  - `fusion.verdict(votes, score, confidence, semantic=True) -> (verdict: str, direction: int)`
  - `calibration.CALIBRATION` (path), `calibration.DEFAULTS`, `calibration.load_calibration(path=CALIBRATION) -> {"weights", "related_cutoff", "meaning_cutoff", "source"}` (always a fresh copy)
  - `calibration.calibrate(texts_by_topic, positions_by_topic, topics, unrelated_topic_pairs) -> dict`
  - Command: `python manage.py calibrate_learning_path --topics 62 79 --unrelated 62:79 [--out PATH]`

- [ ] **Step 1: Write the failing tests** — `test_fusion.py`:

```python
"""Weights, confidence, verdicts and the stored calibration (spec section 7)."""

import json
import math
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from .services.calibration import DEFAULTS, load_calibration
from .services.fusion import ACCEPTED, PARALLEL, PENDING, combine, learn_weights, verdict
from .testing import word_vectors

EQUAL = {"name": 1.0, "terms": 1.0, "meaning": 1.0, "order": 0.5}


def votes(name=0, terms=0, meaning=0, order=0):
    return {"name": name, "terms": terms, "meaning": meaning, "order": order}


class LearnWeightTests(SimpleTestCase):
    def test_a_clue_that_agrees_with_the_others_weighs_more(self):
        rows = [votes(1, 1, 1, 0)] * 9 + [votes(-1, 1, 1, 0)]

        weights, agreement = learn_weights(rows)

        self.assertAlmostEqual(agreement["terms"], 1.0)
        self.assertAlmostEqual(weights["terms"], math.log(0.95 / 0.05))
        self.assertGreater(weights["terms"], weights["name"])

    def test_a_clue_no_better_than_chance_weighs_nothing(self):
        rows = [votes(1, 1, 1, 0), votes(-1, 1, 1, 0)]

        self.assertEqual(learn_weights(rows)[0]["name"], 0.0)

    def test_pdf_order_never_outweighs_a_content_clue(self):
        rows = [votes(1, 1, 1, 1)] * 10

        weights, _ = learn_weights(rows)

        self.assertLessEqual(weights["order"], min(weights[c] for c in ("name", "terms", "meaning")) / 2)


class VerdictTests(SimpleTestCase):
    def test_two_agreeing_clues_with_most_of_the_weight_are_accepted(self):
        pair = votes(terms=1, meaning=1, order=1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence), (ACCEPTED, 1))

    def test_one_content_clue_is_only_pending(self):
        pair = votes(terms=-1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence), (PENDING, -1))

    def test_pdf_order_alone_makes_no_link(self):
        pair = votes(order=1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence)[0], PARALLEL)

    def test_clues_that_cancel_are_parallel(self):
        pair = votes(terms=1, meaning=-1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence)[0], PARALLEL)

    def test_without_the_encoder_nothing_is_accepted(self):
        pair = votes(name=1, terms=1, order=1)
        score, confidence = combine(pair, EQUAL)

        self.assertEqual(verdict(pair, score, confidence, semantic=False), (PENDING, 1))


class CalibrationFileTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "weights.json"

    def test_a_missing_file_gives_the_defaults(self):
        calibration = load_calibration(self.path)

        self.assertEqual(calibration["weights"], DEFAULTS["weights"])
        self.assertEqual(calibration["source"], "defaults")

    def test_a_malformed_file_gives_the_defaults_and_a_warning(self):
        self.path.write_text("{not json", encoding="utf-8")

        with self.assertLogs("learning_path.services.calibration", level="WARNING"):
            calibration = load_calibration(self.path)

        self.assertEqual(calibration["related_cutoff"], DEFAULTS["related_cutoff"])

    def test_the_defaults_are_never_shared(self):
        load_calibration(self.path)["weights"]["name"] = 0.0

        self.assertEqual(DEFAULTS["weights"]["name"], 1.0)

    def test_the_command_writes_a_readable_file(self):
        with patch("learning_path.management.commands.calibrate_learning_path.embed", word_vectors):
            call_command(
                "calibrate_learning_path", "--topics", "62", "79", "--unrelated", "62:79",
                "--out", str(self.path), stdout=StringIO(),
            )

        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["topics"], [62, 79])
        self.assertEqual(set(stored["weights"]), {"name", "terms", "meaning", "order"})
        self.assertEqual(load_calibration(self.path)["source"], str(self.path))
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_fusion`
Expected: FAIL — `ModuleNotFoundError: No module named 'learning_path.services.calibration'`.

- [ ] **Step 3: Implement fusion** — `services/fusion.py`:

```python
"""Combining the clues into one confidence and verdict (spec section 7).

Weights come from how often each clue agrees with the others -- log-odds
weighting of independent voters (Dawid & Skene 1979) -- so no answer key is
read and nothing is fitted to one lesson.
"""

import math

CLUES = ("name", "terms", "meaning", "order")
CONTENT_CLUES = ("name", "terms", "meaning")

ACCEPTED = "accepted"
PENDING = "pending"
PARALLEL = "parallel"

ACCEPT_CONFIDENCE = 0.5
MIN_SUPPORTING_CLUES = 2
MAX_AGREEMENT = 0.95


def _log_odds(agreement):
    if agreement <= 0.5:
        return 0.0
    agreement = min(agreement, MAX_AGREEMENT)
    return math.log(agreement / (1 - agreement))


def learn_weights(vote_rows):
    """``(weights, agreement)`` per clue, from agreement with the other clues' majority."""
    agreement = {}
    for clue in CLUES:
        agreeing = counted = 0
        for votes in vote_rows:
            if not votes[clue]:
                continue
            others = sum(votes[other] for other in CLUES if other != clue)
            if not others:
                continue
            counted += 1
            agreeing += (votes[clue] > 0) == (others > 0)
        agreement[clue] = agreeing / counted if counted else 0.5
    weights = {clue: _log_odds(agreement[clue]) for clue in CLUES}
    content = [weights[clue] for clue in CONTENT_CLUES if weights[clue] > 0]
    weights["order"] = min(weights["order"], min(content) / 2 if content else 0.0)
    return weights, agreement


def combine(votes, weights):
    """``(score, confidence)``: the sign of the score is the direction; an abstaining clue lowers confidence."""
    score = sum(weights[clue] * votes[clue] for clue in CLUES)
    total = sum(weights[clue] for clue in CLUES)
    return score, (abs(score) / total if total else 0.0)


def verdict(votes, score, confidence, semantic=True):
    """``(verdict, direction)``; direction +1 means "first before second"."""
    direction = (score > 0) - (score < 0)
    supporting = [clue for clue in CLUES if direction and votes[clue] == direction]
    if not any(clue in CONTENT_CLUES for clue in supporting):
        return PARALLEL, 0
    if semantic and confidence >= ACCEPT_CONFIDENCE and len(supporting) >= MIN_SUPPORTING_CLUES:
        return ACCEPTED, direction
    return PENDING, direction
```

- [ ] **Step 4: Implement calibration** — `services/calibration.py`:

```python
"""Clue weights and similarity cutoffs, learned once and stored for the whole group.

Weights are not recomputed when a screen opens, so a new upload never quietly
changes another topic's links. ``calibrate_learning_path`` writes the file.
"""

import copy
import json
import logging
from datetime import date
from pathlib import Path

from .clues import find_term_owners, meaning_cutoff, pair_votes
from .embeddings import MODEL, REVISION
from .fusion import CLUES, learn_weights
from .relatedness import related_cutoff

logger = logging.getLogger(__name__)

CALIBRATION = Path(__file__).resolve().parent.parent / "calibration" / "weights.json"

# Used until the command has been run. Cutoffs measured 2026-09-30 on topics
# 340 x 357 (150 concept pairs, 2005 sentence matches).
DEFAULTS = {
    "weights": {"name": 1.0, "terms": 1.0, "meaning": 1.0, "order": 0.5},
    "related_cutoff": 0.25,
    "meaning_cutoff": 0.30,
    "source": "defaults",
}


def load_calibration(path=CALIBRATION):
    """The stored calibration, or the defaults when the file is missing or unreadable."""
    try:
        stored = json.loads(Path(path).read_text(encoding="utf-8"))
        return {
            "weights": {clue: float(stored["weights"][clue]) for clue in CLUES},
            "related_cutoff": float(stored["related_cutoff"]),
            "meaning_cutoff": float(stored["meaning_cutoff"]),
            "source": str(path),
        }
    except FileNotFoundError:
        return copy.deepcopy(DEFAULTS)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Ignoring learning-path calibration %s: %s", path, exc)
        return copy.deepcopy(DEFAULTS)


def calibrate(texts_by_topic, positions_by_topic, topics, unrelated_topic_pairs):
    """Cutoffs from topics in different subjects, then weights from the related pairs of ``topics``."""
    unrelated = [
        (first, second)
        for first_topic, second_topic in unrelated_topic_pairs
        for first in texts_by_topic[first_topic]
        for second in texts_by_topic[second_topic]
    ]
    related = related_cutoff(unrelated)
    meaning = meaning_cutoff(unrelated)
    if related is None or meaning is None:
        raise ValueError("the unrelated topics have no sentences to measure")
    rows = []
    for topic in topics:
        texts = texts_by_topic[topic]
        owners = find_term_owners(texts)
        rows.extend(
            pair["votes"]
            for pair in pair_votes(texts, owners, positions_by_topic[topic], related, meaning)
            if pair["related"]
        )
    weights, agreement = learn_weights(rows)
    return {
        "model": MODEL,
        "revision": REVISION,
        "date": date.today().isoformat(),
        "topics": sorted(topics),
        "unrelated": [list(pair) for pair in unrelated_topic_pairs],
        "related_cutoff": round(related, 4),
        "meaning_cutoff": round(meaning, 4),
        "weights": {clue: round(weight, 4) for clue, weight in weights.items()},
        "agreement": {clue: round(value, 4) for clue, value in agreement.items()},
        "pairs": len(rows),
    }
```

- [ ] **Step 5: Implement the command** — `management/commands/calibrate_learning_path.py`:

```python
"""Learn the learning path's clue weights and cutoffs from frozen topics.

Topics are gold fixtures (fixtures/gold_topic_<id>.json), so a run can be
repeated exactly. No answer key is read: weights come from how often each clue
agrees with the others, cutoffs from pairs of topics in different subjects.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from learning_path.services.calibration import CALIBRATION, calibrate
from learning_path.services.concept_text import material_positions, prepare
from learning_path.services.embeddings import embed
from learning_path.services.gold import load_gold


class Command(BaseCommand):
    help = "Learn clue weights and similarity cutoffs; write learning_path/calibration/weights.json."

    def add_arguments(self, parser):
        parser.add_argument("--topics", nargs="+", type=int, required=True, help="topics whose pairs teach the weights")
        parser.add_argument("--unrelated", nargs="+", required=True, help="topics from different subjects, e.g. 340:357")
        parser.add_argument("--out", default=str(CALIBRATION))

    def handle(self, *args, topics, unrelated, out, **options):
        pairs = []
        for pair in unrelated:
            try:
                first, second = (int(part) for part in pair.split(":"))
            except ValueError:
                raise CommandError(f"--unrelated takes topic pairs like 340:357, not {pair!r}")
            pairs.append((first, second))

        texts, positions = {}, {}
        for topic in sorted(set(topics) | {topic for pair in pairs for topic in pair}):
            _, concepts = load_gold(topic)
            texts[topic] = prepare(concepts, embed=embed)
            positions[topic] = material_positions(concepts)

        result = calibrate(texts, positions, topics, pairs)
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}: {json.dumps(result['weights'])}"))
```

- [ ] **Step 6: Run to verify they pass**

Run: `python manage.py test learning_path.test_fusion`
Expected: PASS (12 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/learning_path/services/fusion.py backend/learning_path/services/calibration.py backend/learning_path/management/commands/calibrate_learning_path.py backend/learning_path/test_fusion.py
git commit -m "Add clue fusion, stored calibration and the calibrate command"
```

---

### Task 6: Kahn with weakest-link cycle breaking, the new tie-break and redundant links

**Files:**
- Modify: `backend/learning_path/services/publishing.py` (`order_with_links`, `save_learning_path`, new `break_cycles`, `redundant_links`, `path_link_confidence`; remove the `structural_role` import and `_ROLE_RANK`)
- Modify: `backend/learning_path/services/path_builder.py` (pass confidence; `redundant` on each shown prerequisite and each edge)
- Test: `backend/learning_path/test_publishing.py` (replace `StructuralOrderTests`)

**Interfaces:**
- Produces:
  - `publishing.break_cycles(links, confidence=None) -> (kept: set, ignored: list)` — `confidence` maps `(before, after)` to a float; a link missing from it is a teacher link and is never removed while a derived link is in the loop.
  - `publishing.redundant_links(links) -> set`
  - `publishing.order_with_links(concepts, links, confidence=None, build_on_latest=True) -> (ordered, depth, ignored)`
  - `publishing.path_link_confidence(node, concept_ids) -> dict` (derived `accepted` rows only; v4 rows without a confidence read as `0.0`)
  - `path_builder` step prerequisite entries and edges carry `"redundant": bool`.

- [ ] **Step 1: Write the failing tests** — in `test_publishing.py`, delete class `StructuralOrderTests` and add:

```python
from django.test import SimpleTestCase

from .services.path_builder import build_topic_path
from .services.publishing import break_cycles, path_link_confidence, redundant_links


class CycleTests(SimpleTestCase):
    def test_the_least_confident_link_in_a_loop_is_dropped(self):
        kept, ignored = break_cycles({(1, 2), (2, 3), (3, 1)}, {(1, 2): 0.9, (2, 3): 0.4, (3, 1): 0.7})

        self.assertEqual(ignored, [(2, 3)])
        self.assertEqual(kept, {(1, 2), (3, 1)})

    def test_a_teacher_link_stays_while_a_derived_one_can_go(self):
        kept, ignored = break_cycles({(1, 2), (2, 1)}, {(2, 1): 0.99})

        self.assertEqual(ignored, [(2, 1)])

    def test_links_without_a_loop_are_all_kept(self):
        self.assertEqual(break_cycles({(1, 2), (2, 3)}), ({(1, 2), (2, 3)}, []))


class RedundantLinkTests(SimpleTestCase):
    def test_a_link_a_longer_chain_already_implies_is_redundant(self):
        self.assertEqual(redundant_links({(1, 2), (2, 3), (1, 3)}), {(1, 3)})

    def test_a_plain_chain_has_nothing_redundant(self):
        self.assertEqual(redundant_links({(1, 2), (2, 3)}), set())


class TieBreakTests(SimpleTestCase):
    def setUp(self):
        self.concepts = [SimpleNamespace(id=1, title="Solid"), SimpleNamespace(id=2, title="Changing"),
                         SimpleNamespace(id=3, title="Examples")]

    def test_a_concept_building_on_the_step_just_placed_comes_next(self):
        ordered, _, _ = order_with_links(self.concepts, [(1, 3)])

        self.assertEqual([concept.id for concept in ordered], [1, 3, 2])

    def test_pdf_order_alone_when_the_rule_is_off(self):
        ordered, _, _ = order_with_links(self.concepts, [(1, 3)], build_on_latest=False)

        self.assertEqual([concept.id for concept in ordered], [1, 2, 3])

    def test_a_loop_is_broken_at_its_weakest_link(self):
        ordered, _, ignored = order_with_links(self.concepts, [(1, 2), (2, 1)], {(1, 2): 0.9, (2, 1): 0.2})

        self.assertEqual(ignored, [(2, 1)])
        self.assertEqual([concept.id for concept in ordered][:2], [1, 2])


class StoredConfidenceTests(PublishingFixture):
    def test_a_v4_row_without_confidence_reads_as_zero(self):
        ConceptPrerequisite.objects.create(
            outline_node=self.topic, prerequisite=self.groups["Matter"], dependent=self.groups["Solid"],
            status="accepted", source="derived", evidence={"rule": "containment", "containment": {"heading": "matter"}},
        )
        ids = {group.id for group in self.groups.values()}

        self.assertEqual(path_link_confidence(self.topic, ids), {(self.groups["Matter"].id, self.groups["Solid"].id): 0.0})

    def test_a_redundant_prerequisite_is_flagged_for_the_screen(self):
        for before, after in (("Matter", "Solid"), ("Solid", "Liquid"), ("Matter", "Liquid")):
            ConceptPrerequisite.objects.create(
                outline_node=self.topic, prerequisite=self.groups[before], dependent=self.groups[after],
                status="approved", source="teacher",
            )

        with self._derive():
            path = build_topic_path(self.topic.id)

        liquid = next(step for step in path["steps"] if step["title"] == "Liquid")
        flags = {entry["title"]: entry["redundant"] for entry in liquid["prerequisites"]}
        self.assertEqual(flags, {"Matter": True, "Solid": False})
```

Move the `from django.test import SimpleTestCase` and the two new imports into the existing import block at the top of the file.

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_publishing`
Expected: FAIL — `ImportError: cannot import name 'break_cycles'`.

- [ ] **Step 3: Implement in `publishing.py`** — replace the `from .concepts import structural_role` import with `import math` and `from collections import defaultdict` (with the other imports), delete `_ROLE_RANK`, and replace `order_with_links` with:

```python
def _find_cycle(links):
    """The links of one loop, or ``None`` when the links form no loop."""
    successors = defaultdict(list)
    for before, after in links:
        successors[before].append(after)
    state, stack = {}, []

    def visit(concept_id):
        state[concept_id] = "open"
        stack.append(concept_id)
        for following in sorted(successors[concept_id]):
            if state.get(following) == "open":
                loop = stack[stack.index(following):] + [following]
                return list(zip(loop, loop[1:]))
            if following not in state:
                found = visit(following)
                if found:
                    return found
        state[concept_id] = "done"
        stack.pop()
        return None

    for concept_id in sorted(successors):
        if concept_id not in state:
            found = visit(concept_id)
            if found:
                return found
    return None


def break_cycles(links, confidence=None):
    """Drop the least confident derived link of each loop until none is left.

    A link missing from ``confidence`` is the teacher's and outranks any
    derived link, so a loop is always broken at something the criteria said.
    """
    confidence = confidence or {}
    kept, ignored = set(links), []
    while True:
        loop = _find_cycle(kept)
        if not loop:
            return kept, ignored
        weakest = min(loop, key=lambda link: (confidence.get(link, math.inf), link))
        kept.discard(weakest)
        ignored.append(weakest)


def redundant_links(links):
    """Links a longer chain already implies: A->C when A->B->C exists."""
    links = set(links)
    successors = defaultdict(set)
    for before, after in links:
        successors[before].add(after)
    redundant = set()
    for before, after in links:
        seen, waiting = set(), [following for following in successors[before] if following != after]
        while waiting:
            current = waiting.pop()
            if current == after:
                redundant.add((before, after))
                break
            if current not in seen:
                seen.add(current)
                waiting.extend(successors[current])
    return redundant


def order_with_links(concepts, links, confidence=None, build_on_latest=True):
    """Kahn's topological sort over the links; returns ``(ordered, depth by id, ignored links)``.

    Loops are first broken at their least confident derived link. Among
    concepts ready at the same time, the one building on the step placed most
    recently goes first (keeps related material together), then the earliest
    in the topic's merged PDF order.
    """
    position = {concept.id: index for index, concept in enumerate(concepts)}
    kept, ignored = break_cycles(
        {(before, after) for before, after in links if before in position and after in position},
        confidence,
    )
    successors = {concept.id: set() for concept in concepts}
    prerequisites = {concept.id: set() for concept in concepts}
    for before, after in kept:
        successors[before].add(after)
        prerequisites[after].add(before)

    placed_at = {}
    remaining = {concept_id: len(prerequisites[concept_id]) for concept_id in position}

    def priority(concept_id):
        latest = max((placed_at[before] for before in prerequisites[concept_id]), default=-1)
        return (latest if build_on_latest else -1, -position[concept_id])

    by_id = {concept.id: concept for concept in concepts}
    ordered = []
    while len(ordered) < len(concepts):
        ready = [concept_id for concept_id, count in remaining.items() if count == 0 and concept_id not in placed_at]
        chosen = max(ready, key=priority)
        placed_at[chosen] = len(ordered)
        ordered.append(by_id[chosen])
        for following in successors[chosen]:
            remaining[following] -= 1

    depth = {concept.id: 0 for concept in ordered}
    for concept in ordered:
        for following in successors[concept.id]:
            depth[following] = max(depth[following], depth[concept.id] + 1)
    return ordered, depth, ignored


def path_link_confidence(node, concept_ids):
    """Confidence of each derived accepted link; approved links are absent, so never broken first."""
    return {
        (row.prerequisite_id, row.dependent_id): float((row.evidence or {}).get("confidence", 0.0))
        for row in ConceptPrerequisite.objects.filter(
            outline_node=node, status=ConceptPrerequisite.Status.ACCEPTED,
        )
        if row.prerequisite_id in concept_ids and row.dependent_id in concept_ids
    }
```

In `save_learning_path`, change the two lines that build the order to:

```python
    concept_ids = {concept.id for concept in concepts}
    links = path_links(node, concept_ids)
    ordered, depth, ignored = order_with_links(concepts, links, path_link_confidence(node, concept_ids))
```

Update the module docstring's third bullet to: "**Prerequisite links win over document order.** Kahn's sort respects every ``accepted`` and ``approved`` link; ties go to the concept building on the latest step, then the merged document order."

- [ ] **Step 4: Implement in `path_builder.py`** — change the import to `from .publishing import order_with_links, path_link_confidence, path_links, redundant_links`, and replace the order line with:

```python
    ordered, depth, ignored = order_with_links(concepts, links, path_link_confidence(node, concept_ids))
    redundant = redundant_links(links)
```

In the `entry` dict built for each link row add:

```python
            "redundant": (row.prerequisite_id, row.dependent_id) in redundant,
```

and in each item of `edges` add:

```python
            "redundant": (row.prerequisite_id, row.dependent_id) in redundant,
```

- [ ] **Step 5: Run the learning-path tests**

Run: `python manage.py test learning_path.test_publishing learning_path.tests learning_path.test_link_editing`
Expected: PASS. (`test_contradicting_links_are_reported_not_hidden` still sees one ignored link: with no confidence map both links count as teacher links and the loop is broken at one of them.)

- [ ] **Step 6: Commit**

```bash
git add backend/learning_path/services/publishing.py backend/learning_path/services/path_builder.py backend/learning_path/test_publishing.py
git commit -m "Break loops at the weakest link and tie-break Kahn by the latest step"
```

## Amendment 1 (2026-09-30, approved by the user)

Spec §14 replaces the learned-weight verdict with two evidence families. Implemented inside
Task 7 (commit "Replace the v4 criteria…"): `clues.heading_vote`, `clues.presented_in_parallel`,
`clues.heading_stems`; `pair_votes` votes gain `"heading"` and `"parallel"`; `fusion.CLUES =
CONTENT_CLUES + STRUCTURE_CLUES`, `fusion.verdict(votes, semantic=True)`,
`fusion.confidence(votes, direction)`, `fusion.family_direction`; `fusion.combine` removed;
`learn_weights` reports agreement only; `calibration.DEFAULTS` weights gain `"heading"`;
`criteria.decide_pairs(..., without=())` silences clues for ablations and stores `parallel` and
`disagreement` in the evidence; `reasons` explains headings, disagreement and siblings; gold
fixtures 62/79/152 have `"structural": []`.

Later tasks read with this amendment:
- **Task 9:** the calibration's `weights` are reported, not used for verdicts.
- **Task 10:** `clue_accuracy` iterates `CLUES` (the votes dict also holds the `parallel` flag);
  `--without CLUE` passes `without=(clue,)` to `decide_pairs` instead of zeroing a weight.

---

### Task 7: Rewrite the criteria as fusion; retire the v4 rules

**Files:**
- Rewrite: `backend/learning_path/services/criteria.py`
- Modify: `backend/learning_path/services/reasons.py` (fusion branch), `backend/learning_path/services/gold.py` (pass confidence), `backend/learning_path/services/text_signals.py` (keep only `strip_part_suffix`, `part_marker`)
- Rewrite: `backend/learning_path/test_criteria.py`; modify `backend/learning_path/test_reasons.py`, `backend/learning_path/test_gold_paths.py`
- Delete: `backend/learning_path/services/concepts.py`, `backend/learning_path/test_concepts.py`, `backend/learning_path/test_evidence.py`, `backend/learning_path/management/commands/evaluate_edges.py`
- Rewrite: `backend/learning_path/management/commands/evaluate_gold_paths.py` (drop the PRD grid; full version in Task 10 — here only make it import-clean)

**Interfaces:**
- Consumes: everything from Tasks 2–6.
- Produces: `criteria.decide_pairs(concepts, runtime_instance=None, calibration=None, embed=None) -> list[dict]` with keys `prerequisite`, `dependent`, `verdict`, `evidence`, `cross_section`; `criteria.ACCEPTED`, `criteria.PENDING` (re-exported from fusion); `criteria.crosses_sections(a, b)`; evidence shape exactly as spec §7 plus `"semantic": bool`.

- [ ] **Step 1: Write the failing tests** — replace `test_criteria.py` entirely with:

```python
"""v5 criteria end to end: gate, clues, fusion, verdicts (spec sections 5-7)."""

import json

from django.test import SimpleTestCase, TestCase

from lessons.models import CourseGroup, LearningMaterial, LearningObject, LearningObjectGroup, OutlineNode

from .services.concept_units import concepts_for_topic
from .services.criteria import ACCEPTED, PENDING, crosses_sections, decide_pairs
from .services.embeddings import EncoderUnavailable
from .testing import concept, member, word_vectors

CALIBRATION = {
    "weights": {"name": 1.0, "terms": 1.0, "meaning": 1.0, "order": 0.5},
    "related_cutoff": 0.1,
    "meaning_cutoff": 0.3,
    "source": "test",
}


def flower():
    return [
        concept(1, "Stamen", "The anther makes pollen grains. " * 8),
        concept(2, "Pollination", "Pollen travels from an anther to a stigma."),
        concept(3, "Pistil", "The stigma is sticky and holds the style. " * 8),
    ]


def decide(concepts, embed=word_vectors):
    return {
        (row["prerequisite"].id, row["dependent"].id): row
        for row in decide_pairs(concepts, calibration=CALIBRATION, embed=embed)
    }


def no_encoder(sentences):
    raise EncoderUnavailable("offline")


class DecisionTests(SimpleTestCase):
    def test_a_concept_using_terms_another_explains_comes_after_it(self):
        decided = decide(flower())

        self.assertIn((1, 2), decided)
        self.assertIn(decided[(1, 2)]["verdict"], (ACCEPTED, PENDING))
        self.assertEqual(decided[(1, 2)]["evidence"]["votes"]["terms"], 1)

    def test_unrelated_concepts_get_no_link(self):
        decided = decide([concept(1, "Stamen", "The anther makes pollen grains."),
                          concept(2, "Weather", "Clouds bring heavy rain showers.")])

        self.assertEqual(decided, {})

    def test_pdf_order_alone_never_makes_a_link(self):
        first = concept(1, "Heat", member("Heat changes water into steam.", material_id=10, order=0),
                        member("Heat changes water into steam.", material_id=11, order=0))
        second = concept(2, "Steam", member("Heat changes water into steam.", material_id=10, order=1),
                         member("Heat changes water into steam.", material_id=11, order=1))

        self.assertEqual(decide([first, second]), {})

    def test_without_the_encoder_links_are_only_pending(self):
        decided = decide(flower(), embed=no_encoder)

        self.assertTrue(decided)
        self.assertEqual({row["verdict"] for row in decided.values()}, {PENDING})
        self.assertFalse(decided[(1, 2)]["evidence"]["semantic"])

    def test_a_concept_with_no_full_sentence_takes_part_in_no_link(self):
        concepts = flower() + [concept(4, "Figure", "Stamen")]

        self.assertFalse(any(4 in pair for pair in decide(concepts)))

    def test_votes_are_stored_for_prerequisite_first(self):
        row = decide(flower())[(1, 2)]

        supporting = [clue for clue, vote in row["evidence"]["votes"].items() if vote == 1]
        self.assertIn("terms", supporting)
        self.assertGreater(row["evidence"]["confidence"], 0)

    def test_evidence_is_json_serialisable(self):
        for row in decide(flower()).values():
            json.dumps(row["evidence"])

    def test_too_few_concepts_decide_nothing(self):
        self.assertEqual(decide([concept(1, "Matter", "Matter has mass and takes up space.")]), {})


class SectionTests(SimpleTestCase):
    def test_different_headings_cross_sections(self):
        solid = concept(1, "Solid", member("x", section_title="Solids"))
        comparing = concept(2, "Comparing", member("x", section_title="Comparing the Three States"))

        self.assertTrue(crosses_sections(solid, comparing))

    def test_a_concept_without_a_heading_crosses_nothing(self):
        self.assertFalse(crosses_sections(concept(1, "Matter", "x"), concept(2, "Solid", member("x", section_title="Solids"))))


class MemberTextTests(TestCase):
    """Concepts built the way the topic path builds them carry every PDF's text."""

    def test_member_text_joins_every_pdf(self):
        course = CourseGroup.objects.create(title="Grade 1 Science")
        topic = OutlineNode.objects.create(course=course, title="Solid, Liquid and Gas", order=0, depth=0)
        first = LearningMaterial.objects.create(course=course, outline_node=topic, title="A", status="completed")
        second = LearningMaterial.objects.create(course=course, outline_node=topic, title="B", status="completed")
        group = LearningObjectGroup.objects.create(outline_node=topic, label="Solid")
        LearningObject.objects.create(material=first, group=group, title="Solid", content="A solid is matter that keeps its shape.", order=0)
        LearningObject.objects.create(material=second, group=group, title="Solids", content="Solid particles vibrate.", order=0)

        concept_unit = next(c for c in concepts_for_topic(topic) if c.id == group.id)

        self.assertIn("A solid is matter that keeps its shape.", concept_unit.member_text)
        self.assertIn("Solid particles vibrate.", concept_unit.member_text)
```

Append to `test_reasons.py` (inside its existing test class):

```python
    def test_a_fused_link_names_its_clues(self):
        evidence = {
            "rule": "fusion", "confidence": 0.81, "semantic": True,
            "votes": {"name": 0, "terms": 1, "meaning": 1, "order": 1},
            "records": {"terms": {"owned": ["anther", "filament"]}, "order": {"pdfs": 2, "agree": 2}},
        }

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination uses terms Stamen explains (anther, filament). "
            "Pollination's sentences refer to Stamen's ideas. "
            "2 of 2 files teach Stamen first. Confidence 0.81.",
        )

    def test_a_fused_link_says_which_clues_disagree_and_when_meaning_was_unavailable(self):
        evidence = {"rule": "fusion", "confidence": 0.3, "semantic": False,
                    "votes": {"name": 1, "terms": 0, "meaning": 0, "order": -1}, "records": {}}

        self.assertEqual(
            link_reason(evidence, "Stamen", "Pollination"),
            "Pollination names Stamen. Against it: the files' order. "
            "The meaning check was unavailable. Confidence 0.30.",
        )
```

In `test_gold_paths.py`, replace the file body so it asserts only the hard gate for now (floors return in Task 10):

```python
"""Acceptance: v5 on real lesson text, against the answer keys.

Uses the real encoder; skipped when it cannot load. The hard gate is 0 forbidden
links accepted. Reachability and Kendall's tau floors are set from measured v5
numbers (spec section 9) -- see the evaluation report.
"""

import json
import unittest

from django.test import SimpleTestCase

from .services import criteria
from .services.embeddings import EncoderUnavailable, load_encoder
from .services.gold import gold_report, load_gold


class GoldPathTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            load_encoder()
        except EncoderUnavailable as exc:
            raise unittest.SkipTest(f"encoder unavailable: {exc}")

    def _report(self, topic_id):
        data, concepts = load_gold(topic_id)
        return gold_report(data, concepts, criteria.decide_pairs(concepts))

    def _assert_gold(self, topic_id):
        report = self._report(topic_id)
        self.assertEqual(report["forbidden_accepted"], [], json.dumps(report, indent=2))

    def test_solid_liquid_and_gas(self):
        self._assert_gold(62)

    def test_reproduction_among_flowering_plants(self):
        self._assert_gold(79)

    def test_solid_liquid_and_gas_as_the_pipeline_groups_it_today(self):
        self._assert_gold(152)

    def test_topic_340_against_the_recommended_arrangement(self):
        self._assert_gold(340)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_criteria learning_path.test_reasons`
Expected: FAIL — `DecisionTests` with `TypeError: decide_pairs() got an unexpected keyword argument 'calibration'` (v4 has no such parameter), and the two new reason tests with `AssertionError` (v4 returns "Added by you." for rule `fusion`).

- [ ] **Step 3: Rewrite `services/criteria.py`**:

```python
"""Prerequisite links for the learning path (criteria v5).

Two questions for each pair of concepts. Are they related? Sentence embeddings
answer that, and the answer is symmetric. Which comes first? Four clues vote --
name use, explained terms, meaning reference, and PDF order when several PDFs
agree -- and fusion weighs them into a confidence. Nothing here writes to the
database. See docs/superpowers/specs/2026-09-30-learning-path-evidence-fusion-design.md.
"""

from . import embeddings
from .calibration import load_calibration
from .clues import clue_records, find_term_owners, pair_votes
from .concept_text import material_positions, prepare
from .fusion import ACCEPTED, PENDING, combine, verdict

__all__ = ["ACCEPTED", "PENDING", "crosses_sections", "decide_pairs"]


def section_headings(concept):
    """The lesson headings a concept sits under, across every file teaching it."""
    members = getattr(concept, "members", None) or (concept,)
    return {
        (getattr(member, "section_title", "") or "").strip().casefold()
        for member in members
        if (getattr(member, "section_title", "") or "").strip()
    }


def crosses_sections(first, second):
    """True when both concepts sit under headings and share none; shown to the teacher, never decisive."""
    left, right = section_headings(first), section_headings(second)
    return bool(left and right and not (left & right))


def decide_pairs(concepts, runtime_instance=None, calibration=None, embed=None):
    """Every pair the evidence accepts or sends to the teacher.

    ``runtime_instance`` is kept for callers and ignored: the learning path
    loads its own encoder. Without the encoder, links are derived from the
    other clues and are never more than pending.
    """
    concepts = list(concepts)
    if len(concepts) < 2:
        return []
    calibration = calibration or load_calibration()
    semantic = True
    try:
        texts = prepare(concepts, embed=embed or embeddings.embed)
    except embeddings.EncoderUnavailable:
        texts, semantic = prepare(concepts), False
    owners = find_term_owners(texts)
    positions = material_positions(concepts)
    meaning_cutoff = calibration["meaning_cutoff"]

    decisions = []
    for pair in pair_votes(texts, owners, positions, calibration["related_cutoff"], meaning_cutoff, semantic):
        if not pair["related"]:
            continue
        score, confidence = combine(pair["votes"], calibration["weights"])
        outcome, direction = verdict(pair["votes"], score, confidence, semantic)
        if outcome not in (ACCEPTED, PENDING):
            continue
        if direction > 0:
            prerequisite, dependent = pair["first"], pair["second"]
        else:
            prerequisite, dependent = pair["second"], pair["first"]
        decisions.append({
            "prerequisite": prerequisite.concept,
            "dependent": dependent.concept,
            "verdict": outcome,
            "evidence": {
                "rule": "fusion",
                "relatedness": None if pair["relatedness"] is None else round(pair["relatedness"], 3),
                "score": round(abs(score), 3),
                "confidence": round(confidence, 3),
                "votes": {clue: vote * direction for clue, vote in pair["votes"].items()},
                "records": clue_records(prerequisite, dependent, owners, positions, meaning_cutoff, semantic),
                "semantic": semantic,
            },
            "cross_section": crosses_sections(prerequisite.concept, dependent.concept),
        })
    return decisions
```

- [ ] **Step 4: Add the fused reason** — in `reasons.py`, add before `def link_reason`:

```python
_CLUE_NAMES = {"name": "the name", "terms": "the terms", "meaning": "the meaning", "order": "the files' order"}


def _fused_reason(evidence, a, b):
    votes = evidence.get("votes") or {}
    records = evidence.get("records") or {}
    parts = []
    if votes.get("terms") == 1:
        owned = (records.get("terms") or {}).get("owned") or []
        listed = f" ({', '.join(owned[:3])})" if owned else ""
        parts.append(f"{b} uses terms {a} explains{listed}.")
    if votes.get("meaning") == 1:
        parts.append(f"{b}'s sentences refer to {a}'s ideas.")
    if votes.get("name") == 1:
        parts.append(f"{b} names {a}.")
    if votes.get("order") == 1:
        order = records.get("order") or {}
        parts.append(f"{order.get('agree')} of {order.get('pdfs')} files teach {a} first.")
    against = [_CLUE_NAMES[clue] for clue in ("name", "terms", "meaning", "order") if votes.get(clue) == -1]
    if against:
        parts.append(f"Against it: {', '.join(against)}.")
    if evidence.get("semantic") is False:
        parts.append("The meaning check was unavailable.")
    if evidence.get("confidence") is not None:
        parts.append(f"Confidence {evidence['confidence']:.2f}.")
    return " ".join(parts)
```

and inside `link_reason`, before `if rule == "definition":`:

```python
    if rule == "fusion":
        return _fused_reason(evidence, a, b)
```

Update the module docstring's first line to mention v5 rows ("Built from the evidence ``criteria.decide_pairs`` stores on each derived row; v4 rows keep their older wording until re-derived.").

- [ ] **Step 5: Pass confidence in the gold report** — in `gold.py` `gold_report`, replace the `links = [...]` / `order_with_links` lines with:

```python
    accepted_rows = [row for row in decisions if row["verdict"] == criteria.ACCEPTED]
    links = [(row["prerequisite"].id, row["dependent"].id) for row in accepted_rows]
    confidence = {
        (row["prerequisite"].id, row["dependent"].id): (row.get("evidence") or {}).get("confidence", 0.0)
        for row in accepted_rows
    }
    ordered, _, ignored = order_with_links(concepts, links, confidence, build_on_latest=build_on_latest)
```

and change the signature to `def gold_report(data, concepts, decisions, build_on_latest=True):`.

- [ ] **Step 6: Retire the v4 code**

```bash
git rm backend/learning_path/services/concepts.py backend/learning_path/test_concepts.py backend/learning_path/test_evidence.py backend/learning_path/management/commands/evaluate_edges.py
```

Replace `services/text_signals.py` with only what `concept_units`, `published` and `concept_text` still import:

```python
"""Recognising the chunker's "(Part 1 of 3)" pieces, so split passages join up again."""

import re

_PART_SUFFIX = re.compile(r"\s*\(\s*part\s+\d+\s+of\s+\d+\s*\)\s*$", re.IGNORECASE)


def strip_part_suffix(title):
    """Drop the chunker's "(Part 1 of 3)" marker so split pieces share a name."""
    return _PART_SUFFIX.sub("", title or "").strip()


def part_marker(title):
    """Return ``(base_title, part_number, part_total)`` for a split chunk, else ``None``."""
    match = _PART_SUFFIX.search(title or "")
    if not match:
        return None
    numbers = re.findall(r"\d+", match.group(0))
    if len(numbers) != 2:
        return None
    return strip_part_suffix(title), int(numbers[0]), int(numbers[1])
```

Replace `management/commands/evaluate_gold_paths.py` with the minimal import-clean version (Task 10 extends it):

```python
"""Print the gold report for frozen topics."""

import json

from django.core.management.base import BaseCommand

from learning_path.services import criteria
from learning_path.services.gold import gold_report, load_gold


class Command(BaseCommand):
    help = "Report derived learning paths against the gold standard."

    def add_arguments(self, parser):
        parser.add_argument("--topics", nargs="*", type=int, default=[62, 79, 152])

    def handle(self, *args, topics, **options):
        reports = []
        for topic_id in topics:
            data, concepts = load_gold(topic_id)
            reports.append(gold_report(data, concepts, criteria.decide_pairs(concepts)))
        self.stdout.write(json.dumps(reports, indent=2))
```

Then search for leftovers:

Run: `grep -rn "text_signals import\|services.concepts\|structural_role\|definition_subject\|PRD_THRESHOLD" learning_path --include=*.py`
Expected: only `concept_units.py`, `published.py` and `concept_text.py` importing `part_marker`/`strip_part_suffix`. Fix anything else before continuing.

- [ ] **Step 7: Run the whole learning-path suite**

Run: `python manage.py test learning_path`
Expected: PASS. If `GoldPathTests` fails on `forbidden_accepted`, **stop**: record the forbidden links and their evidence, and report them to the user. Do not change constants or clues to make it pass (Global Constraints).

- [ ] **Step 8: Commit**

```bash
git add -A backend/learning_path
git commit -m "Replace the v4 criteria with relatedness and fused direction clues"
```

---

### Task 8: Graph screen hides redundant links

**Files:**
- Modify: `web-app/src/learning-path/graphModel.js` (`pathEdges`)
- Test: `web-app/src/learning-path/graphModel.test.js`

**Interfaces:**
- Consumes: `redundant` on each step prerequisite entry (Task 6).
- Produces: `pathEdges(steps)` skips entries with `redundant: true`.

- [ ] **Step 1: Write the failing test** — add `pathEdges` to the import from `./graphModel` and append:

```javascript
describe("pathEdges", () => {
  it("leaves out links a longer chain already implies", () => {
    const steps = [
      step(1, 1, "Matter"),
      step(2, 2, "Solid", [link(10, 1, "Matter")]),
      step(3, 3, "Liquid", [link(11, 2, "Solid"), link(12, 1, "Matter", { redundant: true })]),
    ];

    expect(pathEdges(steps).map((edge) => edge.linkId)).toEqual([10, 11]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd web-app && npx vitest run src/learning-path/graphModel.test.js`
Expected: FAIL — received `[10, 11, 12]`.

- [ ] **Step 3: Implement** — replace `pathEdges` in `graphModel.js`:

```javascript
// Links that shape the path, one per "learn first" entry on a step. A link a
// longer chain already implies (Matter -> Liquid beside Matter -> Solid -> Liquid)
// stays stored but is not drawn.
export function pathEdges(steps) {
  return steps.flatMap((step) =>
    (step.prerequisites || [])
      .filter((link) => !link.redundant)
      .map((link) => ({ linkId: link.link_id, from: link.concept_id, to: step.concept_id })),
  );
}
```

- [ ] **Step 4: Run the frontend suite and build**

Run: `cd web-app && npm test && npm run build`
Expected: all tests PASS, build succeeds.

- [ ] **Step 5: Commit**

```bash
git add web-app/src/learning-path/graphModel.js web-app/src/learning-path/graphModel.test.js
git commit -m "Hide redundant prerequisite links on the learning path graph"
```

---

### Task 9: Calibrate on the frozen topics and commit the weights

**Files:**
- Create: `backend/learning_path/calibration/weights.json` (written by the command)

**Interfaces:**
- Consumes: Task 5's command. Unrelated pairs must be different subjects: 62, 152, 340 are *Solid, Liquid and Gas*; 79 is *Reproduction among flowering plants*. Never pair 62/152/340 with each other.

- [ ] **Step 1: Run the calibration**

Run: `python manage.py calibrate_learning_path --topics 62 79 152 340 --unrelated 62:79 152:79 340:79`
Expected: `Wrote ...weights.json: {...}` with four weights; `order` ≤ half the smallest positive content weight.

- [ ] **Step 2: Read the result before committing**

Run: `python -c "import json; d=json.load(open('learning_path/calibration/weights.json')); print(d['related_cutoff'], d['meaning_cutoff'], d['weights'], d['agreement'], d['pairs'])"`
Expected: cutoffs near the measured 0.25 / 0.30. If a content clue's weight is 0 (agreement ≤ 0.5), note it for the evaluation report — do not change anything.

- [ ] **Step 3: Run the suite with the stored calibration**

Run: `python manage.py test learning_path`
Expected: PASS (same stop rule as Task 7 Step 7 for forbidden links).

- [ ] **Step 4: Commit**

```bash
git add backend/learning_path/calibration/weights.json
git commit -m "Store the learning-path calibration from topics 62, 79, 152 and 340"
```

---

### Task 10: Evaluation command, development-set checks, report and floors

**Files:**
- Modify: `backend/learning_path/services/gold.py` (add `gate_loss`, `clue_accuracy`)
- Rewrite: `backend/learning_path/management/commands/evaluate_gold_paths.py`
- Modify: `backend/learning_path/test_gold_report.py`, `backend/learning_path/test_gold_paths.py`
- Create: `docs/learning-path-v5-evaluation-2026-09-30.md`

**Interfaces:**
- Consumes: `gold_report(..., build_on_latest)`, `load_calibration`, `clues.MEANING_MATCHES`, `pair_votes`, `relatedness`, `prepare`, `material_positions`, `find_term_owners`, `embeddings.embed`.
- Produces: `gold.gate_loss(data, concepts, calibration) -> list[[before, after]]`; `gold.clue_accuracy(data, concepts, calibration) -> {clue: {"right": int, "wrong": int}}`; command flags `--topics`, `--without CLUE`, `--pdf-tiebreak`, `--meaning-matches N`, `--by-clue`.

- [ ] **Step 1: Write the failing tests** — append to `test_gold_report.py`:

```python
class ClueMeasureTests(SimpleTestCase):
    def setUp(self):
        from .testing import concept as make_concept

        self.concepts = [
            make_concept(1, "Stamen", "The anther makes pollen grains. " * 8, key="stamen"),
            make_concept(2, "Pollination", "Pollen travels from an anther to a stigma.", key="pollination"),
            make_concept(3, "Weather", "Clouds bring heavy rain showers today.", key="weather"),
        ]
        self.data = {"required": [["stamen", "pollination"], ["stamen", "weather"]]}
        self.calibration = {"related_cutoff": 0.1, "meaning_cutoff": 0.3}

    def test_clue_accuracy_counts_votes_on_the_keys_links(self):
        from unittest.mock import patch

        from .services.gold import clue_accuracy
        from .testing import word_vectors

        with patch("learning_path.services.embeddings.embed", word_vectors):
            counts = clue_accuracy(self.data, self.concepts, self.calibration)

        self.assertEqual(counts["terms"]["right"], 1)
        self.assertEqual(counts["terms"]["wrong"], 0)

    def test_gate_loss_lists_key_links_the_gate_blocks(self):
        from unittest.mock import patch

        from .services.gold import gate_loss
        from .testing import word_vectors

        with patch("learning_path.services.embeddings.embed", word_vectors):
            lost = gate_loss(self.data, self.concepts, self.calibration)

        self.assertEqual(lost, [["stamen", "weather"]])
```

- [ ] **Step 2: Run to verify they fail**

Run: `python manage.py test learning_path.test_gold_report`
Expected: FAIL — `ImportError: cannot import name 'clue_accuracy'`.

- [ ] **Step 3: Implement in `gold.py`** — add imports `from collections import defaultdict`, `from . import embeddings`, `from .clues import find_term_owners, pair_votes`, `from .concept_text import material_positions, prepare`, `from .fusion import CLUES`, `from .relatedness import relatedness`, then:

```python
def _keyed_texts(concepts):
    texts = prepare(concepts, embed=embeddings.embed)
    by_key = defaultdict(list)
    for text in texts:
        if getattr(text.concept, "key", None):
            by_key[text.concept.key].append(text)
    return texts, by_key


def gate_loss(data, concepts, calibration):
    """The key's links whose two concepts the relatedness gate keeps apart."""
    _, by_key = _keyed_texts(concepts)
    lost = []
    for before, after in data["required"]:
        closest = max(
            (relatedness(first, second) for first in by_key[before] for second in by_key[after]),
            default=0.0,
        )
        if closest < calibration["related_cutoff"]:
            lost.append([before, after])
    return lost


def clue_accuracy(data, concepts, calibration):
    """For each clue, how many of the key's links it points the right and the wrong way."""
    texts, _ = _keyed_texts(concepts)
    owners = find_term_owners(texts)
    positions = material_positions(concepts)
    required = {tuple(edge) for edge in data["required"]}
    counts = {clue: {"right": 0, "wrong": 0} for clue in CLUES}
    for pair in pair_votes(texts, owners, positions, calibration["related_cutoff"], calibration["meaning_cutoff"]):
        first, second = getattr(pair["first"].concept, "key", None), getattr(pair["second"].concept, "key", None)
        if (first, second) in required:
            truth = 1
        elif (second, first) in required:
            truth = -1
        else:
            continue
        for clue, vote in pair["votes"].items():
            if vote:
                counts[clue]["right" if vote == truth else "wrong"] += 1
    return counts
```

- [ ] **Step 4: Rewrite the command** — `evaluate_gold_paths.py`:

```python
"""Print the gold report for frozen topics, with the switches the evaluation needs.

--without CLUE       weigh one clue at zero (ablation)
--pdf-tiebreak       Kahn ties by PDF order only (tie-break rule 1 off)
--meaning-matches N  average the N best matches in the meaning clue (size check)
--by-clue            add each clue's right/wrong count on the key's links
"""

import json

from django.core.management.base import BaseCommand

from learning_path.services import clues, criteria
from learning_path.services.calibration import load_calibration
from learning_path.services.fusion import CLUES
from learning_path.services.gold import clue_accuracy, gate_loss, gold_report, load_gold


class Command(BaseCommand):
    help = "Report derived learning paths against the gold standard."

    def add_arguments(self, parser):
        parser.add_argument("--topics", nargs="*", type=int, default=[62, 79, 152])
        parser.add_argument("--without", choices=CLUES)
        parser.add_argument("--pdf-tiebreak", action="store_true")
        parser.add_argument("--meaning-matches", type=int, default=1)
        parser.add_argument("--by-clue", action="store_true")

    def handle(self, *args, topics, without, pdf_tiebreak, meaning_matches, by_clue, **options):
        calibration = load_calibration()
        if without:
            calibration["weights"][without] = 0.0
        previous_matches = clues.MEANING_MATCHES
        clues.MEANING_MATCHES = meaning_matches
        try:
            reports = []
            for topic_id in topics:
                data, concepts = load_gold(topic_id)
                decisions = criteria.decide_pairs(concepts, calibration=calibration)
                report = gold_report(data, concepts, decisions, build_on_latest=not pdf_tiebreak)
                report["gate_loss"] = gate_loss(data, concepts, calibration)
                if by_clue:
                    report["clue_accuracy"] = clue_accuracy(data, concepts, calibration)
                reports.append(report)
        finally:
            clues.MEANING_MATCHES = previous_matches
        self.stdout.write(json.dumps({
            "calibration": calibration["source"],
            "without": without,
            "pdf_tiebreak": pdf_tiebreak,
            "meaning_matches": meaning_matches,
            "reports": reports,
        }, indent=2))
```

- [ ] **Step 5: Run to verify the tests pass**

Run: `python manage.py test learning_path.test_gold_report`
Expected: PASS.

- [ ] **Step 6: Development-set checks (62, 79, 152 only)** — run and keep each output:

```bash
python manage.py evaluate_gold_paths --topics 62 79 152 --by-clue > ../docs/eval-dev-default.json
python manage.py evaluate_gold_paths --topics 62 79 152 --meaning-matches 2 --by-clue > ../docs/eval-dev-meaning2.json
python manage.py evaluate_gold_paths --topics 62 79 152 --pdf-tiebreak > ../docs/eval-dev-pdf-tiebreak.json
```

Decide, by these numbers only:
- **C3 size fallback:** if `meaning` has more `wrong` than `right` with 1 match and fewer with 2, set `MEANING_MATCHES = 2` in `clues.py` (update its comment with the measured counts); otherwise leave 1.
- **Tie-break rule 1:** keep `build_on_latest=True` only if mean Kendall's τ over 62/79/152 is not lower than with `--pdf-tiebreak`; otherwise change the default of `order_with_links(..., build_on_latest=...)` and `gold_report(..., build_on_latest=...)` to `False`, and record why.

- [ ] **Step 7: Test-set and comparison runs** (after Step 6 decisions; nothing below changes code):

```bash
python manage.py evaluate_gold_paths --topics 62 79 152 340 --by-clue > ../docs/eval-v5.json
python manage.py evaluate_gold_paths --topics 62 79 152 340 --without name > ../docs/eval-v5-without-name.json
python manage.py evaluate_gold_paths --topics 62 79 152 340 --without terms > ../docs/eval-v5-without-terms.json
python manage.py evaluate_gold_paths --topics 62 79 152 340 --without meaning > ../docs/eval-v5-without-meaning.json
python manage.py evaluate_gold_paths --topics 62 79 152 340 --without order > ../docs/eval-v5-without-order.json
```

- [ ] **Step 8: Write `docs/learning-path-v5-evaluation-2026-09-30.md`** with, from the JSON files (v4 numbers from `docs/learning-path-v4-baseline-2026-09-30.json`):
  - a table per topic: v4 vs v5 — forbidden accepted, accepted precision, reachable recall (`reachable_count` / required), Kendall's τ, gate loss;
  - clue-by-clue right/wrong counts;
  - the ablation table (v5 without each clue: reachable, τ, forbidden);
  - the two development-set decisions of Step 6 with their numbers;
  - the calibration used (`weights.json` values);
  - the limitation paragraph from spec §9 (AI-drafted keys; gold 62/79/152 partly built around v4's heading rules);
  - where v5 loses to v4, the concrete pairs and why.
  Then move the `eval-*.json` files into `docs/learning-path-v5-evaluation/` and link them from the report.

- [ ] **Step 9: Set the measured floors** — in `test_gold_paths.py`, add after the imports:

```python
# Measured v5 values from docs/learning-path-v5-evaluation-2026-09-30.md.
REACHABLE_FLOOR = {62: R62, 79: R79, 152: R152, 340: R340}
TAU_FLOOR = {62: T62, 79: T79, 152: T152, 340: T340}
```

replacing each `R…` with that topic's measured `reachable_count` and each `T…` with its measured `kendall_tau` rounded **down** to 2 decimals, and extend `_assert_gold`:

```python
        self.assertGreaterEqual(report["reachable_count"], REACHABLE_FLOOR[topic_id], json.dumps(report, indent=2))
        self.assertGreaterEqual(report["kendall_tau"], TAU_FLOOR[topic_id], json.dumps(report, indent=2))
```

- [ ] **Step 10: Run everything**

Run: `python manage.py test learning_path && python manage.py test`
Expected: PASS for both (full backend ~1200 tests). Report any unrelated failure by name.

- [ ] **Step 11: Commit**

```bash
git add backend/learning_path docs/learning-path-v5-evaluation-2026-09-30.md docs/learning-path-v5-evaluation
git commit -m "Measure v5 against v4 and set the measured gold floors"
```

---

### Task 11: Topic 357 answer key (blocked until the user pastes the AI tool's answer)

**Files:**
- Create: `backend/learning_path/fixtures/gold_map_357.json`, `backend/learning_path/fixtures/gold_topic_357.json`
- Modify: `backend/learning_path/test_gold_paths.py`, `backend/learning_path/calibration/weights.json`, `docs/learning-path-v5-evaluation-2026-09-30.md`

**Interfaces:**
- Consumes: the user's AI answer for `docs/learning-path-357-snapshot-2026-09-30.md`; live topic 357 concept ids (873 main parts, 874 reproduction overview, 894 stamen, 895 pistil, 896 petals and sepals, 878 pollination, 897 fertilization, 898 seed formation, 899 fruit formation, 882 everyday examples — re-check with the command in Step 1).

- [ ] **Step 1: Confirm the live concept ids**

Run: `python manage.py shell -c "from lessons.models import OutlineNode; from learning_path.services.concept_units import concepts_for_topic; [print(c.id, c.title) for c in concepts_for_topic(OutlineNode.objects.get(id=357))]"`
Expected: the ten concepts above (ids may differ if the teacher regrouped; use what is printed).

- [ ] **Step 2: Write `gold_map_357.json`** in the same shape as `gold_map_340.json`: `topic_id` 357; `_note` stating "AI-drafted recommendation from the same tool and prompt as topic 340, not teacher-verified, received <date>"; `concept_keys` mapping each printed id to a short key; `required` = every "Recommended prerequisite" in the answer; `expected_order` = the answer's final arrangement; `parallel` = sibling sets the answer leaves unordered; `structural: []`; `forbidden` = the reverse of each parent → child link the answer states; `known_missing: []`. Only what the answer says — add nothing from the algorithm's output.

- [ ] **Step 3: Freeze the fixture**

Run: `python manage.py export_live_concepts 357 learning_path/fixtures/gold_map_357.json learning_path/fixtures/gold_topic_357.json`
Expected: `Wrote 10 concepts (10 labelled) ...`

- [ ] **Step 4: Recalibrate including 357** (357 is a different subject from 340)

Run: `python manage.py calibrate_learning_path --topics 62 79 152 340 357 --unrelated 62:79 152:79 340:79 340:357`

- [ ] **Step 5: Measure 357 and update the report** — rerun Task 10 Step 7 with `--topics 62 79 152 340 357`, add 357's rows to every table in the evaluation report, and add `357` to `REACHABLE_FLOOR`/`TAU_FLOOR` (measured, rounded down) and a `test_topic_357_against_the_recommended_arrangement` test calling `self._assert_gold(357)`. Existing floors for other topics are re-measured with the new calibration and updated the same way if they move; the report says so.

- [ ] **Step 6: Run and commit**

Run: `python manage.py test learning_path`
Expected: PASS.

```bash
git add backend/learning_path docs/learning-path-v5-evaluation-2026-09-30.md docs/learning-path-v5-evaluation
git commit -m "Add topic 357's AI-drafted key and recalibrate with it"
```

---

### Task 12: Documentation

**Files:**
- Rewrite: `backend/learning_path/CRITERIA.md`
- Modify: `backend/learning_path/fixtures/gold_map_340.json` (`_note` only)
- Modify: `docs/open-issues-2026-09-30.md`, `docs/AGENT_LOG.md`

- [ ] **Step 1: Mark the 340 key's source** — in `gold_map_340.json`, set `_note` to begin: "AI-drafted recommendation (not teacher-verified), 2026-09-30, from docs/learning-path-340-snapshot-2026-09-30.md." Keep the rest of the note.

- [ ] **Step 2: Rewrite `CRITERIA.md`** — replace the v3/v4 text with a v5 description: the six steps (spec §3), each clue with its failure mode, the verdict table, the calibration command and file, the Kahn tie-break and cycle rule, and a "History" section linking the v3 spec, the v4 spec and `docs/learning_path_revision_2026-09-17.md`. Point to the v5 spec and the evaluation report for numbers; do not repeat numbers.

- [ ] **Step 3: Update the handover** — in `docs/open-issues-2026-09-30.md`: mark 1.1 (R1 blind), 1.2 (structural list), 1.3 (backwards recommendation) and 1.4 (figure rule) as addressed by v5 with a link to the evaluation report, stating which ones the numbers show fixed and which remain; update the "Where things stand" table for this branch. Add an `AGENT_LOG.md` entry for 2026-09-30 summarising v5 in five lines.

- [ ] **Step 4: Commit**

```bash
git add backend/learning_path/CRITERIA.md backend/learning_path/fixtures/gold_map_340.json docs/open-issues-2026-09-30.md docs/AGENT_LOG.md
git commit -m "Document the v5 learning-path criteria"
```
