"""Prerequisite evidence for the learning path (criteria v4).

Three kinds of evidence, each traceable to published work, decide whether one
concept precedes another. None of them reads where a concept sits in the PDF;
document order only breaks ties later, in ``order_with_links``.

* **R1 definition dependency** -- B's defining sentence names A
  (Wang et al. 2016; Talukdar & Cohen 2012).
* **R2 section containment** -- B sits under a heading naming A (Wang et al. 2016).
* **R3 passage reference distance** -- B's passages name A more than A's name B
  (Pan et al. 2017, generalising RefD, Liang et al. 2015).

R1 or R2 accepts a link; R3 alone only proposes one for the teacher. Nothing
here writes to the database or calls a model. See ``learning_path/CRITERIA.md``
and docs/superpowers/specs/2026-09-29-learning-path-criteria-v4-design.md.
"""

import re
from collections import Counter

from .concepts import heading_name, resolve_concept, structural_role
from .text_signals import (
    MIN_TERM_LENGTH,
    STOP_WORDS,
    definition_subject,
    first_sentence,
    mentions,
    normalize,
    singular,
)

# R3 threshold. RefD's authors recommend 0.02-0.1 (Liang et al. 2015, sec. 4.3);
# chosen on gold topics 62 and 79 only (Task 6 of the v4 plan). Measured
# 2026-09-29: results identical across that range on all three gold topics.
PRD_THRESHOLD = 0.05

ACCEPTED = "accepted"
PENDING = "pending"


def concept_names(concepts):
    """The name each concept can be *referred to by*, or None.

    A concept with no name cannot be referred to; it can still depend on a
    concept whose heading it sits under.
    """
    return {concept.id: resolve_concept(concept) for concept in concepts}


def concept_text(concept):
    """All of a concept's wording: every member PDF when known, else its own text."""
    return getattr(concept, "member_text", "") or concept.content or ""


def head_words(names):
    """``{concept id: head word}`` for multi-word names, where unambiguous.

    Lessons name a concept by its whole heading ("seed formation") but refer
    to it by its first significant word ("the seed"). A head word that two
    names share points at neither, so it never counts.
    """
    # Every name's head word counts toward ambiguity, single-word names too:
    # beside a "seed" concept, "seed" cannot also point at "seed dispersal".
    candidates = {}
    for concept_id, name in names.items():
        for word in (name or "").split():
            if word not in STOP_WORDS and len(word) >= MIN_TERM_LENGTH:
                candidates[concept_id] = singular(word)
                break
    counts = Counter(candidates.values())
    return {
        concept_id: word for concept_id, word in candidates.items()
        if counts[word] == 1 and len(names[concept_id].split()) >= 2
    }


def contained_in(holder, target_name):
    """True when any of ``holder``'s members sits under a heading naming the target.

    Wang et al. (2016) read textbook section structure as prerequisite
    evidence: a passage under the "Matter" heading builds on Matter even when
    it never says "matter".
    """
    if not target_name:
        return False
    members = getattr(holder, "members", None) or (holder,)
    return any(
        heading_name(getattr(member, "section_title", "") or "") == target_name
        for member in members
    )


def says(text, concept_id, names, heads):
    """True when ``text`` names the concept: its full name, or its head word.

    A multi-word name counts through its head word only when that word is
    unambiguous (see ``head_words``): lessons say "the seed", not "seed
    formation".
    """
    name = names.get(concept_id)
    if not name:
        return False
    normalized = normalize(text)
    if mentions(normalized, name):
        return True
    return concept_id in heads and mentions(normalized, heads[concept_id])


def says_plainly(text, concept_id, names, heads):
    """``says``, in at least one clause that is not a contrast.

    "A gas spreads out, unlike a solid" names solid only to say what a gas is
    not. The contrast check reads the full name only, so a head-word mention is
    always plain -- the known limitation recorded on ``_CONTRAST``.
    """
    if not says(text, concept_id, names, heads):
        return False
    return not only_contrastive_mentions(names[concept_id], text)


def _canonical(name):
    """A name compared word by word in singular form: "solids" matches "solid"."""
    return " ".join(singular(word) for word in (name or "").split())


def defining_sentences(concept, name):
    """The sentences that define ``concept``: R1's evidence.

    Wang et al. (2016) take a concept's first sentence as its definition. Here
    that is the first sentence of each member, counted only when it actually
    opens by defining the concept ("Melting is...", "Solids are..."). A member
    merely *titled* with the name is not enough: "Matter" over "It comes in
    three states: solid, liquid and gas" would make Solid a prerequisite of
    Matter (measured on gold topic 62, 2026-09-29).
    """
    if not name:
        return []
    target = _canonical(name)
    found = []
    for member in getattr(concept, "members", None) or (concept,):
        content = getattr(member, "content", "") or ""
        if _canonical(definition_subject(content)) == target:
            found.append(first_sentence(content))
    return found


def definition_dependency(a, b, names, heads):
    """R1: B's defining sentence that names A, when A must come first; else None.

    Wang et al. 2016, *Supportive relationship in concept definition*: "A is
    likely to be B's prerequisite if A is used in B's definition"; Talukdar &
    Cohen 2012 use the same first-sentence signal. Two definitions naming each
    other decide nothing, and a mention only inside a contrast is not a use.
    """
    if not names.get(a.id) or not names.get(b.id):
        return None
    if any(says(sentence, b.id, names, heads) for sentence in defining_sentences(a, names[a.id])):
        return None
    for sentence in defining_sentences(b, names[b.id]):
        if says_plainly(sentence, a.id, names, heads):
            return sentence
    return None


def passage_reference(concepts, names, heads):
    """R3: ``{(a id, b id): {prw_forward, prw_backward, prd, passages_forward, passages_backward}}`` for named pairs.

    Pan et al. 2017, Feature 2 (video reference distance), a generalisation of
    RefD (Liang et al. 2015) to course material without Wikipedia links. Pan's
    unit is a video; here it is a learning object, and a concept's units are
    its grouped members -- grouping already decided which passages teach it.

    ``prw_forward`` is the share of b's passages that name a; ``prw_backward``
    the share of a's passages that name b; ``prd`` their difference. A positive
    ``prd`` means b's passages lean on a, so a comes first. Position is never
    read, and no concept owns any word.
    """
    passages = {
        concept.id: [
            getattr(member, "content", "") or ""
            for member in (getattr(concept, "members", None) or (concept,))
        ]
        for concept in concepts
    }

    def share(holder_id, target_id):
        texts = passages[holder_id]
        if not texts:
            return 0.0
        return sum(1 for text in texts if says_plainly(text, target_id, names, heads)) / len(texts)

    named = [concept for concept in concepts if names.get(concept.id)]
    references = {}
    for a in named:
        for b in named:
            if a.id == b.id:
                continue
            forward, backward = share(b.id, a.id), share(a.id, b.id)
            references[(a.id, b.id)] = {
                "prw_forward": round(forward, 6),
                "prw_backward": round(backward, 6),
                "prd": round(forward - backward, 6),
                # Passage counts, so a reason can say "4 of 5" not "0.8".
                "passages_forward": len(passages[b.id]),
                "passages_backward": len(passages[a.id]),
            }
    return references


# A mention inside a contrastive clause says what something is *not* like.
#
# KNOWN LIMITATION, kept deliberately: this is a fixed list of English markers.
# It misses contrasts phrased without them ("solids do not flow", "different
# from a solid"), and it would not carry over to another language. A model that
# recognises contrast (NLI) would generalise; it was not adopted because it adds
# a model and slows the build, and whether contrast causes wrong edges in
# practice had not yet been measured.
# "than" added 2026-09-17: "more energy than in a solid" compares, it does not build on solids.
# Two further gaps: "than" also matches phrases that are not contrasts ("more
# than one flower"), so a genuine mention after it counts as contrastive; and
# the check reads mentions of the full name only -- a mention through the head
# word is never treated as contrastive.
_CONTRAST = re.compile(r"\b(while|whereas|unlike|but not|although|however|than)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def only_contrastive_mentions(name, text):
    """True when every mention of ``name`` in ``text`` is contrastive.

    Contrast is scoped to the clause, not the sentence. "Liquids and gases can
    flow, while solids normally do not" contrasts *solids* only -- liquids and
    gases are what it is about.
    """
    records = []
    for sentence in _SENTENCE.split(text or ""):
        marker = _CONTRAST.search(sentence)
        if not marker:
            if mentions(normalize(sentence), name):
                records.append(False)
            continue
        before, after = sentence[:marker.start()], sentence[marker.end():]
        if mentions(normalize(before), name):
            records.append(False)
        if mentions(normalize(after), name):
            records.append(True)
    return bool(records) and all(records)


def named_sections(concept):
    """The headings a concept sits under, as concept *names*.

    ``section_headings`` below returns the raw heading strings, for the
    cross-section flag. This returns them through ``heading_name``, which is how
    ``contained_in`` and ``resolve_concept`` read a heading, so a heading can be
    compared with a concept's name without the two disagreeing about numbering
    or punctuation.
    """
    members = getattr(concept, "members", None) or (concept,)
    return {
        name
        for name in (
            heading_name(getattr(member, "section_title", "") or "")
            for member in members
        )
        if name
    }


def presented_in_parallel(a, b, names):
    """True when the document presents ``a`` and ``b`` as coordinate siblings.

    Wang et al. (2016) read a textbook's section structure as prerequisite
    evidence, and ``contained_in`` already uses the downward reading: a passage
    under the "Matter" heading builds on Matter. This is the sideways reading of
    the same structure. Two passages under *one* heading, neither of which is
    what that heading names, are the author presenting parallel material --
    Solid, Liquid and Gas under "Matter"; Support, Protection and Movement under
    "The Skeletal System". A learner does not master Solid before Gas.

    This sideways reading is MAVIA's own design choice, not a cited method.

    The concept a shared heading *names* is the parent, not a sibling, so it is
    excluded: "Matter" under the "Matter" heading still precedes Solid.

    This keys on the documents' own headings, never on the words of a title --
    the same rule ``section_headings`` follows, and the reason the old sibling
    veto was removed: it keyed on the topic title's words, so renaming one
    object to "Diagram description for Solid" silently deleted 13 edges.
    """
    shared = named_sections(a) & named_sections(b)
    if not shared:
        return False
    return not (names.get(a.id) in shared or names.get(b.id) in shared)


def section_headings(concept):
    """The lesson headings a concept sits under, across every file teaching it.

    Taken from the documents' own structure (the heading each passage was
    extracted beneath), never from the words of a title, so renaming an object
    does not change it.
    """
    members = getattr(concept, "members", None) or (concept,)
    return {
        (member.section_title or "").strip().casefold()
        for member in members
        if (member.section_title or "").strip()
    }


def crosses_sections(a, b):
    """True when both concepts sit under headings and share none of them.

    Recorded on each link for the teacher; it does not change a verdict.
    A concept with no heading -- a comparison at the end, the opening
    definition -- is not treated as crossing anything.
    """
    left, right = section_headings(a), section_headings(b)
    return bool(left and right and not (left & right))


def _strong_evidence(a, b, names, heads):
    """R1, else R2, for "a before b": ``(rule, detail)`` or ``None``."""
    sentence = definition_dependency(a, b, names, heads)
    if sentence:
        return "definition", {"sentence": sentence}
    if contained_in(b, names.get(a.id)):
        return "containment", {"heading": names[a.id]}
    return None


def _trail_decisions(concepts, trail, names=None, heads=None):
    """Pending links from each concept an Examples or Summary section names.

    An Examples or Summary section has no name, so R1 and R2 cannot see it and
    R3 needs a name on both sides. What it can do is *use* concepts: "An ice
    cube is a solid" builds on Solid. The evidence is R3's own reading -- the
    share of the section's passages that name the concept -- with nothing in
    the other direction, since nothing can name a section that has no name. It
    is a suggestion only, like every R3 link, and never between two sections.
    """
    if names is None:
        names = concept_names(concepts)
        heads = head_words(names)
    decisions = []
    for dependent in trail:
        texts = [
            getattr(member, "content", "") or ""
            for member in (getattr(dependent, "members", None) or (dependent,))
        ]
        for prerequisite in concepts:
            if not names.get(prerequisite.id):
                continue
            naming = sum(1 for text in texts if says_plainly(text, prerequisite.id, names, heads))
            if not naming or naming / len(texts) <= PRD_THRESHOLD:
                continue
            decisions.append({
                "prerequisite": prerequisite,
                "dependent": dependent,
                "verdict": PENDING,
                "evidence": {"rule": "reference", "reference": {
                    "prw_forward": round(naming / len(texts), 6),
                    "prw_backward": 0.0,
                    "prd": round(naming / len(texts), 6),
                    "passages_forward": len(texts),
                    "passages_backward": 0,
                    "theta": PRD_THRESHOLD,
                }},
                "cross_section": crosses_sections(prerequisite, dependent),
            })
    return decisions


def decide_pairs(concepts, runtime_instance=None):
    """Every ordered pair the evidence accepts or sends to the teacher.

    ``runtime_instance`` is kept for callers and ignored: v4 calls no model.

    Rule precedence, not voting (spec Section 6). R1/R2 one way only is
    accepted; R1/R2 both ways is a conflict for the teacher; R3 alone is a
    suggestion, never between coordinate siblings. R3 never overrides R1/R2 --
    a parent's overview names its children, so R3 reads parent/child pairs
    backwards (measured: Matter/Solid on topic 62).
    """
    # Furniture names nothing, so nothing can depend on it. A lead section
    # (Introduction) takes no part; Examples and a Summary still *depend on*
    # the concepts their text names -- see ``trail_references``.
    trail = [concept for concept in concepts if structural_role(concept) in ("examples", "closing")]
    concepts = [concept for concept in concepts if structural_role(concept) is None]
    if not concepts:
        return []
    if len(concepts) < 2:
        return _trail_decisions(concepts, trail)

    names = concept_names(concepts)
    heads = head_words(names)
    references = passage_reference(concepts, names, heads)

    decisions = []
    for a in concepts:
        for b in concepts:
            if a.id == b.id:
                continue
            if names.get(a.id) and names.get(a.id) == names.get(b.id):
                continue

            forward = _strong_evidence(a, b, names, heads)
            backward = _strong_evidence(b, a, names, heads)
            reference = references.get((a.id, b.id))

            if forward and backward:
                verdict = PENDING
                evidence = {
                    "rule": "conflict",
                    "forward": {"rule": forward[0], **forward[1]},
                    "backward": {"rule": backward[0], **backward[1]},
                }
            elif forward:
                verdict = ACCEPTED
                evidence = {"rule": forward[0], forward[0]: forward[1]}
                opposing = references.get((b.id, a.id))
                if opposing and opposing["prd"] > PRD_THRESHOLD:
                    evidence["opposing_reference"] = {"prd": opposing["prd"]}
            elif backward:
                # The reverse pair records this link.
                continue
            elif (
                reference
                and reference["prd"] > PRD_THRESHOLD
                and not presented_in_parallel(a, b, names)
            ):
                verdict = PENDING
                evidence = {"rule": "reference", "reference": {**reference, "theta": PRD_THRESHOLD}}
            else:
                continue

            decisions.append({
                "prerequisite": a,
                "dependent": b,
                "verdict": verdict,
                "evidence": evidence,
                "cross_section": crosses_sections(a, b),
            })
    return decisions + _trail_decisions(concepts, trail, names, heads)
