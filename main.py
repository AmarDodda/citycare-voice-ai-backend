from datetime import date
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

MOCK_SLOTS = {
    "cardiology": ["10:00 AM", "2:00 PM"],
    "dermatology": ["9:00 AM", "11:30 AM"],
    "orthopedics": ["1:00 PM", "3:30 PM"],
    "primary care": ["9:30 AM", "4:00 PM"],
}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/")
async def dialogflow_webhook(request: Request):
    body = await request.json()

    tag = body.get("fulfillmentInfo", {}).get("tag")
    params = body.get("sessionInfo", {}).get("parameters") or {}

    department = str(
        params.get("department") or ""
    ).strip().lower()

    appointment_date = str(
        params.get("appointment_date") or ""
    )[:10]

    if tag != "check_availability":
        message = "Unknown webhook operation."

    elif not department or not appointment_date:
        message = (
            "I'm missing some appointment details. "
            "Please provide the department and date."
        )

    else:
        try:
            requested_date = date.fromisoformat(appointment_date)

            if requested_date < date.today():
                message = (
                    "That date is in the past. "
                    "Please choose a future date."
                )
            elif requested_date.weekday() >= 5:
                message = (
                    "Our demo system has no weekend appointments. "
                    "Please choose a weekday."
                )
            else:
                slots = MOCK_SLOTS.get(department, [])

                if slots:
                    available = " and ".join(slots)
                    message = (
                        f"For {department} on {appointment_date}, "
                        f"I found these available demo slots: "
                        f"{available}. "
                        "Which time would you prefer?"
                    )
                else:
                    message = (
                        "I couldn't find availability "
                        "for that department."
                    )

        except ValueError:
            message = (
                "I couldn't understand the date. "
                "Please provide a valid date."
            )

    return {
        "fulfillment_response": {
            "messages": [
                {
                    "text": {
                        "text": [message]
                    }
                }
            ]
        }
    }

from pydantic import BaseModel
from fastapi import Header
import os
import secrets

class AvailabilityRequest(BaseModel):
    department: str
    appointment_date: date

@app.post("/vapi/availability")
async def vapi_availability(
    request: AvailabilityRequest,
    x_webhook_token: str = Header(default="")
):
    expected = os.environ.get("WEBHOOK_TOKEN")

    if not expected or not secrets.compare_digest(
        x_webhook_token, expected
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    department = request.department.strip().lower()
    requested_date = request.appointment_date

    if requested_date < date.today():
        return {
            "available": False,
            "message": "Please choose a future date."
        }

    if requested_date.weekday() >= 5:
        return {
            "available": False,
            "message": "No demo weekend appointments are available."
        }

    slots = MOCK_SLOTS.get(department, [])

    return {
        "available": bool(slots),
        "department": department,
        "date": requested_date.isoformat(),
        "slots": slots,
        "message": (
            f"Available demo slots: {', '.join(slots)}"
            if slots
            else "No demo slots found for this department."
        )
    }

from pydantic import BaseModel
from fastapi import Header
import os
import secrets

class AvailabilityRequest(BaseModel):
    department: str
    appointment_date: date

@app.post("/vapi/availability")
async def vapi_availability(
    request: AvailabilityRequest,
    x_webhook_token: str = Header(default="")
):
    expected = os.environ.get("WEBHOOK_TOKEN")

    if not expected or not secrets.compare_digest(
        x_webhook_token, expected
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    department = request.department.strip().lower()
    requested_date = request.appointment_date

    if requested_date < date.today():
        return {
            "available": False,
            "message": "Please choose a future date."
        }

    if requested_date.weekday() >= 5:
        return {
            "available": False,
            "message": "No demo weekend appointments are available."
        }

    slots = MOCK_SLOTS.get(department, [])

    return {
        "available": bool(slots),
        "department": department,
        "date": requested_date.isoformat(),
        "slots": slots,
        "message": (
            f"Available demo slots: {', '.join(slots)}"
            if slots
            else "No demo slots found for this department."
        )
    }

# ---------------------------------------------------
# MOCK APPOINTMENT BOOKING API
# ---------------------------------------------------

import os
import secrets
import sqlite3
import uuid

from fastapi import Header, HTTPException
from pydantic import BaseModel

BOOKINGS_DB = "/tmp/citycare_bookings.db"


class BookingRequest(BaseModel):
    department: str
    appointment_date: date
    appointment_time: str
    call_id: str


def booking_connection():
    conn = sqlite3.connect(
        BOOKINGS_DB, timeout=10
    )
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id TEXT PRIMARY KEY,
            call_id TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            UNIQUE (
                department,
                appointment_date,
                appointment_time
            )
        )
    """)
    return conn


@app.post("/vapi/book")
async def book_appointment(
    request: BookingRequest,
    x_webhook_token: str = Header(default="")
):
    expected = os.environ.get("WEBHOOK_TOKEN")

    if not expected or not secrets.compare_digest(
        x_webhook_token, expected
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    department = request.department.strip().lower()
    appointment_day = request.appointment_date
    appointment_time = request.appointment_time.strip()
    call_id = request.call_id.strip()

    if not call_id or len(call_id) > 128:
        raise HTTPException(
            status_code=400,
            detail="Invalid call ID"
        )

    if appointment_day < date.today():
        return {
            "status": "rejected",
            "message": "Cannot book a past date."
        }

    if appointment_day.weekday() >= 5:
        return {
            "status": "rejected",
            "message": "Weekend bookings are unavailable."
        }

    valid_slots = MOCK_SLOTS.get(department, [])

    if appointment_time not in valid_slots:
        return {
            "status": "rejected",
            "message": "The requested slot is invalid."
        }

    conn = booking_connection()

    try:
        # Serialize competing booking operations
        conn.execute("BEGIN IMMEDIATE")

        # Idempotency: a retry from the same call
        # cannot create another booking.
        existing = conn.execute(
            "SELECT * FROM bookings WHERE call_id = ?",
            (call_id,)
        ).fetchone()

        if existing:
            conn.rollback()

            if (
                existing["department"] == department
                and existing["appointment_date"]
                    == appointment_day.isoformat()
                and existing["appointment_time"]
                    == appointment_time
            ):
                return {
                    "status": "confirmed",
                    "booking_id": existing["booking_id"],
                    "message": "This demo booking was already confirmed."
                }

            return {
                "status": "rejected",
                "message": "This call already has a different demo booking."
            }

        booking_id = "DEMO-" + uuid.uuid4().hex[:10].upper()

        try:
            conn.execute(
                """
                INSERT INTO bookings (
                    booking_id, call_id, department,
                    appointment_date, appointment_time
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    booking_id,
                    call_id,
                    department,
                    appointment_day.isoformat(),
                    appointment_time
                )
            )
            conn.commit()

        except sqlite3.IntegrityError:
            conn.rollback()
            return {
                "status": "unavailable",
                "message": "That demo slot was just taken."
            }

        return {
            "status": "confirmed",
            "booking_id": booking_id,
            "department": department,
            "date": appointment_day.isoformat(),
            "time": appointment_time,
            "message": "Demo appointment booked successfully."
        }

    finally:
        conn.close()
