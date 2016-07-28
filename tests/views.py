from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, TemplateView

from .models import Article, Author


class HomeView(TemplateView):
    template_name = 'tests/home_view.html'


class ArticleList(ListView):
    model = Article


class ArticleDetail(DetailView):
    model = Article
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            self.model,
            language=self.kwargs['language'],
            slug=self.kwargs['slug'],
        )


class AuthorList(ListView):
    model = Author


class AuthorDetail(DetailView):
    model = Author
    slug_field = 'key'
