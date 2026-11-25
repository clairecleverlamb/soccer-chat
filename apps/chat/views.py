from django.http import JsonResponse
from apps.core.views import SectionView
from apps.knowledge.services import active_chunks
from .prompts import build_prompt, render_grounded_answer
from .retrieval import top_chunks


def serialize_source(chunk, score):
    release = chunk.release
    return {
        "chunk_id": chunk.pk,
        "source_id": chunk.source_id,   
        "title": chunk.title,
        "ordinal": chunk.ordinal,
        "snippet": chunk.text,
        "metadata": chunk.metadata,
        "score": score,
        "release_id": release.pk,
        "published_at": release.published_at.isoformat(),
    }


class ChatView(SectionView):
    template_name = "chat/index.html"
    title = "Ask in chat"
    summary = (
        "Ask about player stats and soccer concepts using the published soccer "
        "knowledge base."
    )

    def post(self, request, *args, **kwargs):
        user_question = request.POST.get("question", "").strip()

        if not user_question:
            return JsonResponse({"error": "No question provided."}, status=400)

        hits = top_chunks(user_question, active_chunks("soccer"), k=4)
        sources = [serialize_source(c, s) for c, s in hits]
        prompt = build_prompt(user_question, hits)

        return JsonResponse({
            "question": user_question,
            "answer": render_grounded_answer(prompt),
            "intent": prompt.intent.value,
            "sources": sources,
            "sources_count": len(sources),
        })