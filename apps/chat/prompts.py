import re
from dataclasses import dataclass
from enum import Enum

from apps.knowledge.models import Chunk


class Intent(str, Enum):
    FACTUAL_LOOKUP = "factual lookup"
    EXPLANATION = "explanation"
    CREATIVE_RESPONSE = "creative response"


@dataclass(frozen=True)
class ChatPrompt:
    intent: Intent
    system_message: str
    user_message: str
    context: tuple[str, ...]


_CREATIVE_QUESTION = re.compile(
    r"\b(write|create|invent|imagine|story|poem|creative|scout'?s note)\b",
    re.IGNORECASE,
)
_EXPLANATION_QUESTION = re.compile(
    r"\b(explain|why|how|meaning|compare|difference|analy[sz]e|describe)\b"
    r"|\bwhat does\b",
    re.IGNORECASE,
)

_INSTRUCTIONS = {
    Intent.FACTUAL_LOOKUP: (
        "Answer the factual question directly and concisely using only the supplied "
        "soccer sources. If they do not contain the answer, say so."
    ),
    Intent.EXPLANATION: (
        "Explain the soccer concept in clear, accessible language using only the "
        "supplied sources. Do not add unsupported facts."
    ),
    Intent.CREATIVE_RESPONSE: (
        "Respond in the requested creative style while keeping every soccer claim "
        "grounded in the supplied sources. Do not invent player facts."
    ),
}


def classify_intent(question: str) -> Intent:
    """Choose a response intent from the wording of a question."""
    if _CREATIVE_QUESTION.search(question):
        return Intent.CREATIVE_RESPONSE
    if _EXPLANATION_QUESTION.search(question):
        return Intent.EXPLANATION
    return Intent.FACTUAL_LOOKUP


def build_prompt(question: str, hits: list[tuple[Chunk, int]]) -> ChatPrompt:
    """Construct intent-specific instructions and retrieved context at runtime."""
    intent = classify_intent(question)
    sources = tuple(chunk.text for chunk, _score in hits)
    context = "\n\n".join(
        f"Source {index} ({chunk.title}): {chunk.text}"
        for index, (chunk, _score) in enumerate(hits, start=1)
    )
    if not context:
        context = "No relevant soccer sources were found."

    return ChatPrompt(
        intent=intent,
        system_message=_INSTRUCTIONS[intent],
        user_message=f"Question: {question}\n\nRetrieved context:\n{context}",
        context=sources,
    )


def render_grounded_answer(prompt: ChatPrompt) -> str:
    """Render a source-grounded response in the style selected for this question."""
    if not prompt.context:
        return "I couldn't find anything in the soccer knowledge base about that."

    source_text = prompt.context[0]
    if prompt.intent is Intent.EXPLANATION:
        return f"In simple terms: {source_text}"
    if prompt.intent is Intent.CREATIVE_RESPONSE:
        return f"Scout's note: {source_text}"
    return source_text
