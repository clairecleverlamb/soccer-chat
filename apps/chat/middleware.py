import logging
from time import perf_counter

from django.db import DatabaseError

from .models import ChatRequest


logger = logging.getLogger(__name__)


class ChatMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = perf_counter()
        response = self.get_response(request)
        elapsed = (perf_counter() - started) * 1000

        match = request.resolver_match
        is_chat_request = (
            request.method == "POST"
            and match is not None
            and match.view_name == "chat:index"
        )

        if is_chat_request:
            error_type = getattr(request, "_chat_error_type", "")

            if response.status_code >= 500 and not error_type:
                error_type = f"HTTP {response.status_code}"

            try:
                ChatRequest.objects.create(
                    response_ms=round(elapsed, 2),
                    status_code=response.status_code,
                    error_type=error_type,
                )
            except DatabaseError:
                logger.exception("Could not save chat request metrics.")

        return response

    def process_exception(self, request, exception):
        request._chat_error_type = type(exception).__name__
        return None