from django.core.exceptions import ValidationError


class MaximumLengthValidator:
    """Valida tamanho maximo de senha."""

    def __init__(self, max_length=8):
        self.max_length = max_length

    def validate(self, password, user=None):
        if len(password or '') > self.max_length:
            raise ValidationError(
                f'A senha deve ter no maximo {self.max_length} caracteres.',
                code='password_too_long',
            )

    def get_help_text(self):
        return f'Sua senha deve conter no maximo {self.max_length} caracteres.'
