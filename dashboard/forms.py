from django import forms
from django.forms import inlineformset_factory

from accounts.forms import StyledFormMixin
from menu.models import Category, FoodExtra, FoodImage, FoodItem, FoodSize
from orders.models import Order
from restaurants.models import Cuisine, Restaurant


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "icon", "image", "display_order", "is_active")


class CuisineForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Cuisine
        fields = ("name",)


class RestaurantForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Restaurant
        fields = (
            "name", "description", "image", "cuisines", "location", "city", "price_range",
            "delivery_time_minutes", "delivery_fee", "min_order_amount", "is_veg_only", "is_open",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class FoodForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FoodItem
        fields = (
            "restaurant", "category", "name", "description", "ingredients",
            "price", "is_veg", "is_available", "is_popular",
        )
        widgets = {"ingredients": forms.Textarea(attrs={"rows": 2})}


class FoodImageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FoodImage
        fields = ("image", "alt_text", "is_primary")


class FoodSizeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FoodSize
        fields = ("name", "price_delta", "is_default")


class FoodExtraForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FoodExtra
        fields = ("name", "price", "is_available")


# Extra rows on the food form: photos, sizes and add-ons
FoodImageFormSet = inlineformset_factory(FoodItem, FoodImage, form=FoodImageForm, extra=2, can_delete=True)
FoodSizeFormSet = inlineformset_factory(FoodItem, FoodSize, form=FoodSizeForm, extra=2, can_delete=True)
FoodExtraFormSet = inlineformset_factory(FoodItem, FoodExtra, form=FoodExtraForm, extra=3, can_delete=True)


class OrderStatusForm(StyledFormMixin, forms.Form):
    status = forms.ChoiceField(choices=Order.Status.choices)
    note = forms.CharField(max_length=200, required=False, label="Note (optional)")