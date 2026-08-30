import logging
from typing import Any

import httpx

from notification.config import SLACK_URL, approval_message_format, message_format
from slack_integration.schemas import create_approval_message

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, ):
        self.message_format = message_format
        self.approval_message_format = approval_message_format
        self.slack_url = SLACK_URL

    async def send_approval_notification(
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

    async def _send_message_to_slack(self, text: str | None = None, blocks: list[dict[str, Any]] | None = None) -> bool:
        """
        Send a message to Slack using httpx.AsyncClient.
        Returns True on success, False on failure.
        """
        if not self.slack_url:
            logger.warning("Slack webhook yapılandırılmamış; bildirim gönderilmedi")
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
                    logger.warning("Slack webhook isteği başarısız oldu: HTTP %d", resp.status_code)
                    return False
                return True
        except httpx.RequestError as exc:
            logger.warning("Slack webhook isteği başarısız oldu: %s", type(exc).__name__)
            return False
