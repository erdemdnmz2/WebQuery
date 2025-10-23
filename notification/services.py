from notification.config import message_format, approval_message_format, SLACK_URL
import httpx


class NotificationService:
    def __init__(self):
        self.message_format = message_format
        self.approval_message_format = approval_message_format
        self.slack_url = SLACK_URL

    async def send_approval_notifivation(
        self,
        username,
        request_time,
        database_name,
        servername,
        risk_type,
        query,
    ) -> bool:
        message = self.approval_message_format.format(
            username=username,
            request_time=request_time,
            database_name=database_name,
            servername=servername,
            risk_type=risk_type,
            query=query,
        )

        return await self._send_message_to_slack(message)

    async def _send_message_to_slack(self, text: str) -> bool:
        """
        Send a message to Slack using httpx.AsyncClient.
        Returns True on success, False on failure.
        """
        if not self.slack_url:
            print("[Notification] SLACK_URL tanımlı değil. Mesaj gönderilmedi.")
            return False

        headers = {"Content-Type": "application/json; charset=utf-8"}
        MAX_LEN = 39000
        safe_text = text if len(text) <= MAX_LEN else (text[:MAX_LEN] + "\n... (truncated)")
        payload = {"text": safe_text}

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(self.slack_url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    print(f"[Notification] Slack webhook hatası: {resp.status_code} - {resp.text}")
                    return False
                return True
        except httpx.RequestError as e:
            print(f"[Notification] Slack isteği başarısız: {type(e).__name__}: {e}")
            return False

