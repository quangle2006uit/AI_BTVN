
from typing import Optional
from uuid import uuid4

from langchain_core.tools import tool


FLIGHTS = [
    {
        "flight_id": "VN101",
        "from_city": "SGN",
        "to_city": "HAN",
        "date": "2026-10-15",
        "departure": "08:00",
        "price": 1_500_000,
        "seats": 5,
    },
    {
        "flight_id": "VN102",
        "from_city": "SGN",
        "to_city": "HAN",
        "date": "2026-10-15",
        "departure": "14:00",
        "price": 1_800_000,
        "seats": 3,
    },
]

BOOKINGS = {}


@tool
def search_flights(
    from_city: str,
    to_city: str,
    date: str,
) -> list[dict]:
    """Tìm chuyến bay theo mã sân bay đi, đến và ngày bay YYYY-MM-DD."""

    return [
        flight.copy()
        for flight in FLIGHTS
        if flight["from_city"] == from_city.upper()
        and flight["to_city"] == to_city.upper()
        and flight["date"] == date
    ]


@tool
def check_seat(flight_id: str) -> dict:
    """Kiểm tra số ghế còn trống của một chuyến bay."""

    flight = next(
        (f for f in FLIGHTS if f["flight_id"] == flight_id),
        None,
    )

    if flight is None:
        return {"success": False, "error": "Không tìm thấy chuyến bay"}

    return {
        "success": True,
        "flight_id": flight_id,
        "available_seats": flight["seats"],
    }


@tool
def book_flight(
    flight_id: str,
    passenger_name: str,
    passenger_email: str,
    confirmed: bool = False,
) -> dict:
    """Tạo đặt vé mô phỏng. Chỉ thực hiện khi confirmed=True."""

    if not confirmed:
        return {
            "success": False,
            "error": "Cần xác nhận của người dùng trước khi đặt vé.",
        }

    flight = next(
        (f for f in FLIGHTS if f["flight_id"] == flight_id),
        None,
    )

    if flight is None:
        return {"success": False, "error": "Không tìm thấy chuyến bay"}

    if flight["seats"] <= 0:
        return {"success": False, "error": "Chuyến bay đã hết chỗ"}

    if not passenger_name.strip() or "@" not in passenger_email:
        return {"success": False, "error": "Thông tin hành khách không hợp lệ"}

    flight["seats"] -= 1

    booking_id = str(uuid4())[:8].upper()

    booking = {
        "booking_id": booking_id,
        "flight_id": flight_id,
        "passenger_name": passenger_name,
        "passenger_email": passenger_email,
        "status": "CONFIRMED",
        "mock": True,
    }

    BOOKINGS[booking_id] = booking

    return {"success": True, **booking}


@tool
def get_booking(booking_id: str) -> dict:
    """Tra cứu thông tin đặt vé theo mã đặt chỗ."""

    booking = BOOKINGS.get(booking_id)

    if booking is None:
        return {"success": False, "error": "Không tìm thấy mã đặt vé"}

    return {"success": True, **booking}


TOOLS = [
    search_flights,
    check_seat,
    book_flight,
    get_booking,
]