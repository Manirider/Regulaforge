"""Unit tests for domain value objects."""

import pytest
from regulaforge.domain.value_objects.address import Address
from regulaforge.domain.value_objects.contact import Contact


class TestAddress:
    def test_create_full(self):
        addr = Address(
            street="123 Main St",
            city="New York",
            state="NY",
            postal_code="10001",
            country="US",
        )
        assert addr.street == "123 Main St"
        assert addr.city == "New York"
        assert addr.country == "US"
        assert addr.full_address == "123 Main St, New York, NY, 10001, US"

    def test_create_minimal(self):
        addr = Address(street="1 Street", city="City", country="CO")
        assert addr.postal_code is None
        assert addr.state is None

    def test_empty_street_raises(self):
        with pytest.raises(ValueError):
            Address(street="", city="City", country="CO")

    def test_equality(self):
        a1 = Address(street="1 St", city="NYC", country="US")
        a2 = Address(street="1 St", city="NYC", country="US")
        assert a1 == a2
        assert hash(a1) == hash(a2)

    def test_inequality(self):
        a1 = Address(street="1 St", city="NYC", country="US")
        a2 = Address(street="2 St", city="NYC", country="US")
        assert a1 != a2

    def test_to_dict(self):
        addr = Address(street="1 St", city="NYC", state="NY", country="US")
        d = addr.to_dict()
        assert d["street"] == "1 St"
        assert d["state"] == "NY"


class TestContact:
    def test_create_email(self):
        c = Contact(email="test@example.com")
        assert c.email == "test@example.com"
        assert c.phone is None

    def test_create_full(self):
        c = Contact(
            email="a@b.com",
            phone="+1-555-0100",
        )
        assert c.phone == "+1-555-0100"

    def test_invalid_email_raises(self):
        with pytest.raises(ValueError):
            Contact(email="not-an-email")

    def test_equality(self):
        c1 = Contact(email="a@b.com", phone="123")
        c2 = Contact(email="a@b.com", phone="123")
        assert c1 == c2

    def test_inequality(self):
        c1 = Contact(email="a@b.com")
        c2 = Contact(email="c@d.com")
        assert c1 != c2

    def test_to_dict(self):
        c = Contact(email="test@test.com", phone="555-0100")
        d = c.to_dict()
        assert d["email"] == "test@test.com"
        assert d["phone"] == "555-0100"
