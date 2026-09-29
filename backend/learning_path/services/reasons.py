"""One plain sentence explaining a prerequisite link, for the review screen.

Built from the evidence ``criteria.decide_pairs`` stores on each derived row,
so the screen never needs to know the rules. A row with no evidence was made
by the teacher.
"""


def link_reason(evidence, prerequisite_title, dependent_title):
    a, b = prerequisite_title, dependent_title
    evidence = evidence or {}
    rule = evidence.get("rule")

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
