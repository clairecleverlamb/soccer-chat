from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "core/home.html"


class SectionView(TemplateView):
    """Shared page shell for an area that does not have a user story yet."""

    template_name = "core/section.html"
    title = ""
    summary = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["summary"] = self.summary
        return context
