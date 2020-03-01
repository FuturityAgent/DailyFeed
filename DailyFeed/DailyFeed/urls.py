"""DailyFeed URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.decorators.cache import cache_page
import sys
sys.path.append("..")
from feed import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.IndexView.as_view(), name='index'),
    path('category/<int:id>', views.CategoryView.as_view(), name='category-view'),
    path('category/new', views.CategoryCreateView.as_view(), name="new-category"),
    path('category/<int:id>/source', views.CategorySourcesView.as_view(), name='category-sources'),
    path("category/<int:id>/source/new", views.SourceCreateView.as_view(), name="new-source"),
    path("category/<int:id>/tags/new", views.TagCreateView.as_view(), name="new-category-tag"),
    path("category/<int:category_id>/tags/<int:pk>/delete", views.DeleteTagView.as_view(), name="delete-tag"),
    path("source/check", views.FindSourcesView.as_view() , name="find-source"),
    path("source/check/add", views.AddDiscoveredSourceView.as_view(), name="discovered-source-add"),
    path("source/<int:pk>/delete", views.DeleteSourceView.as_view(), name="delete-source")
]
