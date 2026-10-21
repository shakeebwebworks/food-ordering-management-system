from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r"^\+?[0-9]{10,13}$",
    message="Enter a valid phone number (10-13 digits, optional leading +).",
)

pincode_validator = RegexValidator(
    regex=r"^[1-9][0-9]{5}$",
    message="Enter a valid 6-digit PIN code.",
)