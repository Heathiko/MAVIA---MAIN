"""One plain sentence explaining a prerequisite link, for the review screen.

Built from the evidence ``criteria.decide_pairs`` stores on each derived row;
v4 rows keep their older wording until re-derived. A row with no evidence was made
by the teacher.
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


def link_reason(evidence, prerequisite_title, dependent_title):
    a, b = prerequisite_title, dependent_title
    evidence = evidence or {}
    rule = evidence.get("rule")

    if rule == "course":
        return _course_reason(evidence, a, b)
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
