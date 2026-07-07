"""Contact information value object."""

import re
from typing import Any, Optional


class ContactInfo:
    """Immutable contact information value object.

    Encapsulates email, phone, and related contact details
    with built-in validation.
    """

    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{1,14}$")  # E.164 format

    def __init__(
        self,
        email: str,
        phone: Optional[str] = None,
        alternate_email: Optional[str] = None,
        website: Optional[str] = None,
        fax: Optional[str] = None,
    ) -> None:
        self._validate_email(email, "email")
        if phone:
            self._validate_phone(phone)
        if alternate_email:
            self._validate_email(alternate_email, "alternate_email")

        self._email: str = email.strip().lower()
        self._phone: Optional[str] = phone.strip() if phone else None
        self._alternate_email: Optional[str] = alternate_email.strip().lower() if alternate_email else None
        self._website: Optional[str] = website.strip() if website else None
        self._fax: Optional[str] = fax.strip() if fax else None

    @staticmethod
    def _validate_email(email: str, field_name: str) -> None:
        if not email or not ContactInfo.EMAIL_PATTERN.match(email.strip()):
            raise ValueError(f"Invalid {field_name} format: {email}")

    @staticmethod
    def _validate_phone(phone: str) -> None:
        cleaned = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not ContactInfo.PHONE_PATTERN.match(cleaned):
            raise ValueError(f"Invalid phone number format (E.164 expected): {phone}")

    @property
    def email(self) -> str:
        return self._email

    @property
    def phone(self) -> Optional[str]:
        return self._phone

    @property
    def alternate_email(self) -> Optional[str]:
        return self._alternate_email

    @property
    def website(self) -> Optional[str]:
        return self._website

    @property
    def fax(self) -> Optional[str]:
        return self._fax

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self._email,
            "phone": self._phone,
            "alternate_email": self._alternate_email,
            "website": self._website,
            "fax": self._fax,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContactInfo":
        return cls(
            email=data["email"],
            phone=data.get("phone"),
            alternate_email=data.get("alternate_email"),
            website=data.get("website"),
            fax=data.get("fax"),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ContactInfo):
            return NotImplemented
        return self._email == other._email

    def __hash__(self) -> int:
        return hash(self._email)

    def __repr__(self) -> str:
        return f"<ContactInfo {self._email}>"


Contact = ContactInfo
