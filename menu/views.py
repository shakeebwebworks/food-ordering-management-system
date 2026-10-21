from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from .models import FoodItem, Wishlist


class FoodDetailView(DetailView):
    model = FoodItem
    template_name = "menu/food_detail.html"
    context_object_name = "food"

    def get_queryset(self):
        # Load everything the page needs in a few queries instead of many
        return (
            FoodItem.objects
            .select_related("restaurant", "category")
            .prefetch_related("images", "sizes", "extras")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        food = self.object

        sizes = list(food.sizes.all())
        context["sizes"] = sizes
        context["default_size"] = next((s for s in sizes if s.is_default), sizes[0] if sizes else None)
        context["extras"] = [extra for extra in food.extras.all() if extra.is_available]

        context["reviews"] = food.reviews.filter(is_approved=True).select_related("user")[:10]

        context["related_foods"] = (
            FoodItem.objects
            .filter(category=food.category, is_available=True)
            .exclude(pk=food.pk)
            .select_related("restaurant")
            .prefetch_related("images")[:3]
        )
        return context


class WishlistView(LoginRequiredMixin, ListView):
    """The logged-in user's saved foods, newest first."""

    template_name = "menu/wishlist.html"
    context_object_name = "foods"
    paginate_by = 12

    def get_queryset(self):
        return (
            FoodItem.objects
            .filter(wishlisted_by__user=self.request.user)
            .select_related("restaurant", "category")
            .prefetch_related("images")
            .order_by("-wishlisted_by__created_at")
        )


@require_POST
def toggle_wishlist(request, food_id):
    """Saves the food to the wishlist, or removes it if it is already there."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)

    food = get_object_or_404(FoodItem, pk=food_id)
    item, created = Wishlist.objects.get_or_create(user=request.user, food_item=food)
    if not created:
        item.delete()
    return JsonResponse({"saved": created})