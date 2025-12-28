from notification.config import message_format, approval_message_format, SLACK_URL
from slack_integration.schemas import create_approval_message
import httpx
from typing import List, Dict, Any, Optional


class NotificationService:
    def __init__(self, ):
        self.message_format = message_format
        self.approval_message_format = approval_message_format
        self.slack_url = SLACK_URL

    async def send_approval_notifivation(
        self,
        request_id,
        username,
        request_time,
        database_name,
        servername,
        risk_type,
        query,
    ) -> bool:
        blocks = create_approval_message(
            request_id=request_id,
            username=username,
            machine_name=servername,
            database=database_name,
            query=query,
            risk_score=risk_type
        )

        return await self._send_message_to_slack(blocks=blocks)

    async def _send_message_to_slack(self, text: str = None, blocks: List[Dict[str, Any]] = None) -> bool:
        """
        Send a message to Slack using httpx.AsyncClient.
        Returns True on success, False on failure.
        """
        if not self.slack_url:
            print("[Notification] SLACK_URL tanımlı değil. Mesaj gönderilmedi.")
            return False

        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {}

        if text:
            MAX_LEN = 39000
            safe_text = text if len(text) <= MAX_LEN else (text[:MAX_LEN] + "\n... (truncated)")
            payload["text"] = safe_text
        
        if blocks:
            payload["blocks"] = blocks
            
        if not payload:
            return False

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

