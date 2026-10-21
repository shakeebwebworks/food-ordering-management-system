from django.contrib import admin

from .models import Cart, CartItem, Coupon, Order, OrderItem, OrderStatusEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("food_item", "name", "size_name", "extras", "unit_price", "quantity")
    can_delete = False


class OrderStatusEventInline(admin.TabularInline):
    model = OrderStatusEvent
    extra = 0
    readonly_fields = ("status", "note", "created_at")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "restaurant_name", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "user__username", "user__email", "contact_phone", "restaurant_name")
    list_select_related = ("user",)
    readonly_fields = ("order_number", "subtotal", "delivery_fee", "tax", "discount", "total", "created_at")
    inlines = [OrderItemInline, OrderStatusEventInline]

    def save_model(self, request, obj, form, change):
        # Route status edits through update_status() so the tracking timeline stays accurate.
        if change and "status" in form.changed_data:
            new_status = obj.status
            obj.status = form.initial["status"]
            super().save_model(request, obj, form, change)
            obj.update_status(new_status)
        else:
            super().save_model(request, obj, form, change)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
    inlines = [CartItemInline]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_type", "value", "valid_until", "used_count", "usage_limit", "is_active")
    list_filter = ("is_active", "discount_type")
    search_fields = ("code",)