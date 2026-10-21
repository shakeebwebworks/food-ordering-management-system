from django.urls import path

from .views import HomeView, preview_error, search_suggestions

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("search/suggestions/", search_suggestions, name="search_suggestions"),
        path("preview-error/<int:code>/", preview_error, name="preview_error"),
]