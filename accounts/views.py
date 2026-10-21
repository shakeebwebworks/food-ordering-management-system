from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView, ListView, UpdateView

from .forms import AddressForm, LoginForm, ProfileForm, RegisterForm, StyledPasswordChangeForm
from .models import Address


class SignInView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class RegisterView(FormView):
    template_name = "accounts/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)  # sign the new user in straight away
        return super().form_valid(form)


# ---------- Account area (needs a logged-in user) ----------

class AccountMixin(LoginRequiredMixin):
    """Marks which tab of the account menu is open."""

    section = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = self.section
        return context


class ProfileView(AccountMixin, UpdateView):
    template_name = "accounts/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:profile")
    section = "profile"

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile was updated.")
        return super().form_valid(form)


class AddressListView(AccountMixin, ListView):
    template_name = "accounts/addresses.html"
    context_object_name = "addresses"
    section = "addresses"

    def get_queryset(self):
        return self.request.user.addresses.all()


class AddressCreateView(AccountMixin, CreateView):
    template_name = "accounts/address_form.html"
    form_class = AddressForm
    success_url = reverse_lazy("accounts:addresses")
    section = "addresses"

    def get_initial(self):
        # The first address someone saves becomes their default
        return {"is_default": not self.request.user.addresses.exists()}

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Address saved.")
        return super().form_valid(form)


class AddressUpdateView(AccountMixin, UpdateView):
    template_name = "accounts/address_form.html"
    form_class = AddressForm
    success_url = reverse_lazy("accounts:addresses")
    section = "addresses"

    def get_queryset(self):
        return self.request.user.addresses.all()  # people can only edit their own addresses

    def form_valid(self, form):
        messages.success(self.request, "Address updated.")
        return super().form_valid(form)


@login_required
@require_POST
def address_delete(request, pk):
    address = get_object_or_404(request.user.addresses, pk=pk)
    was_default = address.is_default
    address.delete()
    if was_default:
        replacement = request.user.addresses.first()
        if replacement:
            replacement.is_default = True
            replacement.save()
    messages.success(request, "Address removed.")
    return redirect("accounts:addresses")


@login_required
@require_POST
def address_default(request, pk):
    address = get_object_or_404(request.user.addresses, pk=pk)
    address.is_default = True
    address.save()  # Address.save() clears the default flag on the user's other addresses
    messages.success(request, "Default address changed.")
    return redirect("accounts:addresses")


class PasswordView(AccountMixin, PasswordChangeView):
    template_name = "accounts/settings.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:settings")
    section = "settings"

    def form_valid(self, form):
        messages.success(self.request, "Your password was changed.")
        return super().form_valid(form)