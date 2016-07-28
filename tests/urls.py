from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
    url(r'^$', views.HomeView.as_view(), name='home'),
    url(r'^articles/$', views.ArticleList.as_view(), name='article_list'),
    url(r'^articles/(?P<language>\w+)/(?P<slug>\w+)/$', views.ArticleDetail.as_view(), name='article_detail'),
    url(r'^authors/$', views.AuthorList.as_view(), name='author_list'),
    url(r'^authors/(?P<slug>\w+)/$', views.AuthorDetail.as_view(), name='author_detail'),
    url(r'^admin/', admin.site.urls),
]
