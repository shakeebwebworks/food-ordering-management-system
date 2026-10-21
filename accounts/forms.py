from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from core.validators import phone_validator

from .models import Address, Profile

User = get_user_model()


class StyledFormMixin:
    """Gives every field our Bootstrap look, and marks fields with errors in red."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, forms.Select) and not isinstance(widget, forms.RadioSelect):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


class LoginForm(StyledFormMixin, AuthenticationForm):
    pass


class RegisterForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ProfileForm(StyledFormMixin, forms.ModelForm):
    """Name and email live on the user, the phone number on the profile."""

    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=14, required=False, validators=[phone_validator])

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile, _ = Profile.objects.get_or_create(user=self.instance)
        self.fields["phone"].initial = self.profile.phone

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self.profile.phone = self.cleaned_data["phone"]
            self.profile.save(update_fields=["phone", "updated_at"])
        return user


class AddressForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            "label", "recipient_name", "phone", "line1", "line2",
            "landmark", "city", "state", "postal_code", "is_default",
        )
        labels = {
            "recipient_name": "Full name",
            "phone": "Phone number",
            "line1": "Address line 1",
            "line2": "Address line 2 (optional)",
            "landmark": "Landmark (optional)",
            "postal_code": "PIN code",
            "is_default": "Make this my default address",
        }


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass