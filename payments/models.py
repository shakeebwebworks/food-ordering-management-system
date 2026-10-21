from django.db import models

from core.models import TimeStampedModel


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        COD = "cod", "Cash on Delivery"
        CARD = "card", "Card"
        UPI = "upi", "UPI"
        NETBANKING = "netbanking", "Net Banking"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    # PROTECT: payment records are financial history and must outlive accidental order deletion.
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=15, choices=Method.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["transaction_id"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="payments_payment_amount_non_negative"),
        ]

    def __str__(self):
        return f"{self.order} - {self.get_method_display()} ({self.get_status_display()})"