from django.conf import settings
from django.db import models, transaction

from core.models import TimeStampedModel
from core.validators import phone_validator, pincode_validator


class Profile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=14, blank=True, validators=[phone_validator])
    avatar = models.ImageField(upload_to="avatars/", blank=True)

    def __str__(self):
        return f"Profile of {self.user}"


class Address(TimeStampedModel):
    class Label(models.TextChoices):
        HOME = "home", "Home"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=10, choices=Label.choices, default=Label.HOME)
    recipient_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=14, validators=[phone_validator])
    line1 = models.CharField("address line 1", max_length=200)
    line2 = models.CharField("address line 2", max_length=200, blank=True)
    landmark = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=6, validators=[pincode_validator])
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name_plural = "addresses"
        indexes = [models.Index(fields=["user", "is_default"])]

    def __str__(self):
        return f"{self.get_label_display()} - {self.line1}, {self.city}"

    @property
    def full_address(self):
        parts = [self.line1, self.line2, self.landmark, self.city, f"{self.state} {self.postal_code}"]
        return ", ".join(part for part in parts if part)

    def save(self, *args, **kwargs):
        # MySQL has no partial unique indexes, so keep one default per user here.
        with transaction.atomic():
            if self.is_default:
                Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
            super().save(*args, **kwargs)