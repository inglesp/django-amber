from django.views.generic import DetailView, ListView, TemplateView

from .models import Article, Author


class HomeView(TemplateView):
    template_name = 'tests/home_view.html'


class ArticleList(ListView):
    model = Article


class ArticleDetail(DetailView):
    model = Article
    slug_field = 'key'


class AuthorList(ListView):
    model = Author


class AuthorDetail(DetailView):
    model = Author
    slug_field = 'key'
