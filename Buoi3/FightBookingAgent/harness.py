
from datetime import date
from pydantic import BaseModel, Field, field_validator


class FlightRequest(BaseModel):
    from_city: str
    to_city: str
    date: date
    passenger_name: str = Field(min_length=2)
    passenger_email: str
    flight_id: str | None = None
    confirmed: bool = False

    @field_validator("from_city", "to_city")
    @classmethod
    def validate_airport_code(cls, value):
        value = value.strip().upper()

        if len(value) != 3 or not value.isalpha():
            raise ValueError("Mã sân bay phải gồm 3 chữ cái")

        return value

    @field_validator("passenger_email")
    @classmethod
    def validate_email(cls, value):
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Email không hợp lệ")
        return value.strip()


def check_permission(action: str, confirmed: bool) -> bool:
    """Kiểm tra quyền thực hiện hành động."""

    if action == "book_flight" and not confirmed:
        return False

    return action in {
        "search_flights",
        "check_seat",
        "get_booking",
        "book_flight",
    }


def check_completion(result: dict) -> bool:
    """Kiểm tra kết quả dựa trên dữ liệu trả về từ tool."""

    return (
        result.get("success") is True
        and result.get("status") == "CONFIRMED"
        and bool(result.get("booking_id"))
    )


def handoff(reason: str, missing_fields=None, state: dict = None) -> dict:
    """Bàn giao cho người dùng khi cần thêm thông tin."""
    return {
        "status": "NEEDS_USER_INPUT",
        "reason": reason,
        "missing_fields": missing_fields or [],
        "state": state  # Dòng quan trọng để giữ lại bộ nhớ
    }