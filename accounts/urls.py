from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.SignInView.as_view(), name="login"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("account/", views.ProfileView.as_view(), name="profile"),
    path("account/addresses/", views.AddressListView.as_view(), name="addresses"),
    path("account/addresses/add/", views.AddressCreateView.as_view(), name="address_add"),
    path("account/addresses/<int:pk>/edit/", views.AddressUpdateView.as_view(), name="address_edit"),
    path("account/addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),
    path("account/addresses/<int:pk>/default/", views.address_default, name="address_default"),
    path("account/settings/", views.PasswordView.as_view(), name="settings"),
]