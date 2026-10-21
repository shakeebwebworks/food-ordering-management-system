from django.conf import settings
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from menu.models import Category, FoodItem
from restaurants.models import Cuisine, Restaurant


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["categories"] = Category.objects.filter(is_active=True)

        # Popular first, then best rated. select_related / prefetch_related
        # load restaurants and photos in a few queries instead of many.
        context["foods"] = (
            FoodItem.objects
            .select_related("restaurant", "category")
            .prefetch_related("images")
            .order_by("-is_popular", "-avg_rating", "name")[:12]
        )

        # Open restaurants first, then best rated
        context["restaurants"] = (
            Restaurant.objects
            .prefetch_related("cuisines")
            .order_by("-is_open", "-avg_rating", "name")[:8]
        )
        context["cuisines"] = Cuisine.objects.filter(restaurants__isnull=False).distinct()
        return context


@require_GET
def search_suggestions(request):
    """Returns matching foods, restaurants and categories as JSON for the search box."""
    query = request.GET.get("q", "").strip()[:60]

    # Nothing typed yet: send popular searches instead
    if len(query) < 2:
        names = (
            FoodItem.objects.filter(is_available=True)
            .order_by("-is_popular", "-avg_rating", "name")
            .values_list("name", flat=True)[:8]
        )
        return JsonResponse({"popular": list(dict.fromkeys(names))[:6]})

    foods = (
        FoodItem.objects.filter(is_available=True)
        .filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(restaurant__name__icontains=query)
        )
        .select_related("restaurant")
        .order_by("-is_popular", "name")[:5]
    )

    restaurants = (
        Restaurant.objects.filter(
            Q(name__icontains=query)
            | Q(location__icontains=query)
            | Q(cuisines__name__icontains=query)
        )
        .distinct()
        .order_by("-is_open", "name")[:4]
    )

    categories = Category.objects.filter(is_active=True, name__icontains=query)[:4]

    return JsonResponse(
        {
            "query": query,
            "foods": [
                {
                    "name": food.name,
                    "restaurant": food.restaurant.name,
                    "price": f"{food.price:.0f}",
                    "is_veg": food.is_veg,
                }
                for food in foods
            ],
            "restaurants": [
                {
                    "name": restaurant.name,
                    "location": f"{restaurant.location}, {restaurant.city}",
                    "is_open": restaurant.is_open,
                }
                for restaurant in restaurants
            ],
            "categories": [{"name": category.name, "slug": category.slug} for category in categories],
        }
    )
def preview_error(request, code):
    """Development only: shows an error page without turning DEBUG off."""
    pages = {400: "400.html", 403: "403.html", 404: "404.html", 500: "500.html"}
    if not settings.DEBUG or code not in pages:
        raise Http404
    return render(request, pages[code], status=code)