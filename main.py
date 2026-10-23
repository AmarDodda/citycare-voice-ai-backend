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
