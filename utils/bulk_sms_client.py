import httpx
import os

AT_USERNAME = os.getenv("AT_USERNAME")
AT_API_KEY = os.getenv("AT_API_KEY")
AT_SENDER_ID = os.getenv("AT_SENDER_ID")
AT_BASE_URL = "https://api.africastalking.com/version1/messaging/bulk"

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "apiKey": AT_API_KEY,
}


async def send_bulk_sms(
    message: str, phone_numbers: list[str], masked_number: str = None, telco: str = None
):
    payload = {
        "username": AT_USERNAME,
        "message": message,
        "senderId": AT_SENDER_ID,
        "phoneNumbers": phone_numbers,
    }

    if masked_number:
        payload["maskedNumber"] = masked_number
    if telco:
        payload["telco"] = telco

    async with httpx.AsyncClient() as client:
        response = await client.post(AT_BASE_URL, headers=headers, json=payload)
        return response.json()
