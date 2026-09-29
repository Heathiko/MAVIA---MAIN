# MAVIA Bugs

Bugs found during pipeline run-throughs. Add new ones at the bottom with the
next number. Each entry says what is wrong, where it shows up, why it happens
(if known), and where to look in the code. Tick a fix item and set the status
when it is done.

**Status values:** Open · In progress · Fixed · Won't fix

**Describe bugs by content, not database IDs.** Everyone runs their own local
database, so a group or learning-object ID from one machine means nothing on
another. Name the PDF file, the section heading, and quote the text involved.
If you want your local IDs for yourself, put them in a *Local IDs* line at the
end of the entry.

## Status overview (updated 2026-09-29)

The 2026-09-29 round covered the first three pipeline stages only:
**extraction, grouping and content versions.** Question generation (BUG-005 to
BUG-008, BUG-011), the learning path (BUG-009) and publishing (BUG-010,
BUG-012) were not changed. See *Notes for the whole team* at the end for the
decisions, known limits and what is still untested. None of this is committed
yet; it is on the `fixExtractionPipeline` branch working tree.

| Bug | Stage | Status |
|---|---|---|
| BUG-001 | Content versions | Fixed (A, B, C, D). E is not a bug (Extra is reserved) |
| BUG-002 | Content versions (generated) | Fixed, with known limits |
| BUG-003 | Extraction | Fixed |
| BUG-004 | Extraction / grouping | Fixed (question part out of scope) |
| BUG-005 – BUG-008 | Question generation | Open (not in this round) |
| BUG-009 | Learning path | Open (not in this round) |
| BUG-010 | Publishing | Open; its *Gases* cause is gone (see entry) |
| BUG-011, BUG-012 | Questions / publishing | Open (not in this round) |
| BUG-013 – BUG-025 | Extraction / grouping / figures | Found and fixed in this round |

---

## BUG-001 — Classification step saves wrong Normal/Simplified/Elaborated/Extra roles

**Status:** Fixed (causes A, B, C, D) · E is not a bug — see *Resolution* below
**Stage:** Content-version classification (`backend/course/version_assignment.py`, `version_classifier.py`, `readability.py`)
**Found:** 2026-09-27, run-through of the *Solid, Liquid and Gas* topic, with three PDFs uploaded in this order:

- **PDF 1:** `Lesson-1_Solid-Liquid-and-Gas-1`
- **PDF 2:** `Solid-Liquid-Gas-2`
- **PDF 3:** `Solid_Liquid_and_Gas`

### What is wrong

For each concept, one PDF's text (its *bundle*) is Normal, and every other
PDF's bundle is classified as Simplified, Elaborated or Extra. In this topic, 7
concepts had text from more than one PDF, so 9 bundles were classified. Gemma
decided all 9, all 9 were saved automatically, and **none went to the teacher
for review. 4 of the 9 are wrong.**

Effect on learners: a student assigned Simplified or Elaborated gets text at the
wrong level, or text about a different concept. PDF 3's core *Solids*,
*Liquids* and *Gases* explanations are no longer their own teaching steps. They
only appear as alternate versions of other concepts, so a student on the Normal
path never sees them.

#### Wrong 1 — Concept "Matter": PDF 2 saved as SIMPLIFIED, should be ELABORATED

Normal (PDF 1, 147 words) covers matter, then one paragraph each on solid,
liquid and gas:

> Matter is anything that has mass and occupies space. A book, water, air, a
> spoon, and a balloon all contain matter. … A solid has a definite shape and a
> definite volume. Its particles are packed closely together and mainly vibrate
> in fixed positions. …

PDF 2's bundle (12 sections, 340 words: *Solids*, *Key properties of solids*,
*Everyday examples*, diagram descriptions, then the same for liquids and gases)
is longer and more detailed:

> In a solid, particles are packed tightly together in a fixed, orderly pattern.
> They vibrate in place but do not move past one another.
> Has a fixed shape -- it does not change shape unless a force is applied.
> Has a fixed volume -- it takes up the same amount of space no matter what
> container it is in. … Generally difficult to compress (squeeze into a smaller
> space). …

Gemma's reason: *"This version simplifies the explanations of solids, liquids,
and gases, using clearer language and focusing on the core concepts."*

#### Wrong 2 — Concept "Matter": PDF 3 saved as ELABORATED, but it only covers liquids

PDF 3's whole bundle for "Matter" is its *Liquids* section (46 words):

> In a liquid, particles are still close together, but they are free to slide
> past one another. This gives a liquid a definite volume but no fixed shape —
> it takes the shape of whatever container holds it, while the amount of liquid
> stays the same.

It covers one of the four parts of the concept, so it cannot be a fuller version.
It was saved at LLM confidence 0.75 (see cause B). PDF 3's *Solids* and *Gases*
sections ended up in other concepts (see Wrong 3).

#### Wrong 3 — PDF 3's *Solids* and *Gases* paired with PDF 2's *Summary* section

Two concepts, both named **"Summary: what to remember"**, each pair a paragraph
of PDF 2's summary with a section from PDF 3 that is about something else:

| Normal (PDF 2, *Summary: what to remember* Part 1 / Part 2) | Paired with (PDF 3) | Saved as |
|---|---|---|
| "Matter is made of particles and commonly exists as a solid, liquid, or gas. Solids hold a fixed shape and volume because their particles are tightly packed. Liquids keep a fixed volume but flow to fit their container because their particles can slide past each other." | *Solids*: "In a solid, particles are packed tightly together in a fixed pattern. They vibrate in place but do not move past one another. Because of this, a solid keeps a definite shape and a definite volume — it does not change shape to fit a container." | SIMPLIFIED |
| "Gases have no fixed shape or volume because their particles move quickly and spread far apart. Adding or removing heat energy can change matter from one state to another through melting, freezing, evaporating, and condensing." | *Gases*: "In a gas, particles are spread far apart and move quickly in every direction. A gas has no definite shape and no definite volume — it expands to completely fill whatever container it is in." | SIMPLIFIED |

A summary and a section explanation are not two versions of one concept, so no
role is correct here. This comes from grouping (cause A).

#### Wrong 4 — Concept "Matter usually exists in one of three everyday states": PDF 3 saved as SIMPLIFIED, should be ELABORATED

Normal (PDF 2, 27 words, grade level 8.0):

> solid, liquid, and gas. What state matter is in depends on two things: how
> closely packed its particles are, and how much energy (movement) those
> particles have.

PDF 3, *States of Matter (Part 2 of 2)* (41 words, grade level 17.1):

> Each state has its own shape, volume, and particle behavior, but all matter is
> made of the same kinds of tiny particles — what changes between the states is
> how closely packed those particles are and how much energy they have.

Gemma's reason: *"This object is a slightly more concise version of the same
core information"*. That is false: PDF 3's text is the longer and harder one.
The readability check said Elaborated with full confidence and was overruled
(cause C). The Normal text also starts mid-sentence (cause D).

#### Correct, for reference

- "Comparing the Three States": PDF 2's table description → Elaborated ✓
- "Changing From One State to Another": PDF 3 → Elaborated ✓
- "Comparing the Three States": PDF 3's table description (same table plus
  examples) → Extra, and "Everyday Examples": PDF 2's list → Extra. Both are
  reasonable roles, but see cause E.

### Causes (each can be fixed separately)

- [x] **A. Grouping sends mismatched text into classification.** This is the
  largest cause and the one classification cannot fix. *Fixed — see
  Resolution A.*
  - PDF 3's three sibling sections (*Solids*, *Liquids*, *Gases*) were split
    across three concepts: *Liquids* went into "Matter", while *Solids* and
    *Gases* were each paired with a paragraph from PDF 2's *Summary* section.
  - Side effect: two different concepts are both named "Summary: what to
    remember". The concept name comes from the Normal bundle's heading, and
    `clean_group_label` removes "(Part 1 of 2)" / "(Part 2 of 2)", so both end
    up with the same name.
  - Where: semantic grouping and concept bundles
    (`lessons/services/semantic_grouping.py`,
    `lessons/services/concept_bundles.py`).

- [x] **B. The LLM confidence threshold is never used.** *Fixed differently —
  see Resolution B/C: confidence is recorded, but no longer trusted as a
  probability.*
  `CONTENT_VERSION_LLM_AUTO_THRESHOLD = 0.80` is defined in
  `config/settings.py:298`, but nothing reads it. In
  `course/version_assignment.py:459`, `"confident": bool(llm_slot) or ...` treats
  any slot Gemma returns as confident. Result: Wrong 2 was saved automatically
  at 0.75, and while the LLM is on, the teacher review list
  (`needs_confirmation`) is always empty.
  - Fix: treat an LLM verdict as confident only when its confidence is at least
    the threshold. Send anything below it to the teacher.

- [x] **C. A confident readability result cannot stop the LLM.** *Fixed
  differently — see Resolution B/C: measurements now check every label.* In Wrong 4, all
  four readability checks passed and pointed to Elaborated (grade-level
  difference, word ratio, word difference, both signals agreeing). Gemma's
  opposite answer still won. `readability.py` itself says a disagreement is
  exactly the case where a guess is least safe.
  - Fix: when readability is confident and the LLM picks the opposite primary
    role (Simplified vs Elaborated), send the bundle to the teacher instead of
    saving it.
  - Where: the proposal loop in `assign_group_versions`
    (`course/version_assignment.py:444-472`).

- [x] **D. Extraction splits a sentence into a heading and its body.** *Fixed
  with BUG-003.* In Wrong
  4, the Normal text starts with "solid, liquid, and gas. …", so classification
  compared an incomplete sentence. Tracked separately as **BUG-003**, because
  it affects more than classification.

- [x] **E. Extra is a dead end.** Text saved as Extra is never shown to any
  learner: `_versions` skips `EXTRA`, and `represented_by` removes those
  objects from the path. A teacher-written passage classified as Extra is
  effectively deleted. We need to decide what Extra is for, or stop producing
  it. (Also in `docs/AGENT_LOG.md`.) *Not a bug: Extra is deliberately held
  back and reserved for a teammate's feature. Its behaviour was left exactly
  as it was in this round (it is not checked either — see Notes).*

### How to reproduce

Upload the three PDFs above into one topic, in the order listed, and run
grouping, then classification (the Content versions step). Then check the
Content versions screen for the concepts named above. Gemma is not fully
deterministic across machines and model versions, so the exact roles may
differ. Causes B and C are visible in the code regardless.

### Note for whoever fixes this

A saved role will not change on its own. Once a concept's text is unchanged,
`assign_group_versions` reuses the stored `classification_assignments` and never
calls Gemma again. After fixing B or C, remove `roles_signature` from
`version_selection` on the affected concepts, then run the classification
again. After fixing A, the concepts change anyway.

`course.test_version_assignment`, `course.test_version_classifier` and
`course.test_readability` all pass (52 tests), so none of these cases are
covered by tests. Add a test for B and C when fixing them.

*Local IDs (Jure's DB, 2026-09-27):* groups 615 "Matter", 625, 647, 648, 619,
623, 641; materials 50/52/53 = PDF 1/2/3; objects 649 (PDF 3 *Liquids*), 646
(*Solids*), 652 (*Gases*), 620 (split sentence).

### Resolution (2026-09-29)

**A. Grouping.** Three separate causes, all fixed:

1. **Upload order decided the concepts.** Section joining ran per PDF at
   upload. PDF 1, uploaded alone, folded its "Solid", "Liquid" and "Gas"
   paragraphs into "Matter" (nothing else taught them *yet*); PDF 2's and
   PDF 3's sections on each state then matched that swollen concept. In a
   throwaway run, "Matter" held 20 objects and the topic had no Solid, Liquid
   or Gas concept at all. Joins are now recorded, released before a new PDF is
   matched, and redone across every PDF of the topic (`release_section_joins`,
   `join_sections_across_topic` in `lessons/services/learning_resource_linker.py`).
   Measured: upload orders 1-2-3, 3-2-1 and 2-3-1 give the same 9 concepts.
2. **A summary was paired as a version of one concept.** A summary restates
   several concepts, so it scores close to each of them. Summary / recap
   sections ("Summary", "Recap", "Key takeaways", "What I have learned",
   "Conclusion"…) are never paired with another PDF's object, and nothing is
   paired into them (`is_recap_section` in `lessons/services/content_generator.py`,
   guarded in `semantic_grouping.semantic_decision` and the legacy matcher).
   Their parts stay together as one step, which also removes the two concepts
   both called "Summary: what to remember".
3. **Split passages were separated.** A later piece ("What Is Matter? (Part 2
   of 2)", "SOLID (Part 3 of 3)") now follows its own Part 1 into whatever
   concept Part 1 joined. Pieces of different passages that share a title
   ("Diagram description" under each state) are never fused.

**B/C. Classification.** Readability can no longer decide the label on its
own, and Gemma's label is no longer trusted blindly:

- Gemma still makes **one** classification call per concept. The prompt now
  has the criteria and the overlap rule (simplifies *and* adds explanation =
  Elaborated), and Gemma writes short evidence (what got easier / what was
  added / what is wrong) **before** the label. Asked for the label first,
  gemma3:4b committed to "Simplified" and then wrote evidence contradicting it.
- The label is then checked by **measurements of the two texts**, not by
  Gemma (`backend/course/content_measures.py`, `review_gemma_role` in
  `version_assignment.py`):
  - facts kept — every Normal sentence still matched (MiniLM mean coverage ≥ 0.55,
    the encoder grouping already uses);
  - something added — a candidate sentence matching nothing in Normal
    (similarity < 0.6);
  - easier — Dale-Chall (familiar-word list; plurals and endings matched).
  Simplified = facts kept + nothing added + easier. Elaborated = facts kept +
  something added.
- **Overlap-rule correction:** Gemma says Simplified, but the text keeps the
  facts and adds content → stored as **Elaborated**. The only relabel; nothing
  is ever relabelled to Simplified.
- A label that fails, or where Gemma reports a problem, is **not stored**.
  The text is not lost: it stays available as another explanation (alternate)
  of the concept, the missing version is generated, and the teacher gets no
  task for it (`kept_as_own_step`, not `needs_confirmation`).
- **FKGL and Gemma's confidence are recorded as concerns only.** Measured:
  FKGL called both valid simplifications *harder* (explaining a term makes a
  sentence longer) while Dale-Chall called them easier; combining FKGL with
  Dale-Chall scored worse than Dale-Chall alone.
- Extra is left exactly as before.
- Stored results from before are classified once more (`CLASSIFICATION_VERSION = 3`).

**Measured result** (gemma3:4b, 21 labelled pairs, real texts, batched as MAVIA
calls it):

| | Correct | Wrong label stored | Correct label withheld |
|---|---|---|---|
| Before (committed code) | 3 / 21 | 18 | 0 |
| After | 17 / 21 | 3 | 1 |

The 21 pairs: the 8 real grouped pairs from the three PDFs, the observed
failures above, and written cases (valid simplification, paraphrase,
contradiction, unrelated text, missing fact, jargon…). 16 of them were labelled
by the developer, not a teacher, and Gemma is not fully repeatable between runs,
so treat the numbers as "clearly better on these cases", not as accuracy.

**Still wrong in that run (known limits, see Notes):** a contradiction
("Solids change their shape to fit their container") stored as Simplified;
an unrelated text stored as Extra (Extra is not checked); jargon
("intermolecular forces lock particles into a lattice") stored as Elaborated.

**Tests:** `course/test_version_assignment.py`, `course/test_version_classifier.py`.

---

## BUG-002 — Generated versions are not checked against their role or their source

**Status:** Fixed, with known limits — see *Resolution* below
**Stage:** Generating missing versions (`backend/course/variant_generator.py`)
**Found:** 2026-09-27, same *Solid, Liquid and Gas* topic and PDFs as BUG-001

### What is wrong

Every concept got the versions it was missing: 17 Simplified and 15 Elaborated
were generated, none are missing, and no generation errors occurred. But
nothing checks that a Simplified version is simpler, that an Elaborated version
elaborates, or that either one sticks to the source. The prompt asks for all
three, and the model often does not follow it.

#### 1. Simplified versions that are harder than the source (4 of 17)

Measured by Flesch-Kincaid grade level. The clearest case is PDF 3, *Solids →
Everyday examples*:

> **Source (grade 2.9):** An ice cube keeps its shape whether it sits in a bowl
> or on a plate. A wooden block stays the same size and shape no matter where
> you put it. A rock does not flow or spread out like a liquid would.
>
> **Simplified (grade 6.7):** An ice cube maintains its form regardless of its
> location. Similarly, a wooden block and a rock retain their size and shape,
> unlike liquids that flow or spread.

"Keeps its shape" became "maintains its form regardless of its location". The
same happens to PDF 3's *Liquids → Everyday examples* and *Gases → Everyday
examples*, and to PDF 1's *Flow* line ("Liquids and gases can flow, while
solids normally do not." → "…but solids generally do not.").

#### 2. Elaborated versions that are no longer than the source and drop facts (3 of 15)

- PDF 2, *As a general rule* (27 words → 27 words). The source says "Solids have
  the least particle energy and movement; gases have the most." The Elaborated
  version only mentions solids. **The fact about gases is lost.**
- PDF 3, *States of Matter (Part 1 of 2)* (50 words → 44 words). The source's
  examples ("Your desk, the air you breathe, the water you drink, and even you
  are all made of matter.") are dropped. The version is only reworded in harder
  vocabulary ("possessing both mass and volume", "constituent particles").
- PDF 2, *Matter usually exists in one of three everyday states* (27 → 27
  words). A reworded version with harder words, not an elaboration.

#### 3. Elaborated versions that bring in terms from outside the lesson

The prompt forbids outside facts. These terms appear in generated Elaborated
versions and **nowhere in any of the three PDFs**: *intermolecular forces*,
*kinetic energy*, *thermal energy*, *cohesive forces*, *constituent particles*,
*phase change*, *temperature*. Example, PDF 3 *Liquids → Key idea*:

> **Source:** heating a liquid gives its particles enough energy to escape into
> the air entirely, a process called evaporation, which turns the liquid into a
> gas at its boiling point.
>
> **Elaborated:** When a liquid is heated, the added energy increases the
> kinetic energy of its particles. This increased energy enables the particles
> to overcome the intermolecular forces holding them together, resulting in
> evaporation and a phase change to a gaseous state at the boiling point.

#### 4. One Elaborated version states something false

PDF 3, *Liquids → Everyday examples*:

> **Source:** Water poured from a bottle into a cup changes shape but not amount.
>
> **Elaborated:** When liquid, such as water, is poured from one container into
> another, the liquid's volume changes shape to fit the new container.

The source's point is that the amount (volume) stays the same. The version
leaves that out and says the volume changes. For a lesson about exactly this
property, it teaches the wrong idea.

### Why it happens

- `_parse_response` (`variant_generator.py:87`) only checks that the JSON is
  valid, that both fields are non-empty and different, and that neither
  exceeds its **maximum** word count. Nothing else about the text is checked.
- The Elaborated version has a maximum length (`max(20, 2 × source words)`)
  but **no minimum**, so a shorter or same-length rewording passes.
- `course/readability.py` already has `compare()`, which classification uses to
  tell simpler from fuller text. Generation never calls it on its own output.
- There is no grounding check like the one question generation has, so terms
  that are not in the source are not caught.
- Generated versions are saved and used without any teacher review step unless
  a teacher opens *Content versions* on their own.

### Fix items

- [x] Run `readability.compare(source, generated)` on each generated version.
  Reject and retry (the request already retries up to 3 times) when the
  Simplified version is not easier, or the Elaborated version is not longer.
  *Done with Dale-Chall instead of FKGL (see BUG-001 Resolution B/C for why).*
- [x] Give the Elaborated version a minimum length (e.g. more words than the
  source).
- [x] Add a lexical grounding check: flag content words not found in the
  source (or anywhere in the topic's PDFs), as question generation does.
  *For Simplified only — see Resolution.*
- [x] Anything that still fails after retries should reach the teacher as
  "needs review", not be saved as finished. *Done as a warning instead of a
  blocking review — see Resolution.*
- [x] Fact-dropping (item 2) and false statements (item 4) will not be caught
  by the checks above. A teacher review or an LLM judge is needed for those.
  Decide which. *Decided: fact-dropping is checked by the "facts kept"
  measurement; false statements are not caught (no LLM judge / NLI model, by
  decision). The teacher can replace any version on Content versions.*

### Resolution (2026-09-29)

Every generated version is checked by code, in `check_generated_version`
(`backend/course/variant_generator.py`), using the measurements from
`course/content_measures.py`:

- **Simplified:** keeps the facts (MiniLM coverage) + easier (Dale-Chall) +
  at most 1 unfamiliar word the source does not use.
- **Elaborated:** keeps the facts + fuller (more words than the source). The
  generator is told to add no new facts, so "Elaborated" here means *fuller*,
  not *adds content*.

A version that fails is **written again, with Gemma told why** ("it is not
easier to read than the SOURCE; use shorter, everyday words"). A passing one is
kept from whichever attempt produced it. If all 3 attempts fail, that level
**keeps the Normal text** (`generator_model = "normal-text-fallback"`), so a
harder or incomplete version never reaches a learner and publishing is not held
back.

**Teacher warning:** Content versions shows "Using the Normal text for now" on
such a level, with a **Write your own explanation** button (the existing
editor). Saving an explanation clears the warning (`fallback` flag in the
learning-resources payload, `lessons/views.py`; `VersionSlotCard` in
`web-app/src/pages/TopicDetailPage.jsx`). It is optional.

**Measured on 10 real sources** (gemma3:4b): Elaborated 10/10 kept from Gemma;
Simplified 5/10 kept, **5/10 fell back to the Normal text** (4 were not easier
after 3 attempts — some sources, like "Solids have a fixed shape and volume.",
are already simple; 1 used the words "examples, include"). Generation now makes
about **2.4× more Gemma calls** (24 for 10 objects), because of the retries.

**Known limits:**

- Outside terms are **not** checked in Elaborated versions. Tried and measured
  unusable: gemma3:4b's elaborations use 4–28 ordinary academic words each
  ("within", "movement", "consequently") that are not on the Dale-Chall list,
  and a word list cannot tell those from "intermolecular" or "kinetic energy".
  The *kinetic energy / intermolecular forces* example above is still not caught.
- A false statement in similar words (item 4) is not caught.
- Possible tuning: allow 2 unfamiliar words in a Simplified version instead of
  1 (would avoid fallbacks like "examples, include"). Not decided.

**Tests:** `course/tests.py` (`GeneratedVersionCheckTests`,
`GeneratedVersionMeasureTests`), `lessons/test_version_editing.py` (warning).

---

## BUG-003 — Extraction splits a lead-in phrase off as a heading, so text starts mid-sentence

**Status:** Fixed
**Stage:** PDF extraction (heading detection)
**Found:** 2026-09-27, same topic and PDFs as BUG-001

### What is wrong

When a paragraph opens with a short bold or styled lead-in (*"Key idea:"*,
*"Example:"*, *"As a general rule,"*), extraction treats the lead-in as a
section heading. The body then starts mid-sentence, in lower case:

| PDF | Heading extracted | Text starts with |
|---|---|---|
| PDF 2 | "Matter usually exists in one of three everyday states" | "solid, liquid, and gas. What state matter is in depends on…" |
| PDF 2 | "As a general rule" | "the more energy particles have, the faster they move…" |
| PDF 2 | "Example" | "an ice cube (solid) left on a counter absorbs heat from the air…" |
| PDF 3 | "Key idea" (under *Solids*) | "solid particles are held in place by strong forces between them…" |
| PDF 3 | "Key idea" (under *Liquids*) | "heating a liquid gives its particles enough energy to escape…" |
| PDF 3 | "Key idea" (under *Gases*) | "cooling a gas slows its particles down until they pack close…" |

In the first row, the original sentence was most likely "Matter usually exists
in one of three everyday states: solid, liquid, and gas." The first half became
a heading.

### Effects

- The fragments become concept names: three concepts called "Key idea", one
  called "Example", one called "As a general rule". A learner (and the learning
  path) cannot tell the three "Key idea" concepts apart.
- Classification (BUG-001, Wrong 4) and version generation (BUG-002, item 2)
  work on incomplete sentences.
- Audio narration made from this text will start without the sentence's
  opening words.

### Fix items

- [x] Do not treat a short styled phrase as a heading when it runs into the same
  line or sentence as the body text (it ends with ":" or ",", or the next text
  starts in lower case).
- [x] When such a lead-in is kept, keep it inside the body text so the sentence
  stays whole.

### Resolution (2026-09-29)

In `build_section_learning_objects` (`lessons/services/content_generator.py`):

- **Any label, not a word list:** a short line (≤ 5 words) followed by text that
  starts in **lower case** opens that sentence, so it stays in its section
  ("Remember: cooling a gas…", "Big idea: …"). The known labels ("Key idea",
  "As a general rule", "Everyday examples") are still recognised for PDFs where
  the next word is capitalised.
- **Inline "Label: text" and "Label — text"** stay one sentence when the label
  is a lead-in (≥ 4 words, or a known label, followed by lower case) — including
  a dash, which the first fix missed ("Flowering plants rely on pollination —
  pollen must travel…").
- **Guards so real concepts still split:** a label that is a word the lesson
  itself uses ("Solid: matter with…", where the lesson says "a solid") is a
  definition, not a lead-in; runs of definitions (glossaries) still split;
  under a numbered section an inline label stays a part linked to that section.
- Confirmed on the real PDF 3: all three "Key idea" lines stay inside
  *Solids*, *Liquids* and *Gases*.

**Tests:** `lessons/test_inline_leadins.py`, `lessons/test_extraction_fixes.py`.

---

## BUG-004 — Sub-sections and figure descriptions become separate concepts instead of staying in their section

**Status:** Fixed (the question-generation observation at the end is out of this round's scope)
**Stage:** Grouping / concept bundles
**Found:** 2026-09-27, same topic and PDFs as BUG-001

### What is wrong

The same kind of content is handled differently depending on the PDF:

- **PDF 2:** its *Solids* section's sub-parts (*Key properties of solids*,
  *Everyday examples*, the diagram description) stay inside the *Solids* bundle.
- **PDF 3:** its *Solids*, *Liquids* and *Gases* sections each have an
  *Everyday examples* and a *Key idea* sub-section. These became **six
  separate concepts** (three "Everyday examples", three "Key idea") instead of
  staying in their section. Their names lose the section they belonged to, so
  "Everyday examples" of solids and of gases look identical to a learner.
- **Figure and table descriptions** also became concepts of their own:
  - PDF 1's particle diagram is a concept named after the description's first
    sentence: "The image shows three arrangements of particles representing
    solids, liquids, and gases".
  - PDF 2's changes-of-state table is a separate concept named "Changing From
    One State to Another". It sits beside the real *Changing From One State to
    Another* section rather than inside it.

Each of these then gets its own generated Simplified and Elaborated versions,
e.g. "The image presents three distinct arrangements of particles…".

### Effects

- More, smaller concepts than the lesson has, with duplicate or meaningless
  names, which feed the learning path.
- Figure descriptions are taught as standalone steps, separate from the
  section they illustrate. Their audio will say "The image shows…" as a lesson
  step of its own.

### Fix items

- [x] Keep a sub-section and a figure/table description in the bundle of the
  section that contains it (restore the nesting; do not merge concepts after
  the fact).
- [x] A concept must never be named after a figure description's sentence.

Also seen at question generation: PDF 1's particle-diagram concept got 5
questions about the drawing ("Which arrangement of particles represents a
solid?"). PDF 2's changes-of-state table concept, the same kind of object, got
none.

### Resolution (2026-09-29)

- **Sub-sections** ("Key idea", "Everyday examples") stay in their section:
  see BUG-003.
- **A figure gets the section it sits in:** the heading printed above it on
  the page, including a heading with no text of its own (see BUG-013).
- **Parts join their section's concept** when no other PDF teaches them
  (`attach_orphan_objects_to_their_section`), now also when the heading has
  no text of its own — its first part stands in for it (the flower module's
  four steps under "How Flowering Plants Reproduce"). Glossary sections ("Key
  Vocabulary") are excluded: each term stays its own concept.
- **Figure names:** a supplied title, then the printed caption, then
  "<section> - figure" / "<section> - table" (numbered when a section has
  several), and only as a last resort the description's first sentence.
  Generated names such as "Solids - figure" never count as matching labels
  between PDFs, so two figures are not auto-grouped just because they sit in
  same-named sections. Two figures *are* grouped automatically when their
  printed caption or the text printed inside them (≥ 4 words, ≥ 80% shared)
  agrees.

**Tests:** `lessons/test_inline_leadins.py`, `lessons/test_label_corroboration.py`,
`lessons/test_image_grouping.py`, `lessons/test_section_joins.py`.

---

## BUG-005 — Questions with wrong answer keys are saved as final (7 of 50)

**Status:** Open — **highest priority**: a learner who answers correctly is marked wrong
**Stage:** Question generation → grounding gate (`backend/question_generation/services/grounding.py`)
**Found:** 2026-09-28, question run on the same topic and PDFs as BUG-001

### What is wrong

All 50 final questions passed the grounding gate. The judge actually ran on
every draft (the run trace shows 0 unverified). Still, 7 of the 50 have the
wrong answer, and 4 of them are a source sentence copied almost word for word
and then marked **False**:

| Concept (PDF) | Question | Saved key | Source says | Correct key |
|---|---|---|---|---|
| As a general rule (PDF 2) | "The more energy particles have, the further apart they spread." | False | "the more energy particles have, the faster they move and the further apart they spread." | True |
| Everyday examples, *Gases* (PDF 3) | "A helium tank fills every party balloon you attach to it, one at a time." | False | "A helium tank fills every party balloon you attach to it, one at a time." The explanation invents "all at once". | True |
| Comparing the Three States (PDF 1) | "The table shows that solids have particles very close together, liquids have them closer than gases, and gases have particles far apart." | False | "solids have particles very close together, liquids have them closer than gases, and gases have particles far apart" | True |
| Summary: what to remember, Part 1 (PDF 2) | "Liquids keep a fixed volume but can change shape to fit their container." | False | "Liquids keep a fixed volume but flow to fit their container" | True |
| Comparing the Three States (PDF 1) | "True or False: Solids have a definite volume." | False | "Solids and liquids have definite volume". The explanation claims the opposite. | True |
| Comparing the Three States (PDF 1) | "Gases can take the shape of their container, while solids and liquids do not." | True | "liquids and gases take the shape of their container" | False |
| Everyday examples, *Solids* (PDF 3) | "A liquid can change its shape when placed on a plate." | False | "A rock does not flow or spread out like a liquid would." The whole topic says liquids take their container's shape. | True |

In several cases, the saved explanation itself supports the opposite key.

**After publishing:** a published step serves at most one LOT and one HOT
question, 22 in total for this topic. **4 of those 22 are from the table
above** (the *general rule*, *helium tank*, *table shows…* and *liquid on a
plate* questions), so about 1 in 5 questions a learner sees is keyed wrong.

### Why it happens

- Both the generator and the judge are `llama3.2:3b` by default
  (`QUESTION_LLM_MODEL`; `QUESTION_JUDGE_MODEL` falls back to it). For a
  true/false question, the judge only sees "Answer: False" next to the
  statement and has to work out the truth value itself. On this run it got
  that wrong 7 times.
- It also fails the other way. It rejected correct questions with invented
  reasons, e.g. it rejected "A solid keeps its shape and size when moved."
  because "a solid can change its shape when moved".
- This matches the open item in `docs/AGENT_LOG.md`: the judge is uncalibrated,
  and it was tested on only two questions.

### Fix items

- [ ] Cheap deterministic check for true/false questions: if the statement
  (ignoring "True or False:") matches a source sentence almost exactly, the key
  must be True. It would have caught 4 of the 7.
- [ ] Check that the explanation agrees with the key. When the explanation
  restates the source claim and the key is False, reject the question.
- [ ] Try a stronger judge model than the generator, and measure it on a small
  labelled set. The 7 wrong and several wrongly rejected questions above are a
  starting set.
- [ ] Until then, send true/false questions to teacher review instead of
  straight to final.

---

## BUG-006 — Every concept falls short of its question target; the lexical gate rejects on harmless words

**Status:** Open
**Stage:** Question generation → grounding gate (`grounding.py`, `pipeline.py`)
**Found:** 2026-09-28, same run as BUG-005

### What is wrong

The target is 3 lower-order (LOT) + 3 higher-order (HOT) questions per concept,
which is 102 for this topic's 17 concepts. **50 were saved.** No concept reached
6.

- "Matter", the largest concept (533 words of source), got 2 questions and no
  LOT at all.
- 7 concepts have **no HOT question**: Everyday Examples (PDF 1), Example
  (PDF 2), all three "Key idea" concepts of PDF 3, and PDF 3's *Liquids* and
  *Gases* "Everyday examples".

### Why it happens

83 drafts were rejected by the gate. **51 of those were rejected by the lexical
stage** for a single ordinary word not found in the PDFs. The tolerance
`QUESTION_VALIDATION_MAX_NOVEL_TERMS` is 0. Examples of rejected drafts and the
word that failed them:

| Draft | Rejected for |
|---|---|
| "What determines the state of matter?" | *determines* |
| "Which type of matter has the most energy particles and movement?" | *type* |
| "Heat energy is needed to change matter from one state to another." | *needed* |
| "When a gas cools, what happens to its particles?" | *slower* |
| "What is shown in the arrangement of particles that represents a solid?" | *shown* |

Question words and ordinary verbs are treated as new facts. The generator gets
one corrective retry (`QUESTION_VALIDATION_MAX_RETRIES = 1`). After that the
bank is accepted short.

Short sources (22–44 words, often a single example list) also rarely support a
question that combines two facts, which is why HOT is empty there. BUG-003 and
BUG-004 make this worse by cutting the lesson into small fragments.

### Fix items

- [ ] Stop the lexical stage from failing on function words and common verbs.
  Use a stop-list or general vocabulary list, or allow 1–2 novel terms and let
  the judge decide. Raise the tolerance only after BUG-005's check exists,
  since the lexical stage is currently the safer of the two stages.
- [ ] Report the shortfall to the teacher per concept (it is only a
  `shortfall_warning` event in the run trace today).

---

## BUG-007 — Word-for-word recall questions are labelled higher-order (HOT)

**Status:** Open
**Stage:** Bloom classification (`question_generation/services/bloom_classifier.py`, `finalize_node_questions` in `pipeline.py`)
**Found:** 2026-09-28, same run as BUG-005

### What is wrong

The adaptive quiz walks a learner through *remember → understand →
apply/analyze*. Several questions that only ask the learner to recognise a
sentence copied from the source are labelled **HOT / analyze**:

- "Melting is the change of state from solid to liquid." (the source: "Melting —
  solid to liquid")
- "In a solid, particles are packed tightly together in a fixed pattern."
- "The particles in a gas are spread far apart and move quickly in every
  direction."
- "Scientists sort matter into three common states based on how its particles
  are arranged and how they move: solid, liquid, and gas."

"All matter is made up of the same kinds of particles" is labelled HOT/analyze,
while its near-copy "All matter is made of the same kinds of tiny particles" is
labelled LOT/apply, for the same concept.

### Why it matters

The HOT count in BUG-006 is overstated: some concepts meet part of their HOT
quota with recall questions. A learner reaching the top tier gets recall, not
analysis.

### Why it happens

The classifier sees only the question text, not the source. A long declarative
true/false statement is labelled *analyze* regardless of whether it is copied
from the source.

### Fix items

- [ ] When a question's stem (or correct option) is a near-copy of a source
  sentence, cap its level at *remember*.
- [ ] Add these examples to the classifier's evaluation set.

---

## BUG-008 — Malformed and near-duplicate questions reach final

**Status:** Open
**Stage:** Question generation → structural validation and dedup (`question_generator.py::_validate_question`, `pipeline.py::_dedup_key`)
**Found:** 2026-09-28, same run as BUG-005

### What is wrong

**Malformed questions** that pass structural validation:

- A true/false question disguised as multiple choice. The stem is "Your desk,
  the air you breathe, the water you drink, and even you are all made of
  matter." and the choices are *A) False, B) True, C) Solid, D) Liquid*.
- A statement used as a multiple-choice stem: "You can change the state of
  matter from solid to liquid by adding heat energy." The choices are four
  more statements.
- True/false stems left unfinished: "A rock does not flow or spread out like a
  liquid would. This is true because…" (and the same for the wooden block).

**Near-duplicates in one concept's bank.** Dedup only catches identical text:

- "All matter is made up of the same kinds of particles." / "All matter is made
  of the same kinds of tiny particles."
- "A gas has no definite shape and no definite volume." / "A gas has no definite
  shape and no definite volume — it expands to completely fill whatever
  container it is in."
- "Which of the following states of matter is a gas?" (answer: water vapor) /
  "What state of matter does water vapor represent?" (answer: gas)
- "Which process allows a gas to change state to a liquid?" / "What is the
  process called when a gas cools and its particles pack close enough to form
  a liquid again?"

With banks already short (BUG-006), each duplicate is one fewer real question.

### Fix items

- [ ] Reject a multiple-choice question whose stem has no question form (no "?",
  no "which/what/…"), or whose choices include "True"/"False".
- [ ] Reject a stem ending in "because…" or "…".
- [ ] Deduplicate on similarity (e.g. token overlap or the embeddings grouping
  already uses) rather than exact text.

---

## BUG-009 — Published learning path teaches "Matter" fifth, after steps that depend on it

**Status:** Open
**Stage:** Learning path (`backend/learning_path/services/criteria.py`, `publishing.py`)
**Found:** 2026-09-28, after publishing the same topic as BUG-001

### What is wrong

The published path (16 steps) opens like this:

1. "Matter usually exists in one of three everyday states". The step starts
   mid-sentence: "solid, liquid, and gas. What state matter is in depends on…"
2. "The image shows three arrangements of particles representing solids,
   liquids, and gases" (a figure description)
3. "As a general rule" ("the more energy particles have, the faster they
   move…")
4. "Key idea" ("solid particles are held in place by strong forces… at the
   melting point… the solid becomes a liquid")
5. **"Matter"**: "Matter is anything that has mass and occupies space…", plus
   the introductions of solid, liquid and gas.

A learner meets particle energy and melting before being told what matter, a
solid or a liquid is.

### Why it happens

Accepted prerequisite links point the wrong way. The path is built to respect
them:

- *figure description* → **Matter** (and → *Comparing the Three States*, →
  *Changing From One State to Another* table, → *Key idea* for solids)
- *Key idea* (solids melting) → **Matter**
- *Key idea* (gas condensation) → *Comparing the Three States*

Nothing links Matter → "Matter usually exists in one of three everyday
states", so the fragment starts the path on document order alone.

BUG-003 (sentence fragments named "Key idea") and BUG-004 (figure descriptions
as separate concepts) supply most of the concepts involved. Links from a figure
description, or from a fragment, to the concept that defines their subject are
still a criteria problem. This topic is not in the gold-standard set, so no
test catches it.

### Fix items

- [ ] Find which criteria votes produced *figure description → Matter* and *Key
  idea → Matter* (the `evidence` on each `ConceptPrerequisite` row) and why.
- [ ] Add this topic's expected order as a gold fixture once BUG-003/004 are
  fixed, so it is tested alongside topics 62 and 79.

---

## BUG-010 — Some PDF text never reaches any learner after publishing

**Status:** Open
**Stage:** Publishing / published path (`learning_path/services/published.py`)
**Found:** 2026-09-28, after publishing the same topic as BUG-001

### What is wrong

The published text (every step's three versions and every alternate) was
checked against every PDF section in the topic.

**Never served to anyone:**

- **PDF 3, *Gases*** ("In a gas, particles are spread far apart and move
  quickly in every direction. A gas has no definite shape and no definite
  volume — it expands to completely fill whatever container it is in."). This
  is PDF 3's whole explanation of gases.
- PDF 2, *Everyday Examples* (section 7, text and table), classified Extra.
- PDF 3, *Comparing the Three States* table description, classified Extra.

**Only served as a Simplified or Elaborated version, never as a normal
step:** PDF 2's entire *Solids*, *Liquids*, *Gases* and *Comparing the Three
States* sections (14 sections), PDF 3's *Solids* and *Liquids*, and PDF 3's
*How Matter Changes State*. A learner who stays on Normal never hears any of
them.

### Why it happens

- **PDF 3 *Gases*:** grouping paired it with PDF 2's *Summary: what to remember
  (Part 2 of 2)*, as that concept's Simplified version (BUG-001, Wrong 3). At
  publish, the path joins Summary Part 1 and Part 2 into one step
  (`_passage_parts`), but the step only reads versions from Part 1's concept
  (`_versions(parts, representative.group)`). Part 2's concept, and the
  Simplified version it held, is dropped. *Gases* is also marked
  `represented_by`, so it is not offered as an alternate either.
- **Extras:** see BUG-001, cause E.
- **Version-only sections:** a consequence of BUG-001's pairings. Whole
  sections were made into versions of other concepts.

**Update 2026-09-29:** the *Gases* case is gone at its source — summaries are
no longer paired as versions of another concept (BUG-001 Resolution A), and a
role the measurements do not support is no longer stored, so whole sections are
no longer turned into versions by a wrong label. **The code bug itself is still
open** (publishing, not changed in this round): a joined step reads versions
only from its first part's concept. Extras are held back on purpose (BUG-001 E),
so the publish-time check below should treat Extra as intentional, not missing.

### Fix items

- [ ] When `_passage_parts` joins parts from different concepts, take the
  versions from every one of those concepts, not only the first.
- [ ] Add a publish-time check: every non-empty section of every PDF must be
  served somewhere (Normal, a version, or an alternate). List any that are not
  to the teacher before publishing.

---

## BUG-011 — Learners are asked about text they were never given

**Status:** Open
**Stage:** Question generation source text (`question_generation/services/pipeline.py::concept_source_text`) and publishing
**Found:** 2026-09-28, after publishing the same topic as BUG-001

### What is wrong

A concept's questions are written from **every** PDF's text for that concept
(Normal plus the texts serving as Simplified and Elaborated). A learner on the
Normal version only hears the Normal text, but is asked all the questions.
Examples from the published path:

- **"Matter"** step: its only question is "Particles in a solid are drawn as
  evenly spaced dots arranged in tidy rows and columns." (True). This comes
  from PDF 2's *Diagram description*, which is only in the Simplified version.
  The Normal text never mentions a drawing.
- **"Comparing the Three States"** step: "The table shows that solids have
  particles very close together…" asks about PDF 2's table, which is only in
  the Elaborated version (and its key is wrong, BUG-005).
- **"Summary: what to remember"** step: "In a solid, particles are packed
  tightly together in a fixed pattern." comes from PDF 3's *Solids*, which is
  only the Simplified version.

### Why it happens

`concept_source_text` deliberately joins every telling. Its docstring says an
Elaborated learner hears other wording, and short Normal texts don't hold
enough facts for higher-order questions. Nothing records which telling a
question came from, and the published step serves the same questions whichever
version the learner is on.

### Fix items

- [ ] Decide the rule as a group. Either questions come only from the Normal
  text, or each question is tagged with the version(s) whose text supports it,
  and a learner is only asked questions supported by the version they heard.
- [ ] Never ask about a figure's appearance ("drawn as dots") when the step may
  be heard as audio only.

---

## BUG-012 — Published steps: wrong titles, a step with no questions, headings read aloud

**Status:** Open
**Stage:** Published path (`learning_path/services/published.py`, `course/models.py::bundle_segments`)
**Found:** 2026-09-28, after publishing the same topic as BUG-001

### What is wrong

- **The "Comparing the Three States" step is titled "Shape".** `_chunk_title`
  uses the first section's title ("Shape", then "Volume", "Particle
  arrangement", "Flow"), not the concept's name. The same rule only gives
  "Matter" its right name because its first section happens to be called
  "Matter".
- **A step titled "6. Changing From One State to Another"** (PDF 2's
  changes-of-state table) keeps its section number. Its `section_title` is
  "Comparing the Three States", which is the previous section, and **it has no
  questions at all**.
- **Version text starts with its source heading, including part markers.**
  The first step's Simplified version begins "States of Matter (Part 2 of 2).
  Each state has its own shape…", so the part marker is part of what a learner
  reads and hears. Others begin "Solids.", "Liquids.", "How Matter Changes
  State.".
- **The first step's alternate repeats its own Simplified version.** The
  alternate is PDF 3's *States of Matter* Part 1 + Part 2. Part 2 is already
  the step's Simplified version, so a learner switched to the alternate hears
  that text again.

### Fix items

- [ ] Title a step by its concept's name (`group.label`), not its first
  section's title.
- [ ] Strip "(Part n of m)" and leading section numbers from any heading that
  ends up in served text.
- [ ] Exclude from an alternate any section already serving as one of the
  step's versions.
- [ ] Decide what a step with no questions should do (block publishing, warn
  the teacher, or pass the learner through), and make publish report it.

---

## BUG-013 — A table or figure under a heading with no text of its own gets the previous section

**Status:** Fixed
**Stage:** Extraction (`lessons/services/content_generator.py`)
**Found:** 2026-09-28, in `Solid, Liquid, Gas 2.pdf` (a version of PDF 2 with numbered sections) and PDF 3

### What was wrong

| PDF | Table | Section it got | Should be |
|---|---|---|---|
| Solid, Liquid, Gas 2 | "6. SOLID VS. LIQUID VS. GAS" | PARTICLE ARRANGEMENT | its own heading |
| PDF 3 | "Comparing the Three States" | Gases | its own heading |

Section 6 is only a heading and a table. The table's text is (correctly) taken
out of the lesson text, so the heading had no text under it and was dropped,
and the table took the section of the last passage before it.

### Fix

A figure's section now comes from its **position**: the last heading printed
above it on the page, even a heading with no text of its own. If that heading
has text under it, the figure joins that text's section ("Shape" sits in
"Comparing the Three States"). The old "previous passage" rule is only a
fallback.

**Tests:** `lessons/test_extraction_fixes.py`, `lessons/test_figure_sections.py`.

---

## BUG-014 — The document's title block is read aloud as lesson content

**Status:** Fixed
**Stage:** Extraction (`lessons/services/instructional_content_classifier.py`)
**Found:** 2026-09-28, PDF 3

### What was wrong

PDF 3's first concept began "Solid, Liquid, and Gas / Science · Lesson 1 ·
Grade 4 / Matter is anything that has mass…": the subtitle and the subject /
lesson / grade line were attached to the first concept and read aloud.

### Fix

- A short line naming a subject, lesson, grade, quarter or week joined by `·`,
  `|` or a dash is document information (`_is_document_label_line`).
- On the first page, before the first paragraph, a short uncertain line under
  the title is the title block's subtitle; a title and subtitle printed as one
  block keep only the title line (`_mark_title_block`).

**Tests:** `lessons/test_extraction_fixes.py` (`TitleBlockTests`).

---

## BUG-015 — Headings phrased as questions were deleted, with the explanation under them

**Status:** Fixed
**Stage:** Extraction (`instructional_content_classifier.py`, `content_generator.py`)
**Found:** 2026-09-28, `Grade8_English_Q1W2_Handout.pdf` and PDF 3

### What was wrong

"What is Point of View?" (large, bold) over "Point of view is the angle or
perspective from which a story is told…" was classified as a quiz question
because it ends with "?". That opened an excluded (assessment) section, and the
definition under it reached no learner. The same happened to "What is Plot?",
"What is Conflict?" and PDF 3's "What Is Matter?" (the definition of matter).
A second step, the final accessibility review, also dropped any concept whose
*title* is a question.

### Fix

A short, emphasised line ending in "?" that is directly followed by an
explanatory paragraph (no choices, blanks or further questions) is a
**question-form heading**, not a quiz item (`_mark_question_headings`). It never
opens an excluded section, it closes one that is open, and the final review
keeps a concept built from it (its lines are still checked one by one).

**Tests:** `lessons/test_extraction_fixes.py` (`QuestionHeadingTests`).

---

## BUG-016 — A dash lead-in replaced the author's heading

**Status:** Fixed
**Stage:** Extraction (`content_generator.py`)
**Found:** 2026-09-28, `Lesson-4_Reproduction-in-Non-Flowering-Plants.pdf`

### What was wrong

Under the heading "Comparing With Flowering Plants", the paragraph "Flowering
plants rely on pollination — pollen must travel from the anther to the stigma…"
became a concept titled "Flowering plants rely on pollination" whose text began
"pollen must travel…": the author's heading was replaced and the sentence cut.
The rule that adopts a paragraph's own label ("Heading" over "Term: definition")
did not recognise a sentence lead-in.

### Fix

The label-adoption rule skips a sentence lead-in, and the lead-in rule accepts a
dash as well as a colon (see BUG-003).

**Tests:** `lessons/test_extraction_fixes.py` (`DashLeadinTests`).

---

## BUG-017 — "vs." and other abbreviations were treated as the end of a sentence

**Status:** Fixed
**Stage:** Extraction / chunking (`content_generator.py`)
**Found:** 2026-09-28, `Grade8_English_Q1W2_Handout.pdf`

### What was wrong

"• Character vs. Nature — The character struggles…" was split after "vs.":
one chunk ended "• Character vs.", the next began "Nature — …", and inside a
chunk "Character vs.\nTechnology" was read with a pause mid-phrase.

### Fix

A sentence never ends after a known abbreviation (vs., e.g., i.e., Mr., Dr.,
Fig., …) or a single capital initial (`_split_sentences`). Words that often end
real sentences ("in", "no") are not on the list.

**Tests:** `lessons/test_extraction_fixes.py` (`AbbreviationTests`).

---

## BUG-018 — "Part 3: …" divisions were dropped, so the concepts under them had no section

**Status:** Fixed
**Stage:** Extraction (`content_generator.py`)
**Found:** 2026-09-28, `Grade8_English_Q1W2_Handout.pdf`

### What was wrong

"Part 3: Understanding Point of View (POV)" was dropped as a structural label
("Part 3"), so "First Person POV", "Second Person POV" and "Third Person POV" had
no section.

### Fix

"Part N:" / "Section N:" followed by a name becomes the section of what follows
it ("Understanding Point of View (POV)"). A bare "Part 3", or a module or lesson
label, is still treated as structure. The part keeps its section even when the
headings inside it are printed larger than the "Part" label.

**Tests:** `lessons/test_extraction_fixes.py` (`QuestionHeadingTests`).

---

## BUG-019 — Two concepts with the same name in one PDF

**Status:** Fixed
**Stage:** Extraction (`content_generator.py`, `disambiguate_repeated_titles`)
**Found:** 2026-09-28, `Solid, Liquid, Gas 2.pdf`

### What was wrong

The PDF has a *SOLID* section and a "Solid" part under *PARTICLE ARRANGEMENT*:
two concepts called "Solid" (also for Liquid and Gas). A learner met two steps
with the same name, and the learning path treats same-named concepts as one idea.

### Fix

When a name repeats inside one PDF, the part gets its section: "Solid (Particle
Arrangement)". A name used once, the pieces of one split passage, and a heading
other objects name as their section are never renamed.

**Tests:** `lessons/test_extraction_fixes.py` (`RepeatedTitleTests`).

---

## BUG-020 — Bullet lists read as one run-on sentence; "=" read as "equals"

**Status:** Fixed
**Stage:** Narration text (`content_generator._accessible_narration_text`)
**Found:** 2026-09-28, `Solid, Liquid, Gas 2.pdf`

### What was wrong

"Characteristics of Solids: / Has a definite shape / Has a definite volume /
Particles are tightly packed" had line breaks but no full stops, so the voice
could run it together. "SOLID = keeps its shape and volume" was read "SOLID
equals keeps…".

### Fix

In the spoken form only (the saved text is unchanged): each list item ends with
a full stop unless the sentence continues in lower case on the next line;
bullet and checkbox glyphs are dropped; "=" is read "means", or "equals" between
numbers.

**Tests:** `lessons/test_extraction_fixes.py` (`SpokenFormTests`).

---

## BUG-021 — A table was silent when it had no narration

**Status:** Fixed
**Stage:** Extraction / figures (`content_generator.describe_pdf_images`, `image_describer.spoken_table`)
**Found:** 2026-09-28, `Solid, Liquid, Gas 2.pdf`

### What was wrong

A table's text is taken out of the lesson (so it is not read twice). When the
vision model did not narrate the table (Ollama down, or narration capped for
speed), the table had no content at all.

### Fix

Until the model narrates it, a table reads its own rows: "Shape: Solid,
Definite. Liquid, Not definite. Gas, Not definite." This is recorded as a
stand-in, so publishing still replaces it with the model's narration. When PDF
extraction merged or lost a cell (the row no longer lines up with the header),
the values are read in order without column names rather than under the wrong
column.

**Tests:** `lessons/test_extraction_fixes.py` (`SpokenTableTests`, `TableStandInPublishTests`), `lessons/tests.py`.

---

## BUG-022 — A figure could be described twice (its narration and the printed paragraph)

**Status:** Fixed
**Stage:** Figures (`image_describer.py`, `content_generator._use_printed_descriptions`)
**Found:** 2026-09-28 (code review)

### What was wrong

When a PDF prints a description under a figure, the upload step compares it
with the model's narration and keeps the printed text once. But:

- figures narrated **later, at publish** (capped at upload, or Ollama down)
  skipped this check, so the learner heard the model's narration and then the
  printed paragraph saying the same thing;
- only the **first** text block under the figure was checked, so a description
  split into two paragraphs was half removed;
- the paragraph **above** a figure was never checked.

### Fix

The same check runs at publish (the printed paragraph stays in the lesson and
the figure only announces itself), a description split over several blocks is
taken whole, and the paragraph above a figure is checked too. The author's or
teacher's words are always the ones kept. Every similarity score is logged
("Printed-passage check: … score=…") so a model change that drifts the scores is
visible.

**Not verified with the real vision model** — see Notes.

**Tests:** `lessons/test_figure_descriptions.py`.

---

## BUG-023 — "Figure 1 —" was read aloud before a text-only figure description

**Status:** Fixed
**Stage:** Extraction (`content_generator.py`)
**Found:** 2026-09-28, `Lesson-4_Reproduction-in-Non-Flowering-Plants.pdf`

### What was wrong

The fern module prints "Figure 1 — Text Description of a Fern's Reproductive
Structures" followed by a written description, with no picture. The concept's
text began "Figure 1 — …", pointing a listener at a figure they do not have.

### Fix

The "Figure N —" label is dropped from the spoken text; the author's
description heading stays, as does the title ("Text Description of a Fern's
Reproductive Structures" — the author's own wording, deliberately not rewritten).

**Tests:** `lessons/tests.py`.

---

## BUG-024 — The same table in three PDFs became three concepts

**Status:** Fixed
**Stage:** Grouping (`lessons/services/unit_matching.py`, `semantic_grouping.py`)
**Found:** 2026-09-29, the three *Solid, Liquid and Gas* PDFs

### What was wrong

"Comparing the Three States" was PDF 1's text section (Shape, Volume, Particle
arrangement, Flow), PDF 3's table of that title, and PDF 2's table "6. SOLID VS.
LIQUID VS. GAS" — three concepts, met up to three times. A table is worded
nothing like prose, so the model scored them only 0.45–0.52 against each other,
below the 0.6 auto bar.

### Fix

- A section matched to a **single figure or table that carries its heading,
  word for word, as its title** is placed at the review threshold (0.3) — the
  same bar an exact label already gets in semantic grouping. Only for a
  specific heading; a generic one ("Everyday Examples") keeps the 0.6 bar, and
  two prose sections keep their original behaviour.
- **Table structure** counts as corroboration: the same header row
  (Property | Solid | Liquid | Gas) and at least half of the same row names.
- A unit placed next to a table already grouped with another PDF's table joins
  them, instead of pulling one table away.

Measured: one concept "Comparing the Three States" holding all three, the same
in upload orders 1-2-3, 3-2-1 and 2-3-1 (the topic went from 11 to 9 concepts).

**Tests:** `lessons/test_table_grouping.py`.

---

## BUG-025 — A concept was named after its first part, or after whichever table was grouped first

**Status:** Fixed
**Stage:** Grouping (`learning_resource_linker.py`, `unit_matching.py`)
**Found:** 2026-09-29

### What was wrong

PDF 1's "Comparing the Three States" concept was called **"Shape"** (its first
part); after BUG-024's fix it was called "6. SOLID VS. LIQUID VS. GAS" or
"Comparing the Three States" depending on upload order.

### Fix

A concept that stands for a heading with no text of its own, and a concept
formed by matching a section across PDFs, are named after that **section
heading**. A name a teacher locked is never changed.

Note: other concepts are still named after whichever PDF was uploaded first
("Solid" / "SOLID" / "Solids (Part 1 of 2)"). That name is provisional — the
content-versions step renames a concept after its Normal text.

**Tests:** `lessons/test_section_joins.py`.

---

## Notes for the whole team (2026-09-29)

### Decisions made in this round

- **Scope:** extraction, grouping and content versions only.
- **Extra is reserved** for a teammate's feature. It is not served to
  learners, and its behaviour was not changed — including that nothing checks
  what Gemma calls Extra (an unrelated text can be stored as Extra). Whoever
  owns Extra should decide whether the "facts kept" check should apply to it.
- **No NLI model.** Only an entailment model would catch a contradiction or a
  missing fact inside one sentence; it was considered and declined (new model,
  speed).
- **No Coh-Metrix.** It measures readability in more detail, not meaning, and
  it is a web tool that MAVIA cannot call.
- **FKGL is a note, not a rule.** Dale-Chall decides "easier" (measured better
  on these texts); FKGL and Gemma's confidence are recorded only.
- **One Gemma call per concept** for classification is kept. One call per
  candidate was measured (+2 correct, same number of wrong labels stored) and
  not built.
- **Teacher work:** failures are handled automatically (the text stays
  available, a version is generated or the Normal text is used). The only
  teacher-facing addition is the optional "Write your own explanation" warning
  (BUG-002).

### Known limits

- A contradiction or a dropped fact inside one sentence can still be stored
  (no NLI).
- Jargon rephrasing can pass as Elaborated.
- Outside terms in a *generated* Elaborated version are not checked.
- Half of the generated Simplified versions fell back to the Normal text in
  the test; generation makes about 2.4× more Gemma calls.
- Concept names at the grouping stage depend on upload order (provisional).

### Not tested yet

- **A full upload with figure narration on.** All real-PDF runs in this round
  had the vision model off. The printed-description check (BUG-022) and its
  0.28 similarity threshold have never run with the real model.
- **Other kinds of PDF:** scanned (image-only), long modules, two-column
  layouts. Only six short handouts were tested.
- **A teacher-labelled evaluation.** The classification numbers come from 21
  pairs mostly labelled by the developer; 30–50 teacher-labelled pairs from
  other topics are needed before quoting accuracy.
- The copy of PDF 2 described in BUG-001 (with "Summary: what to remember") was
  not available; the runs used `Solid, Liquid, Gas 2.pdf`, a different version.

### How the runs were done

Real-PDF checks uploaded the PDFs into a **throwaway SQLite database** (never a
dev database), confirmed each PDF and ran grouping, in several upload orders.
The classification evaluation called gemma3:4b on the labelled pairs, batched as
MAVIA calls it. These scripts are not in the repository.

### Test suite

All 1,184 backend tests pass. New test files: `lessons/test_inline_leadins.py`,
`lessons/test_extraction_fixes.py`, `lessons/test_section_joins.py`,
`lessons/test_table_grouping.py`; new tests in several existing files.
`course/testing.py` has `without_measurements()`, for tests of bundles,
collisions and generation that mock Gemma over short made-up texts and are not
about the measured check.

---
