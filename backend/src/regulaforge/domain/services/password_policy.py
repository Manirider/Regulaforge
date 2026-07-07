import re
from dataclasses import dataclass


@dataclass
class PasswordValidationResult:
    is_valid: bool
    errors: list[str]


class PasswordPolicy:
    MIN_LENGTH = 12
    MAX_LENGTH = 128

    @staticmethod
    def validate(password: str) -> PasswordValidationResult:
        errors = []
        if len(password) < PasswordPolicy.MIN_LENGTH:
            errors.append(f"Password must be at least {PasswordPolicy.MIN_LENGTH} characters")
        if len(password) > PasswordPolicy.MAX_LENGTH:
            errors.append(f"Password must not exceed {PasswordPolicy.MAX_LENGTH} characters")
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        if not re.search(r"\d", password):
            errors.append("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+]", password):
            errors.append("Password must contain at least one special character")
        return PasswordValidationResult(is_valid=len(errors) == 0, errors=errors)
