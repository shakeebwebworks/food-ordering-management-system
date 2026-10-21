from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("cart/", views.CartView.as_view(), name="cart"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/update/<int:item_id>/", views.cart_update, name="cart_update"),
    path("cart/remove/<int:item_id>/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("account/orders/", views.OrderListView.as_view(), name="order_list"),
    path("orders/<str:order_number>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<str:order_number>/status/", views.order_status, name="order_status"),
    path("orders/<str:order_number>/reorder/", views.reorder_order, name="reorder"),
]