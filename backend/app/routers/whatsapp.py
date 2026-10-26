import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.message_parser import WhatsAppMessageParser
from app.services.whatsapp_service import WhatsAppConversationService


router = APIRouter(
    prefix="/api/whatsapp",
    tags=["WhatsApp"],
)

logger = logging.getLogger("app.routers.whatsapp")


def _mask_phone(phone: str) -> str:
    """Mask a phone number before writing it to application logs."""
    if len(phone) <= 4:
        return "***"
    return "*" * (len(phone) - 4) + phone[-4:]


def _format_outbound_message(message: Any) -> str:
    """Normalize escaped line breaks and remove excess outer whitespace."""
    text = str(message or "")
    return text.replace("\\r\\n", "\n").replace("\\n", "\n").strip()


# ================================================================
# META WEBHOOK VERIFICATION
# ================================================================

@router.get(
    "/webhook",
    response_class=PlainTextResponse,
)
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(
        default=None,
        alias="hub.verify_token",
    ),
    hub_challenge: str | None = Query(
        default=None,
        alias="hub.challenge",
    ),
):
    """Verify the callback URL with Meta."""
    if (
        hub_mode == "subscribe"
        and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN
        and hub_challenge is not None
    ):
        return PlainTextResponse(
            content=hub_challenge,
            status_code=status.HTTP_200_OK,
        )

    return PlainTextResponse(
        content="Forbidden",
        status_code=status.HTTP_403_FORBIDDEN,
    )


# ================================================================
# META WEBHOOK RECEIVER
# ================================================================

@router.post("/webhook")
async def receive_webhook(
    payload: dict,
    db: Session = Depends(get_db),
) -> Any:
    if not payload:
        return JSONResponse(
            content={
                "status": "received",
                "detail": "Empty notification ignored",
            },
            status_code=status.HTTP_200_OK,
        )

    # Extract the business phone number ID associated with this webhook.
    business_phone_id = None
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                if metadata.get("phone_number_id"):
                    business_phone_id = metadata["phone_number_id"]
                    break
            if business_phone_id:
                break
    except (AttributeError, TypeError):
        logger.warning("Could not extract business phone ID from webhook.")

    messages = WhatsAppMessageParser.parse(payload)

    # Meta also sends status notifications with no inbound messages.
    if not messages:
        return {
            "status": "received",
            "messages_found": 0,
        }

    whatsapp_service = WhatsAppConversationService(db)
    client = WhatsAppClient()
    results = []

    for message in messages:
        sender_phone = message.get("from")
        if not sender_phone:
            logger.warning("Ignoring inbound WhatsApp message without sender.")
            continue

        message_type = message.get("type", "unknown")
        masked_sender = _mask_phone(str(sender_phone))

        logger.info(
            "Processing inbound WhatsApp message from %s; type=%s",
            masked_sender,
            message_type,
        )

        try:
            # START, RESTART, RESET, SKIP, and conversation-state handling
            # belong in WhatsAppConversationService.handle_message().
            result = whatsapp_service.handle_message(
                sender_phone=sender_phone,
                message_type=message_type,
                text=message.get("text"),
                media_reference=message.get("media_id"),
                raw_message=message,
            )

            if not isinstance(result, dict):
                logger.error(
                    "WhatsApp service returned an unexpected result for %s.",
                    masked_sender,
                )
                results.append({
                    "status": "error",
                    "detail": "Unexpected conversation service response.",
                })
                continue

            results.append(result)
            outbound_message = result.get("message")

            if not outbound_message:
                continue

            formatted_message = _format_outbound_message(outbound_message)

            if not formatted_message:
                continue

            # ================================================================
            # FIX: INTERACTIVE BUTTON INJECTION CONDITIONAL GATEWAY
            # ================================================================
            action_stage = result.get("action")

            if action_stage == "ASSESSMENT_READY":
                tax_action_buttons = [
                    {"id": "btn_make_payment", "title": "Make Payment"},
                    {"id": "btn_objection", "title": "Objection"}
                ]
                
                # Dispatches the assessment template text bundled with dynamic Meta buttons
                await client.send_interactive_buttons(
                    recipient_phone=sender_phone,
                    body_text=formatted_message,
                    buttons=tax_action_buttons,
                    phone_number_id=business_phone_id,
                )
            else:
                # Mainpath standard text question handler block
                await client.send_text_message(
                    recipient_phone=sender_phone,
                    message=formatted_message,
                    phone_number_id=business_phone_id,
                )

            logger.info(
                "WhatsApp response delivered to %s",
                masked_sender,
            )

        except Exception:
            # Do not expose phone numbers, tokens, or message content in logs.
            logger.exception(
                "Failed to process or respond to WhatsApp message from %s.",
                masked_sender,
            )

            results.append({
                "status": "error",
                "detail": (
                    "Message processing failed. Check the server logs "
                    "for the diagnostic details."
                ),
            })

    # Return promptly with HTTP 200 so Meta does not repeatedly retry
    # successfully received webhook notifications.
    return {
        "status": "processed",
        "messages_found": len(messages),
        "results": results,
    }
