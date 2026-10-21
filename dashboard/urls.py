from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.OverviewView.as_view(), name="overview"),
    path("orders/<str:order_number>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("foods/add/", views.FoodEditView.as_view(), name="foods_add"),
    path("foods/<int:pk>/edit/", views.FoodEditView.as_view(), name="foods_edit"),
    path("<str:key>/<int:pk>/delete/", views.resource_delete, name="delete"),
    path("<str:key>/<int:pk>/<str:name>/", views.resource_action, name="action"),
]

# One list page for every resource, and add/edit pages for those that have a form
for key, resource in views.RESOURCES.items():
    urlpatterns.append(
        path(f"{key}/", views.ResourceListView.as_view(resource=resource), name=f"{key}_list")
    )
    if resource.form_class is not None:
        urlpatterns += [
            path(f"{key}/add/", views.ResourceCreateView.as_view(resource=resource), name=f"{key}_add"),
            path(f"{key}/<int:pk>/edit/", views.ResourceUpdateView.as_view(resource=resource), name=f"{key}_edit"),
        ]