from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import Address
from core.validators import phone_validator, pincode_validator
from payments.models import Payment

# Needed only when the customer types a new address instead of picking a saved one
REQUIRED_FOR_NEW_ADDRESS = ("contact_name", "contact_phone", "line1", "city", "state", "postal_code")


class CheckoutForm(StyledFormMixin, forms.Form):
    saved_address = forms.ModelChoiceField(queryset=Address.objects.none(), required=False)

    contact_name = forms.CharField(max_length=100, required=False, label="Full name")
    contact_phone = forms.CharField(max_length=14, required=False, label="Phone number", validators=[phone_validator])
    line1 = forms.CharField(max_length=200, required=False, label="Address line 1")
    line2 = forms.CharField(max_length=200, required=False, label="Address line 2 (optional)")
    landmark = forms.CharField(max_length=100, required=False, label="Landmark (optional)")
    city = forms.CharField(max_length=80, required=False)
    state = forms.CharField(max_length=80, required=False)
    postal_code = forms.CharField(max_length=6, required=False, label="PIN code", validators=[pincode_validator])
    save_address = forms.BooleanField(required=False, label="Save this address for next time")

    payment_method = forms.ChoiceField(choices=Payment.Method.choices, initial=Payment.Method.COD)
    notes = forms.CharField(
        max_length=300,
        required=False,
        label="Delivery instructions (optional)",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the customer's own addresses can be chosen
        self.fields["saved_address"].queryset = user.addresses.all()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("saved_address"):
            return cleaned
        for name in REQUIRED_FOR_NEW_ADDRESS:
            if not cleaned.get(name):
                self.add_error(name, "This field is required.")
        return cleaned