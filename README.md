# Soccer Chat

A Django app for football managers and analysts. The chatbot retrieves published soccer knowledge, classifies questions into factual, explanation, or creative intents, and responds using the selected behavior.

Player lookup and evaluation are still to build. A developer can define and update the knowledge dataset the chatbot retrieves from.

## Apps

| App | Role |
| --- | --- |
| `apps.accounts` | Custom user model and login. Add profile fields here. |
| `apps.players` | Player identity and stored stats for lookup. |
| `apps.evaluations` | Score a player from stats that are typed in, without requiring a saved player. |
| `apps.knowledge` | RAG dataset: source documents and the published release the chatbot reads. |
| `apps.chat` | Intent-aware chatbot using the active knowledge release. |
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

## Knowledge dataset

Documents live in a JSONL file, one JSON object per line, with `source_id`, `title`, `body`, and optional `metadata`. `source_id` is the stable key: import the same id again to update that document.

```bash
python manage.py load_knowledge data/soccer.jsonl --dataset soccer --name "Soccer knowledge" --replace
```

`--replace` removes documents that are no longer in the file, then publishes. A bad file publishes nothing. Admin at `/admin/` can inspect documents and publish a dataset after a one-off edit. Saving a document in admin stores a draft; chatbot knowledge changes when that dataset is published.

`apps.knowledge.services.active_chunks("soccer")` returns the chunks from the active release, which the chat app uses for retrieval.

## Chat prompts and accuracy checks

Each chat request is classified at runtime as a factual lookup, explanation, or creative response. The selected intent changes the system instruction and the grounded response style. The app does not currently call an external language model; it renders a concise answer from retrieved source text so responses stay grounded.

The known-question regression tests check intent selection, expected facts, and source retrieval against the sample knowledge dataset:

```bash
python manage.py test apps.chat.tests
```

For a quick demo, publish the sample dataset and start the app:

```bash
python manage.py load_knowledge data/soccer.jsonl --dataset soccer --replace
python manage.py runserver
```

Open the chat page and try:

- `Where does Rodri receive in 2024-25?` — factual lookup
- `Explain what makes a pressing forward effective.` — explanation
- `Write a scout's note about Mbappe.` — creative response

Each answer displays its detected intent and retrieved source. To show the validation to a TA, run `python manage.py test apps.chat.tests` and point out the expected fact/source assertions.

## Tests

```bash
python manage.py test
```

## Settings

`manage.py` loads `config.settings.local`, which reads `config.settings.base`. Set `DJANGO_SETTINGS_MODULE` when you add another environment.
