"""Address value object representing a physical or legal address."""

from typing import Any, Optional


class Address:
    """Immutable address value object.

    Represents a physical or legal address for entities,
    organizations, and legal jurisdictions.
    """

    def __init__(
        self,
        street: str,
        city: str,
        country: str,
        state: Optional[str] = None,
        postal_code: Optional[str] = None,
        building_name: Optional[str] = None,
        floor: Optional[str] = None,
        po_box: Optional[str] = None,
    ) -> None:
        self._validate(street, city, country)

        self._street: str = street.strip()
        self._city: str = city.strip()
        self._country: str = country.strip()
        self._state: Optional[str] = state.strip() if state else None
        self._postal_code: Optional[str] = postal_code.strip() if postal_code else None
        self._building_name: Optional[str] = building_name.strip() if building_name else None
        self._floor: Optional[str] = floor.strip() if floor else None
        self._po_box: Optional[str] = po_box.strip() if po_box else None

    @staticmethod
    def _validate(street: str, city: str, country: str) -> None:
        if not street or len(street.strip()) < 3:
            raise ValueError("Street address must be at least 3 characters")
        if not city or len(city.strip()) < 2:
            raise ValueError("City must be at least 2 characters")
        if not country or len(country.strip()) < 2:
            raise ValueError("Country must be at least 2 characters")

    @property
    def street(self) -> str:
        return self._street

    @property
    def city(self) -> str:
        return self._city

    @property
    def country(self) -> str:
        return self._country

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def postal_code(self) -> Optional[str]:
        return self._postal_code

    @property
    def full_address(self) -> str:
        """Return human-readable full address."""
        parts = [self._street]
        if self._building_name:
            parts.insert(0, self._building_name)
        if self._floor:
            parts.append(f"Floor {self._floor}")
        if self._po_box:
            parts.append(f"PO Box {self._po_box}")
        parts.append(self._city)
        if self._state:
            parts.append(self._state)
        if self._postal_code:
            parts.append(self._postal_code)
        parts.append(self._country)
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "street": self._street,
            "city": self._city,
            "country": self._country,
            "state": self._state,
            "postal_code": self._postal_code,
            "building_name": self._building_name,
            "floor": self._floor,
            "po_box": self._po_box,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Address":
        return cls(
            street=data["street"],
            city=data["city"],
            country=data["country"],
            state=data.get("state"),
            postal_code=data.get("postal_code"),
            building_name=data.get("building_name"),
            floor=data.get("floor"),
            po_box=data.get("po_box"),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Address):
            return NotImplemented
        return (
            self._street == other._street
            and self._city == other._city
            and self._country == other._country
            and self._state == other._state
            and self._postal_code == other._postal_code
        )

    def __hash__(self) -> int:
        return hash((self._street, self._city, self._country, self._state, self._postal_code))

    def __repr__(self) -> str:
        return f"<Address {self._city}, {self._country}>"
