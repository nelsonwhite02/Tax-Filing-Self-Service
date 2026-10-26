from typing import Any


class WhatsAppMessageParser:
    """
    Extracts useful message information from Meta WhatsApp webhook payloads.

    Supported incoming message types:
    - text
    - image
    - document
    - audio
    - interactive button replies
    - interactive list replies
    """

    @staticmethod
    def parse(payload: dict[str, Any]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                incoming_messages = value.get("messages", [])

                for message in incoming_messages:
                    parsed = WhatsAppMessageParser._parse_message(message)

                    if parsed:
                        messages.append(parsed)

        return messages

    @staticmethod
    def _parse_message(
        message: dict[str, Any],
    ) -> dict[str, Any] | None:

        message_type = message.get("type")

        result: dict[str, Any] = {
            "message_id": message.get("id"),
            "from": message.get("from"),
            "timestamp": message.get("timestamp"),
            "type": message_type,
        }

        # ------------------------------------------------------------
        # TEXT
        # ------------------------------------------------------------

        if message_type == "text":

            result["text"] = (
                message.get("text", {}).get("body")
            )

        # ------------------------------------------------------------
        # IMAGE
        # ------------------------------------------------------------

        elif message_type == "image":

            image = message.get("image", {})

            result["media_id"] = image.get("id")
            result["mime_type"] = image.get("mime_type")
            result["caption"] = image.get("caption")

            result["media_type"] = "image"

        # ------------------------------------------------------------
        # DOCUMENT
        # ------------------------------------------------------------

        elif message_type == "document":

            document = message.get("document", {})

            result["media_id"] = document.get("id")
            result["mime_type"] = document.get("mime_type")
            result["filename"] = document.get("filename")
            result["caption"] = document.get("caption")

            result["media_type"] = "document"

        # ------------------------------------------------------------
        # AUDIO
        # ------------------------------------------------------------

        elif message_type == "audio":

            audio = message.get("audio", {})

            result["media_id"] = audio.get("id")
            result["mime_type"] = audio.get("mime_type")
            result["voice"] = audio.get("voice", False)

            result["media_type"] = "audio"

        # ------------------------------------------------------------
        # INTERACTIVE
        # ------------------------------------------------------------

        elif message_type == "interactive":

            interactive = message.get("interactive", {})

            interactive_type = interactive.get("type")

            result["interactive_type"] = interactive_type

            if interactive_type == "button_reply":

                button_reply = interactive.get(
                    "button_reply",
                    {},
                )

                result["button_id"] = button_reply.get("id")
                result["button_title"] = button_reply.get("title")

                # Treat the button selection as a logical choice.
                result["selection_id"] = button_reply.get("id")
                result["selection_title"] = button_reply.get("title")

            elif interactive_type == "list_reply":

                list_reply = interactive.get(
                    "list_reply",
                    {},
                )

                result["list_id"] = list_reply.get("id")
                result["list_title"] = list_reply.get("title")
                result["list_description"] = list_reply.get(
                    "description"
                )

                # Treat the list selection as a logical choice.
                result["selection_id"] = list_reply.get("id")
                result["selection_title"] = list_reply.get("title")

        # ------------------------------------------------------------
        # UNSUPPORTED
        # ------------------------------------------------------------

        else:

            result["unsupported"] = True

        return result