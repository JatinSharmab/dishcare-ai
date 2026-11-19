import httpx

from app.core.exceptions import BusinessError


class WhatsAppClient:
    def __init__(self, client: httpx.AsyncClient, phone_id: str, api_version: str):
        self.client = client
        self.path = f"/{api_version}/{phone_id}/messages"

    async def send(self, recipient: str, answer: str):
        try:
            response = await self.client.post(self.path, json={
                "messaging_product": "whatsapp", "to": recipient,
                "type": "text", "text": {"body": answer[:4096]},
            })
            response.raise_for_status()
        except httpx.HTTPError:
            raise BusinessError(502, "WHATSAPP_DELIVERY_UNCERTAIN", "Delivery could not be verified") from None
