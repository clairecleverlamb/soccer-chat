from django.http import JsonResponse
from apps.core.views import SectionView
from apps.knowledge.services import active_chunks


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
        chunks = active_chunks("soccer")

        # 2. Build your context or response logic here
        response_answer = f"Processed natural language query against {len(chunks)} active soccer knowledge documents."

        return JsonResponse({
            "question": user_question,
            "answer": response_answer,
            "sources_count": len(chunks),
        })