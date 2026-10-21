from django.urls import path

from .views import FoodDetailView, WishlistView, toggle_wishlist

app_name = "menu"

urlpatterns = [
    path("food/<slug:slug>/", FoodDetailView.as_view(), name="food_detail"),
    path("wishlist/", WishlistView.as_view(), name="wishlist"),
    path("wishlist/toggle/<int:food_id>/", toggle_wishlist, name="wishlist_toggle"),
]