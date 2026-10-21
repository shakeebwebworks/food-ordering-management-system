from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("restaurants", views.RestaurantViewSet, basename="restaurant")
router.register("foods", views.FoodItemViewSet, basename="food")
router.register("orders", views.OrderViewSet, basename="order")
router.register("reviews", views.ReviewViewSet, basename="review")
router.register("wishlist", views.WishlistViewSet, basename="wishlist")

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view(), name="csrf"),
    path("auth/register/", views.RegisterAPIView.as_view(), name="register"),
    path("auth/login/", views.LoginAPIView.as_view(), name="login"),
    path("auth/logout/", views.LogoutAPIView.as_view(), name="logout"),
    path("auth/me/", views.MeAPIView.as_view(), name="me"),
    path("search/", views.SearchAPIView.as_view(), name="search"),
    path("cart/", views.CartAPIView.as_view(), name="cart"),
    path("cart/items/", views.CartItemsAPIView.as_view(), name="cart-items"),
    path("cart/items/<int:item_id>/", views.CartItemDetailAPIView.as_view(), name="cart-item"),
    path("dashboard/", views.DashboardAPIView.as_view(), name="dashboard"),
    path("", include(router.urls)),
]