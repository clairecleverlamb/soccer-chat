from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.knowledge.services import active_chunks

from .prompts import Intent, build_prompt, classify_intent


class PromptIntentTests(TestCase):
    def test_questions_are_classified_by_intent(self):
        examples = (
            ("Where does Rodri receive the ball?", Intent.FACTUAL_LOOKUP),
            ("Explain what makes a pressing forward effective.", Intent.EXPLANATION),
            ("Write a scout's note about Mbappe.", Intent.CREATIVE_RESPONSE),
        )

        for question, expected_intent in examples:
            with self.subTest(question=question):
                self.assertEqual(classify_intent(question), expected_intent)

    def test_prompt_instructions_change_with_intent(self):
        factual = build_prompt("Where does Rodri play?", [])
        explanatory = build_prompt("Explain Rodri's role.", [])
        creative = build_prompt("Write a story about Rodri.", [])

        self.assertNotEqual(factual.system_message, explanatory.system_message)
        self.assertNotEqual(explanatory.system_message, creative.system_message)
        self.assertEqual(factual.intent, Intent.FACTUAL_LOOKUP)


class KnownQuestionAccuracyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "load_knowledge",
            str(settings.BASE_DIR / "data" / "soccer.jsonl"),
            "--dataset",
            "soccer",
            "--replace",
        )

    def test_known_questions_return_expected_facts_and_intents(self):
        known_questions = (
            {
                "question": "Where does Rodri receive in 2024-25?",
                "intent": "factual lookup",
                "source_id": "player:rodri:2024-25",
                "answer_prefix": "Rodri is a single pivot",
                "expected_text": "receives between the lines",
            },
            {
                "question": "Explain what makes a pressing forward effective.",
                "intent": "explanation",
                "source_id": "guide:pressing-forward",
                "answer_prefix": "In simple terms:",
                "expected_text": "pressures lead to turnovers",
            },
            {
                "question": "Write a scout's note about Mbappe.",
                "intent": "creative response",
                "source_id": "player:mbappe:2024-26",
                "answer_prefix": "Scout's note:",
                "expected_text": "attacks space behind a high line",
            },
        )

        for case in known_questions:
            with self.subTest(question=case["question"]):
                response = self.client.post(
                    reverse("chat:index"),
                    {"question": case["question"]},
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["intent"], case["intent"])
                self.assertTrue(payload["answer"].startswith(case["answer_prefix"]))
                self.assertIn(case["expected_text"], payload["answer"].lower())
                self.assertIn(
                    case["source_id"],
                    {source["source_id"] for source in payload["sources"]},
                )

    def test_prompt_contains_retrieved_knowledge(self):
        hits = [
            (active_chunks("soccer").get(source_id="player:rodri:2024-25"), 3)
        ]

        prompt = build_prompt("Where does Rodri receive?", hits)

        self.assertIn("receives between the lines", prompt.user_message)
