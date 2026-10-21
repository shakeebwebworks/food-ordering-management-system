from django.contrib import admin

from .models import Category, FoodExtra, FoodImage, FoodItem, FoodSize, Wishlist


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("name",)


class FoodImageInline(admin.TabularInline):
    model = FoodImage
    extra = 1


class FoodSizeInline(admin.TabularInline):
    model = FoodSize
    extra = 0


class FoodExtraInline(admin.TabularInline):
    model = FoodExtra
    extra = 0


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "category", "price", "is_veg", "is_available", "is_popular", "avg_rating")
    list_filter = ("category", "is_veg", "is_available", "is_popular", "restaurant")
    search_fields = ("name", "restaurant__name", "description")
    list_select_related = ("restaurant", "category")
    readonly_fields = ("avg_rating", "review_count")
    inlines = [FoodImageInline, FoodSizeInline, FoodExtraInline]


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "food_item", "created_at")
    list_select_related = ("user", "food_item")