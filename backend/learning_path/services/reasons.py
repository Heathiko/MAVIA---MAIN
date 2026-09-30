"""One plain sentence explaining a prerequisite link, for the review screen.

Built from the evidence ``criteria.decide_pairs`` stores on each derived row;
rows from older versions (v4, v5) keep their wording until re-derived. A row
with no evidence was made by the teacher.
"""


_CLUE_NAMES = {
    "name": "the name", "terms": "the terms", "meaning": "the meaning",
    "heading": "the headings", "order": "the files' order",
}


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
    if votes.get("heading") == 1:
        parts.append(f"{b} sits under a heading naming {a}.")
    if votes.get("order") == 1:
        order = records.get("order") or {}
        parts.append(f"{order.get('agree')} of {order.get('pdfs')} files teach {a} first.")
    against = [_CLUE_NAMES[clue] for clue in _CLUE_NAMES if votes.get(clue) == -1]
    if against:
        parts.append(f"Against it: {', '.join(against)}.")
    if not any(votes.get(clue) for clue in ("name", "terms", "meaning")):
        parts.append("The text says nothing either way.")
    if evidence.get("disagreement"):
        parts.append("The text reads the other way; this follows how the files are organised.")
    if evidence.get("parallel"):
        parts.append(f"The files present {a} and {b} side by side under one heading.")
    if evidence.get("semantic") is False:
        parts.append("The meaning check was unavailable.")
    if evidence.get("confidence") is not None:
        parts.append(f"Confidence {evidence['confidence']:.2f}.")
    return " ".join(parts)


def _course_reason(evidence, a, b):
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
    if evidence.get("contradicts_outline"):
        parts.append(f"This contradicts your outline: {a}'s topic comes later.")
    else:
        parts.append("This follows your outline.")
    if evidence.get("semantic") is False:
        parts.append("The meaning check was unavailable.")
    if evidence.get("confidence") is not None:
        parts.append(f"Confidence {evidence['confidence']:.2f}.")
    return " ".join(parts)


_CONTRADICTION_SENTENCES = {
    "figure": "One of them is a figure, so its place in the file does not give the order.",
    "no_shared_pdf": "They come from different files, so their order is a guess.",
    "pdfs_disagree": "The files put them in different orders.",
}


def _reference_order_reason(evidence, a, b):
    """``records`` are oriented prerequisite-first, so every sentence reads from them.

    The stored ``contradictions`` name the PDF's earlier and later concept, which
    is the dependent when a figure or the names reversed the order; only the
    orientation-free ones (figure, files) are read from that list.
    """
    votes = evidence.get("votes") or {}
    records = evidence.get("records") or {}
    names = records.get("name") or {}
    terms = records.get("terms") or {}
    contradictions = evidence.get("contradictions") or []
    parts = []
    if votes.get("heading") == 1:
        parts.append(f"{b} sits under a heading naming {a}.")
    if names.get("use", 0) > 0:
        parts.append(f"{b} names {a}.")
    if terms.get("use", 0) > 0:
        owned = terms.get("owned") or []
        listed = f" ({', '.join(owned[:3])})" if owned else ""
        parts.append(f"{b} uses terms {a} explains{listed}.")
    source = evidence.get("direction_from")
    if source == "pdf_order":
        parts.append(f"{a} comes first in the lesson.")
    elif source == "merged_order":
        parts.append(f"{a} comes first in the topic's combined order.")
    elif source == "figure":
        parts.append(f"The figure's description refers to {a}.")
    elif source == "name":
        parts.append(f"The names put {a} first; the files do not settle the order.")
    elif source == "pdf_agreement":
        order = records.get("order") or {}
        parts.append(f"{order.get('agree')} of {order.get('pdfs')} files teach {a} first; the text says nothing either way.")
    if names.get("use_back", 0) > names.get("use", 0):
        parts.append(f"But {a}'s text names {b} more than the reverse.")
    refers = names.get("use", 0) > 0 or terms.get("use", 0) > 0
    refers_back = names.get("use_back", 0) > 0 or terms.get("use_back", 0) > 0
    if refers_back and not refers and votes.get("heading") != 1:
        parts.append(f"But only {a}'s text refers to {b}.")
    parts.extend(_CONTRADICTION_SENTENCES[key] for key in _CONTRADICTION_SENTENCES if key in contradictions)
    return " ".join(parts)


def link_reason(evidence, prerequisite_title, dependent_title):
    a, b = prerequisite_title, dependent_title
    evidence = evidence or {}
    rule = evidence.get("rule")

    if rule == "course":
        return _course_reason(evidence, a, b)
    if rule == "reference-order":
        return _reference_order_reason(evidence, a, b)
    if rule == "fusion":
        return _fused_reason(evidence, a, b)
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
