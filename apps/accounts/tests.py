from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class UserModelTests(TestCase):
    def test_project_uses_the_custom_user_model(self):
        user = get_user_model().objects.create_user(
            "manager",
            "manager@example.com",
            "a-long-password",
        )

        self.assertEqual(user.get_username(), "manager")
        self.assertEqual(get_user_model()._meta.label, "accounts.User")


class AuthFlowTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log in")

    def test_login_then_logout(self):
        get_user_model().objects.create_user("manager", password="a-long-password")

        login_response = self.client.post(
            reverse("login"),
            {"username": "manager", "password": "a-long-password"},
        )
        self.assertRedirects(login_response, reverse("home"))

        home = self.client.get(reverse("home"))
        self.assertContains(home, "manager")

        logout_response = self.client.post(reverse("logout"))
        self.assertRedirects(logout_response, reverse("home"))
