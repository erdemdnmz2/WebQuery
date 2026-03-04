from typing import List, Dict, Any

def create_approval_message(request_id: str, username: str, machine_name: str, database: str, query: str, risk_score: str) -> List[Dict[str, Any]]:
    """
    Slack için butonlu onay mesajı bloklarını oluşturur.
    request_id (UUID) butonların 'value' kısmına gizlenir.
    """
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "⚠️ Kritik Sorgu Onayı Bekleniyor",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Kullanıcı:*\n{username}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Makine:*\n{machine_name}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Veritabanı:*\n{database}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Risk Skoru:*\n{risk_score}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Sorgu:*\n```{query}```"
            }
        },
        {
            "type": "actions",
            "block_id": "approval_actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "▶️ Çalıştır",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": str(request_id),
                    "action_id": "execute_query"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Reddet",
                        "emoji": True
                    },
                    "style": "danger",
                    "value": str(request_id),
                    "action_id": "reject_query"
                }
            ]
        }
    ]
