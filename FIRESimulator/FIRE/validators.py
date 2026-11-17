import re

from django.core.exceptions import ValidationError


class ComplexityValidator:
    """Requires an uppercase letter, a number and a special character."""

    message = "Password must contain a capital letter, a number and a special character."

    def validate(self, password, user=None):
        if not (re.search(r'[A-Z]', password) and re.search(r'\d', password) and re.search(r'[^A-Za-z0-9]', password)):
            raise ValidationError(self.message, code='password_complexity')

    def get_help_text(self):
        return self.message
