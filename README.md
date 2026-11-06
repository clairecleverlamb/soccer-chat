# Soccer Chat

A Django app for football managers and analysts. It will look up stored player stats and evaluate a player from stats you enter, including through a chatbot.

This repository is the project framework. Player data, evaluation logic, and the chatbot are not built yet.

## Apps

| App | Role |
| --- | --- |
| `apps.accounts` | Custom user model and login. Add profile fields here. |
| `apps.players` | Player identity and stored stats for lookup. |
| `apps.evaluations` | Score a player from stats that are typed in, without requiring a saved player. |
| `apps.chat` | Conversation that will call lookup and evaluation. |
| `apps.core` | Home page and the shared page shell. |

`accounts.User` is the auth user (`AUTH_USER_MODEL`). Add fields on that model before the first production migration if you need them; changing the user model later is painful.

## Requirements

- Python 3.13 (Django 5.2). The default `python3` on this machine may be newer than Django supports. A virtualenv is already at `.venv` if you are on the machine where this project was created.

## Run locally

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/

Create an admin user when you want to sign in:

```bash
python manage.py createsuperuser
```

Admin is at http://127.0.0.1:8000/admin/

If you are setting the environment up on a new machine:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Optional environment variables live in `.env` (see `.env.example`). Local settings default to debug mode and SQLite.

## Tests

```bash
python manage.py test
```

## Settings

`manage.py` loads `config.settings.local`, which reads `config.settings.base`. Set `DJANGO_SETTINGS_MODULE` when you add another environment.
