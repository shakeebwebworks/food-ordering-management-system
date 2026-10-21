from django.contrib import admin

from .models import Cuisine, Restaurant


@admin.register(Cuisine)
class CuisineAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "location", "price_range", "avg_rating", "is_open")
    list_filter = ("is_open", "is_veg_only", "price_range", "city", "cuisines")
    search_fields = ("name", "location", "city")
    filter_horizontal = ("cuisines",)
    readonly_fields = ("avg_rating", "review_count")