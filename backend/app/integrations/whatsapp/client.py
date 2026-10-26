from typing import Any

import httpx

from app.core.config import settings


class WhatsAppClient:
    def __init__(self) -> None:
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.api_version = settings.WHATSAPP_API_VERSION

    async def send_text_message(
        self,
        recipient_phone: str,
        message: str,
        phone_number_id: str | None = None,  # FIXED: Accept dynamic router gateway ID
    ) -> dict[str, Any]:
        
        # Determine the target endpoint using the incoming webhook's ID, or fall back to settings
        target_phone_id = phone_number_id or self.phone_number_id
        
        url = f"https://graph.facebook.com/{self.api_version}/{target_phone_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "body": message,
            },
        }

        print("\n--- WHATSAPP OUTBOUND MESSAGE ---")
        print(f"Target URL: {url}")
        print(f"Recipient: {recipient_phone}")
        print(f"Message: {message}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

        print(
            f"WhatsApp API response: "
            f"{response.status_code} | {response.text}"
        )

        response.raise_for_status()

        return response.json()

    async def send_interactive_buttons(
        self,
        recipient_phone: str,
        body_text: str,
        buttons: list[dict[str, str]],
        phone_number_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Sends a WhatsApp Interactive Button message safely using verified URL compiling.
        """
        # 1. Ensure target_phone_id falls back to the reliable initialized value
        target_phone_id = phone_number_id or self.phone_number_id
        
        # 2. Re-verify api_version formatting
        version = self.api_version if self.api_version else "v26.0"
        
        # Absolute URL construction matching your successful send_text_message route
        url = f"https://graph.facebook.com/{version}/{target_phone_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        formatted_buttons = [
            {
                "type": "reply",
                "reply": {
                    "id": btn["id"],
                    "title": btn["title"]
                }
            }
            for btn in buttons
        ]

        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body_text
                },
                "action": {
                    "buttons": formatted_buttons
                }
            }
        }

        print("\n--- WHATSAPP OUTBOUND INTERACTIVE MESSAGE ---")
        print(f"Target URL: {url}")
        print(f"Recipient: {recipient_phone}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

        print(f"WhatsApp Interactive Response: {response.status_code} | {response.text}")
        response.raise_for_status()
        return response.json()
