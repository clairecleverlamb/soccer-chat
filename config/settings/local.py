"""Development settings.

``manage.py`` uses this module unless ``DJANGO_SETTINGS_MODULE`` is set.
"""

import os

os.environ.setdefault("DJANGO_DEBUG", "true")

from .base import *  # noqa: E402, F403
