from typing import Any

# Slack rejects a `section` block whose text exceeds 3000 characters, and it
# rejects the *whole* payload - so an over-long query used to mean the approval
# request never arrived at all, with only a log line to show for it. The budget
# below leaves room for the "*Sorgu:*", the code fence and the truncation note.
_SLACK_SECTION_LIMIT = 3000
_QUERY_TEXT_BUDGET = 2700


def _query_block_text(request_id: str, query: str) -> str:
    """Render the query for Slack, trimmed to what a section block accepts.

    The full statement is sent when it fits: an approver cannot judge a query
    they cannot read (ADR-0019). When it does not fit, the notification carries
    the opening of the statement and sends the approver to the WebQuery
    approval queue for the rest, rather than dropping the request.
    """
    if len(query) <= _QUERY_TEXT_BUDGET:
        return f"*Sorgu:*\n```{query}```"
    return (
        f"*Sorgu:* _(ilk {_QUERY_TEXT_BUDGET} karakter; tamamı için "
        f"WebQuery onay kuyruğuna bakın — istek {request_id})_\n"
        f"```{query[:_QUERY_TEXT_BUDGET]}```"
    )


def create_approval_message(request_id: str, username: str, machine_name: str, database: str, query: str, risk_score: str) -> list[dict[str, Any]]:
    """
    Slack için butonlu onay mesajı bloklarını oluşturur.
    request_id (UUID) butonların 'value' kısmına gizlenir.

    Sorgu metninin tamamının Slack'e çıkması bilinçli bir karardır; gerekçesi
    ve sınırları `docs/adr/ADR-0019-slack-approval-payload.md` içindedir.
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
                "text": _query_block_text(request_id, query)
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
                        "text": "✅ Onayla",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": str(request_id),
                    "action_id": "approve_with_results"
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
