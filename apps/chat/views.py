from django.http import JsonResponse
from apps.core.views import SectionView
from apps.knowledge.services import active_chunks
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
        "This is where a manager will ask for a player's stats or an evaluation "
        "in one conversation. The chatbot is the next story to build here."
    )

    def post(self, request, *args, **kwargs):
        user_question = request.POST.get("question", "").strip()

        if not user_question:
            return JsonResponse({"error": "No question provided."}, status=400)

        # 1. Pull active soccer knowledge chunks (fulfilling RAG context requirement)
        #chunks = active_chunks("soccer")


        # 2. Build your context or response logic here
        #response_answer = f"Processed natural language query against {len(chunks)} active soccer knowledge documents."
        print(active_chunks("soccer").count())
        qs = active_chunks("soccer")
        hits = top_chunks(user_question, qs, k=4)
        sources = [serialize_source(c, s) for c, s in hits]

        if hits:
            answer = f"Processed natural language query against {len(sources)} active soccer knowledge documents." # LLM FUNCTION -> build_answer(user_question, [c for c, _ in hits])  # LLM or template
        else:
            answer = "I couldn't find anything in the soccer knowledge base about that."


        return JsonResponse({
            "question": user_question,
            "answer": answer,
            "sources" : sources,
            "sources_count": len(sources),

        })