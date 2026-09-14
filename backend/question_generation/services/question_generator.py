import hashlib
import json
import logging
import re
import threading
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

QUESTION_GENERATOR_VERSION = 2
QUESTION_TEMPERATURE = 0.7
QUESTION_NUM_PREDICT = 2048
_warm_lock = threading.Lock()
_warm_model = ""
_warm_until = 0.0


def _mark_question_model_warm():
    global _warm_model, _warm_until
    with _warm_lock:
        _warm_model = settings.QUESTION_LLM_MODEL
        # Slightly shorter than the default Ollama keep-alive so the local
        # state never intentionally outlives the server-side residency window.
        _warm_until = time.monotonic() + 25 * 60

# ── Prompt templates ──
# Intentionally SHORT to minimize token usage.
# Keyed by thinking order, and deliberately phrased in terms of the cognitive
# work each question demands rather than how "hard" it is. The LLM is never
# told about Bloom's taxonomy — the classifier assigns the actual level after
# generation, and these prompts only steer the model toward the right region.
#
#   LOT covers remember / understand / apply
#   HOT covers analyze / evaluate
#
# There are no "strict" retry variants any more. LOT and HOT are wide enough
# that ordinary prompt drift stays inside the intended bucket, so the pipeline
# no longer regenerates to correct it.

PROMPT_TEMPLATES = {
    "LOT": (
        "You are a quiz maker. Given the content below, generate {count} questions.\n"
        "Each question must be answerable DIRECTLY from the content. Ask the learner to "
        "recall a stated fact, show they understand what a concept means, or use a stated "
        "rule in a straightforward case.\n"
        "Do NOT ask the learner to compare two things, weigh trade-offs, judge which "
        "option is better, or justify a choice.\n\n"
        "{examples}\n\n"
        "{format_request}\n\n"
        "Content:\n{content}\n\n"
        "{format_instructions}\n\n"
        "Respond ONLY with valid JSON, no other text. Every question object must\n"
        "carry a \"format\" field saying which kind it is. Use this exact structure:\n"
        '{{"questions": [{question_schema}]}}'
    ),
    "HOT": (
        "You are a quiz maker. Given the content below, generate {count} questions.\n"
        "Each question must require reasoning BEYOND recall or direct application. Ask the "
        "learner to break an idea into parts, compare or differentiate two concepts, work "
        "out a cause-and-effect relationship, or judge and justify which option is more "
        "appropriate and why.\n"
        "Do NOT ask for a fact that is stated word-for-word in the content.\n"
        "The question must still have ONE defensible correct answer.\n\n"
        "{examples}\n\n"
        "{format_request}\n\n"
        "Content:\n{content}\n\n"
        "{format_instructions}\n\n"
        "Respond ONLY with valid JSON, no other text. Every question object must\n"
        "carry a \"format\" field saying which kind it is. Use this exact structure:\n"
        '{{"questions": [{question_schema}]}}'
    ),
}

# ── Few-shot style examples — small local models drift far less when shown
# the target cognitive level instead of only being told about it ──
FEW_SHOT_EXAMPLES = {
    "LOT": (
        "Examples of the style (different topic — do NOT reuse these):\n"
        "- What is evaporation?\n"
        "- Why does a puddle shrink on a sunny day?\n"
        "- A pot of water is left boiling. Which process is turning the water into steam?"
    ),
    "HOT": (
        "Examples of the style (different topic — do NOT reuse these):\n"
        "- How does evaporation differ from condensation in the water cycle?\n"
        "- A farmer waters crops daily but they still die. Which explanation best "
        "justifies why too much water can harm plants?\n"
        "- Which process matters more for forming clouds: evaporation or condensation? Why?"
    ),
}

FORMAT_INSTRUCTIONS = {
    "MCQ": (
        "Each question must have exactly 4 choices (A, B, C, D). "
        "Only one choice is correct. Distractors should be plausible."
    ),
    "TF": (
        "Each question must be a clear statement that is either True or False. "
        "Do not make it obvious. Include a brief explanation for the correct answer."
    ),
}

QUESTION_SCHEMA = {
    "MCQ": (
        '{"question": "...", "format": "MCQ", '
        '"choices": {"A": "...", "B": "...", "C": "...", "D": "..."}, '
        '"correct_answer": "A or B or C or D", "explanation": "brief explanation"}'
    ),
    "TF": (
        '{"question": "statement here", "format": "TF", '
        '"correct_answer": "True or False", "explanation": "brief explanation"}'
    ),
}

# Formats the pipeline can actually assess. An item claiming anything else is
# dropped rather than coerced -- guessing at what the model meant would put an
# ungradeable question into the bank.
SUPPORTED_FORMATS = ("MCQ", "TF")


def question_bank_fingerprint(content, distribution):
    """Identify the exact source and generation contract for a question bank."""
    payload = {
        "version": QUESTION_GENERATOR_VERSION,
        "content": content,
        "model": settings.QUESTION_LLM_MODEL,
        "distribution": distribution,
        "prompts": PROMPT_TEMPLATES,
        "examples": FEW_SHOT_EXAMPLES,
        "format_instructions": FORMAT_INSTRUCTIONS,
        "schemas": QUESTION_SCHEMA,
        "temperature": QUESTION_TEMPERATURE,
        "num_predict": QUESTION_NUM_PREDICT,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ollama_metrics(data):
    """Convert Ollama nanosecond timings into trace-friendly values."""
    def milliseconds(name):
        value = data.get(name)
        return round(value / 1_000_000, 1) if isinstance(value, (int, float)) else None

    eval_count = data.get("eval_count") or 0
    eval_duration = data.get("eval_duration") or 0
    tokens_per_second = (
        round(eval_count / (eval_duration / 1_000_000_000), 2)
        if eval_count and eval_duration else None
    )
    return {
        "load_ms": milliseconds("load_duration"),
        "prompt_eval_ms": milliseconds("prompt_eval_duration"),
        "eval_ms": milliseconds("eval_duration"),
        "total_ms": milliseconds("total_duration"),
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
        "tokens_per_second": tokens_per_second,
        "model": settings.QUESTION_LLM_MODEL,
    }


def build_response_schema(format_split):
    """JSON schema handed to Ollama so the response cannot be malformed.

    Constraining the shape at decode time is what makes a single call able to
    return a mix of multiple-choice and true/false questions: the parser no
    longer has to gamble on the model closing its JSON correctly.

    ``choices`` is deliberately optional -- a true/false item has none, and
    requiring it would make every one of them violate the schema.
    """
    formats = [fmt for fmt in SUPPORTED_FORMATS if format_split.get(fmt)]
    letter = {"type": "string"}
    return {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "format": {"type": "string", "enum": formats or list(SUPPORTED_FORMATS)},
                        "choices": {
                            "type": "object",
                            "properties": {k: letter for k in ("A", "B", "C", "D")},
                        },
                        "correct_answer": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["question", "format", "correct_answer"],
                },
            },
        },
        "required": ["questions"],
    }


def _format_request(format_split):
    """The human-readable half of the same instruction the schema encodes."""
    parts = [
        f"{count} {fmt}" for fmt, count in format_split.items() if count
    ]
    if len(parts) == 1:
        return f"Format: {parts[0]} question(s)."
    return "Formats: " + ", ".join(parts) + " question(s), in that mix."


def _build_prompt(content, thinking_order, format_split):
    formats = [fmt for fmt in SUPPORTED_FORMATS if format_split.get(fmt)]
    return PROMPT_TEMPLATES[thinking_order].format(
        count=sum(format_split.values()),
        content=content,
        format_request=_format_request(format_split),
        format_instructions="\n".join(FORMAT_INSTRUCTIONS[fmt] for fmt in formats),
        question_schema=", ".join(QUESTION_SCHEMA[fmt] for fmt in formats),
        examples=FEW_SHOT_EXAMPLES[thinking_order],
    )


def _validate_question(q, format_type):
    """Structural validation — reject hallucinated answers before they enter
    the bank (e.g. an MCQ whose correct_answer is 'A, B, C and D').
    Normalizes correct_answer in place when it can be recovered."""
    if "question" not in q or "correct_answer" not in q:
        return False

    answer = str(q["correct_answer"]).strip()

    if format_type == "MCQ":
        choices = q.get("choices")
        if not isinstance(choices, dict) or not choices:
            return False
        if answer in choices:
            q["correct_answer"] = answer
            return True
        # LLM sometimes answers with the choice text instead of the letter
        for letter, text in choices.items():
            if str(text).strip().lower() == answer.lower():
                q["correct_answer"] = letter
                return True
        return False

    # TF
    if answer.lower() in ("true", "false"):
        q["correct_answer"] = answer.capitalize()
        return True
    return False


def _extract_question_objects(text):
    """Recover individual question objects from text that isn't valid JSON
    as a whole — e.g. the response got truncated by the token limit mid
    object, or the model dropped a comma between two objects. Questions sit
    nested inside {"questions": [...]}, so this records every balanced
    {...} span at any depth (via a stack, honoring quoted strings) and
    parses each independently — a truncated or comma-less object simply
    fails to close or fails to parse, and is skipped without sinking the
    objects around it."""
    spans = []
    stack = []
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            stack.append(i)
        elif ch == "}":
            if stack:
                start = stack.pop()
                spans.append(text[start:i + 1])

    recovered = []
    for candidate in spans:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "question" in parsed and "correct_answer" in parsed:
            recovered.append(parsed)
    return recovered


def _parse_llm_response(response_text):
    """
    Extract JSON from LLM response.
    Local models are messy — they sometimes wrap JSON in markdown
    code blocks or add preamble text.
    """
    text = response_text.strip()

    # strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # find the outermost JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in LLM response: {text[:200]}")

    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError:
        recovered = _extract_question_objects(match.group())
        if not recovered:
            raise
        print(f"  Recovered {len(recovered)} question(s) from malformed JSON response")
        return recovered

    if "questions" in parsed:
        return parsed["questions"]
    elif isinstance(parsed, list):
        return parsed
    else:
        return [parsed]


def _ollama_generate(prompt, schema=None, on_metrics=None):
    """Call Ollama over HTTP using the project's existing settings.

    ``schema`` constrains the reply at decode time. Temperature stays where it
    was: the schema governs shape, not wording, so lowering it would cost
    question variety without preventing a single malformed response.
    """
    payload = {
        "model": settings.QUESTION_LLM_MODEL,
        "prompt": prompt,
        # Chunks keep slow CPU generation from looking like an idle HTTP
        # connection. They are joined before parsing, preserving the API.
        "stream": True,
        "keep_alive": getattr(
            settings, "QUESTION_LLM_KEEP_ALIVE", settings.OLLAMA_KEEP_ALIVE
        ),
        "options": {
            "temperature": QUESTION_TEMPERATURE,
            # generous ceiling — a batch of MCQs (4 choices + explanation
            # each) can run past 1000 tokens and get cut off mid-JSON
            "num_predict": QUESTION_NUM_PREDICT,
        },
    }
    if schema is not None:
        payload["format"] = schema
    response = requests.post(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=settings.OLLAMA_TIMEOUT,
        stream=True,
    )
    response.raise_for_status()
    response_parts = []
    data = None
    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        chunk = json.loads(raw_line)
        if chunk.get("error"):
            raise RuntimeError(str(chunk["error"]))
        response_parts.append(chunk.get("response") or "")
        data = chunk
    if data is None:
        raise ValueError("Ollama returned an empty streaming response.")
    data["response"] = "".join(response_parts)
    _mark_question_model_warm()
    if on_metrics:
        on_metrics(_ollama_metrics(data))
    return data["response"]


def warm_question_model(on_metrics=None):
    """Load the configured question model without generating lesson content."""
    with _warm_lock:
        already_warm = (
            _warm_model == settings.QUESTION_LLM_MODEL
            and time.monotonic() < _warm_until
        )
    if already_warm:
        metrics = {
            "load_ms": 0.0,
            "prompt_eval_ms": 0.0,
            "eval_ms": 0.0,
            "total_ms": 0.0,
            "prompt_tokens": 0,
            "output_tokens": 0,
            "tokens_per_second": None,
            "model": settings.QUESTION_LLM_MODEL,
            "warm_cache_hit": True,
        }
        if on_metrics:
            on_metrics(metrics)
        return metrics

    payload = {
        "model": settings.QUESTION_LLM_MODEL,
        "prompt": "",
        "stream": False,
        "keep_alive": getattr(
            settings, "QUESTION_LLM_KEEP_ALIVE", settings.OLLAMA_KEEP_ALIVE
        ),
    }
    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=settings.OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        metrics = _ollama_metrics(response.json())
        metrics["warm_cache_hit"] = False
        _mark_question_model_warm()
        if on_metrics:
            on_metrics(metrics)
        return metrics
    except (requests.RequestException, ValueError, KeyError) as exc:
        # Warming is an optimization, never a prerequisite. The real request
        # remains authoritative and will surface its own failure normally.
        logger.warning("Question model warm-up failed: %s", exc)
        return None


def generate_questions(
    content,
    thinking_order,
    format_split,
    max_retries=3,
    on_metrics=None,
):
    """
    Generate one thinking order's questions in a single LLM call.

    The returned questions carry no classification — the prompt only steers
    toward a thinking order, it does not decide one. The Bloom classifier
    assigns the authoritative label later, in the post-generation pass.

    Args:
        content:        text content to generate questions from
        thinking_order: "LOT" or "HOT" — which prompt to steer with
        format_split:   {"MCQ": 2, "TF": 1} — how many of each kind to ask for
        max_retries:    retry on JSON parse failures

    Returns:
        list of question dicts, each labelled with the format it actually is
    """
    prompt = _build_prompt(content, thinking_order, format_split)
    schema = build_response_schema(format_split)

    for attempt in range(max_retries):
        try:
            raw_text = _ollama_generate(prompt, schema=schema, on_metrics=on_metrics)
            questions = _parse_llm_response(raw_text)

            validated = []
            for q in questions:
                # The item's own format decides how it is validated. Asking for
                # two MCQs and being handed a usable true/false question is not
                # a failure -- the split is a request, not a contract.
                fmt = str(q.get("format") or "").upper()
                if fmt not in SUPPORTED_FORMATS:
                    continue
                if not _validate_question(q, fmt):
                    continue
                q["format"] = fmt
                validated.append(q)

            if validated:
                return validated

        except (json.JSONDecodeError, ValueError) as e:
            print(f"  Attempt {attempt + 1}/{max_retries} failed: {e}")
            continue

    print(f"  WARNING: Failed to generate after {max_retries} attempts")
    return []
