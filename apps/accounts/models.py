from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Person using Soccer Chat to look up and evaluate players.

    Extra profile fields, such as club or role, can be added on this model
    when an accounts story needs them. Swap this out later only with a migration.
    """
