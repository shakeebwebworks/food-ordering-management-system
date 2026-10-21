from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("food_item", "user", "rating", "is_approved", "created_at")
    list_filter = ("is_approved", "rating")
    search_fields = ("user__username", "food_item__name", "comment")
    list_select_related = ("user", "food_item")
    actions = ["approve_reviews", "hide_reviews"]

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        self._set_approved(queryset, True)

    @admin.action(description="Hide selected reviews")
    def hide_reviews(self, request, queryset):
        self._set_approved(queryset, False)

    @staticmethod
    def _set_approved(queryset, value):
        # save() per row (not queryset.update) so rating-aggregate signals fire.
        for review in queryset:
            review.is_approved = value
            review.save(update_fields=["is_approved", "updated_at"])