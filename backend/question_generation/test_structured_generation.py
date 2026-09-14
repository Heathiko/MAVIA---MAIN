import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from .services import question_generator as qg
from .services.pipeline import QUESTION_DISTRIBUTION, thinking_order_counts


CONTENT = "A solid keeps a fixed shape. A liquid takes the shape of its container."


def _response(items):
    return json.dumps({"questions": items})


def _stream_response(post, data):
    post.return_value.iter_lines.return_value = [json.dumps(data).encode("utf-8")]
    post.return_value.raise_for_status.return_value = None


MCQ_ITEM = {
    "question": "What keeps a fixed shape?",
    "format": "MCQ",
    "choices": {"A": "A solid", "B": "A liquid", "C": "A gas", "D": "A plasma"},
    "correct_answer": "A",
    "explanation": "Solids hold their shape.",
}
TF_ITEM = {
    "question": "A liquid keeps a fixed shape.",
    "format": "TF",
    "correct_answer": "False",
    "explanation": "A liquid takes its container's shape.",
}


class StructuredOutputTests(SimpleTestCase):
    def test_ollama_call_sends_a_json_schema(self):
        with patch("question_generation.services.question_generator.requests.post") as post:
            _stream_response(post, {"response": _response([MCQ_ITEM]), "done": True})
            qg._ollama_generate("prompt", schema=qg.build_response_schema({"MCQ": 1}))

        sent = post.call_args.kwargs["json"]
        self.assertIn("format", sent)
        self.assertTrue(sent["stream"])
        self.assertTrue(post.call_args.kwargs["stream"])
        self.assertEqual(sent["format"]["type"], "object")
        self.assertIn("questions", sent["format"]["properties"])

    def test_temperature_is_not_lowered(self):
        # The schema constrains shape, not content. Dropping temperature would
        # cost question variety without preventing anything.
        with patch("question_generation.services.question_generator.requests.post") as post:
            _stream_response(post, {"response": _response([MCQ_ITEM]), "done": True})
            qg._ollama_generate("prompt", schema=qg.build_response_schema({"MCQ": 1}))

        self.assertEqual(post.call_args.kwargs["json"]["options"]["temperature"], 0.7)

    def test_ollama_metrics_are_reported_in_milliseconds(self):
        callback = Mock()
        with patch("question_generation.services.question_generator.requests.post") as post:
            _stream_response(post, {
                "response": _response([MCQ_ITEM]),
                "load_duration": 2_000_000,
                "prompt_eval_duration": 3_000_000,
                "eval_duration": 2_000_000_000,
                "total_duration": 2_100_000_000,
                "prompt_eval_count": 120,
                "eval_count": 40,
                "done": True,
            })
            qg._ollama_generate("prompt", on_metrics=callback)

        metrics = callback.call_args.args[0]
        self.assertEqual(metrics["load_ms"], 2.0)
        self.assertEqual(metrics["output_tokens"], 40)
        self.assertEqual(metrics["tokens_per_second"], 20.0)

    def test_warmup_loads_model_without_requesting_output(self):
        with patch.object(qg, "_warm_model", ""), patch.object(
            qg, "_warm_until", 0.0
        ), patch("question_generation.services.question_generator.requests.post") as post:
            post.return_value.json.return_value = {"response": "", "load_duration": 1}
            post.return_value.raise_for_status.return_value = None
            qg.warm_question_model()

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["prompt"], "")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["keep_alive"], "30m")

    def test_warmup_is_reused_while_model_keep_alive_is_active(self):
        with patch.object(qg, "_warm_model", ""), patch.object(
            qg, "_warm_until", 0.0
        ), patch("question_generation.services.question_generator.requests.post") as post:
            post.return_value.json.return_value = {"response": "", "load_duration": 1}
            post.return_value.raise_for_status.return_value = None
            first = qg.warm_question_model()
            second = qg.warm_question_model()

        self.assertFalse(first["warm_cache_hit"])
        self.assertTrue(second["warm_cache_hit"])
        post.assert_called_once()

    def test_schema_allows_both_formats(self):
        schema = qg.build_response_schema({"MCQ": 2, "TF": 1})
        item = schema["properties"]["questions"]["items"]
        self.assertEqual(set(item["properties"]["format"]["enum"]), {"MCQ", "TF"})
        # choices must be optional, or every true/false item violates the schema
        self.assertNotIn("choices", item.get("required", []))

    def test_single_format_schema_pins_the_enum(self):
        schema = qg.build_response_schema({"MCQ": 3})
        item = schema["properties"]["questions"]["items"]
        self.assertEqual(item["properties"]["format"]["enum"], ["MCQ"])


class MixedFormatValidationTests(SimpleTestCase):
    def test_validates_each_item_by_its_own_format(self):
        self.assertTrue(qg._validate_question(dict(MCQ_ITEM), "MCQ"))
        self.assertTrue(qg._validate_question(dict(TF_ITEM), "TF"))

    def test_true_false_item_is_not_rejected_for_lacking_choices(self):
        self.assertTrue(qg._validate_question(dict(TF_ITEM), "TF"))

    def test_mcq_without_choices_is_rejected(self):
        broken = {k: v for k, v in MCQ_ITEM.items() if k != "choices"}
        self.assertFalse(qg._validate_question(broken, "MCQ"))


class MixedGenerationTests(SimpleTestCase):
    @patch("question_generation.services.question_generator._ollama_generate")
    def test_one_call_returns_both_formats(self, generate):
        generate.return_value = _response([MCQ_ITEM, MCQ_ITEM, TF_ITEM])

        result = qg.generate_questions(CONTENT, "LOT", {"MCQ": 2, "TF": 1})

        self.assertEqual(generate.call_count, 1)
        self.assertEqual([q["format"] for q in result], ["MCQ", "MCQ", "TF"])

    @patch("question_generation.services.question_generator._ollama_generate")
    def test_item_format_wins_over_the_requested_split(self, generate):
        # The model returned a true/false item even though only MCQ was asked
        # for. It is still a usable question, so it is kept and labelled by
        # what it actually is rather than by what was requested.
        generate.return_value = _response([TF_ITEM])

        result = qg.generate_questions(CONTENT, "LOT", {"MCQ": 1})

        self.assertEqual(result[0]["format"], "TF")

    @patch("question_generation.services.question_generator._ollama_generate")
    def test_items_with_an_unusable_format_are_dropped(self, generate):
        generate.return_value = _response([{**MCQ_ITEM, "format": "ESSAY"}])

        result = qg.generate_questions(CONTENT, "LOT", {"MCQ": 1})

        self.assertEqual(result, [])

    @patch("question_generation.services.question_generator._ollama_generate")
    def test_requested_split_reaches_the_prompt(self, generate):
        generate.return_value = _response([MCQ_ITEM])

        qg.generate_questions(CONTENT, "LOT", {"MCQ": 2, "TF": 1})

        prompt = generate.call_args.args[0]
        self.assertIn("2", prompt)
        self.assertIn("MCQ", prompt)
        self.assertIn("TF", prompt)


class DistributionConfigTests(SimpleTestCase):
    def test_lot_asks_for_both_formats_in_one_call(self):
        self.assertEqual(set(QUESTION_DISTRIBUTION["LOT"]["format_split"]), {"MCQ", "TF"})

    def test_hot_is_multiple_choice_only(self):
        self.assertEqual(set(QUESTION_DISTRIBUTION["HOT"]["format_split"]), {"MCQ"})

    def test_counts_default_to_three(self):
        self.assertEqual(QUESTION_DISTRIBUTION["LOT"]["count"], 3)
        self.assertEqual(QUESTION_DISTRIBUTION["HOT"]["count"], 3)

    def test_split_sums_to_the_target_count(self):
        for order, config in QUESTION_DISTRIBUTION.items():
            self.assertEqual(
                sum(config["format_split"].values()), config["count"], msg=order
            )

    def test_default_generation_does_not_pad_the_question_count(self):
        from .services.pipeline import OVERGENERATION_FACTOR

        self.assertEqual(OVERGENERATION_FACTOR, 1.0)

    def test_fingerprint_changes_with_content_or_model(self):
        first = qg.question_bank_fingerprint(CONTENT, QUESTION_DISTRIBUTION)
        changed_content = qg.question_bank_fingerprint(CONTENT + " More.", QUESTION_DISTRIBUTION)
        with override_settings(QUESTION_LLM_MODEL="another-model"):
            changed_model = qg.question_bank_fingerprint(CONTENT, QUESTION_DISTRIBUTION)

        self.assertNotEqual(first, changed_content)
        self.assertNotEqual(first, changed_model)

    @override_settings(QUESTION_COUNT_LOT=4, QUESTION_COUNT_HOT=2)
    def test_counts_are_configurable(self):
        counts = thinking_order_counts()
        self.assertEqual(counts["LOT"], 4)
        self.assertEqual(counts["HOT"], 2)
