from django.test import TestCase
from django.urls import reverse


class FrameworkPageTests(TestCase):
    def test_home_lists_the_three_workflows(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Player lookup")
        self.assertContains(response, "Evaluate a player")
        self.assertContains(response, "Ask in chat")

    def test_section_pages_are_wired(self):
        for name in ("players:index", "evaluations:index", "chat:index"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
