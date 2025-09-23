import requests
from config import SLACK_URL, message_format

def send_to_slack(text: str, button_value: str = None):
    """
    Sends a message to Slack using Block Kit. 
    Can include an interactive button if button_text, button_value, and action_id are provided.
    """
    headers = {"Content-Type": "application/json; charset=utf-8"}
    
    # Base structure with the main text in a code block
    blocks = [
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_preformatted",
                    "elements": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ]
                }
            ]
        }
    ]

    if button_value:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Onay",
                        "emoji": True
                    },
                    "style": "primary", # Yeşil buton
                    "action_id": "query_action",
                    "value": button_value # The data to be sent back to your app
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Red",
                        "emoji": True
                    },
                    "style": "danger", # Kırmızı buton
                    "action_id": "reject_action",
                    "value": button_value # The data to be sent back to your app
                }
            ]
        })

    # The top-level 'text' is a fallback for notifications
    data = {
        "text": text,  # Fallback for notifications
        "blocks": blocks
    }
    
    requests.post(SLACK_URL, headers=headers, json=data)

def send_message_to_slack(text: str):
    headers = {"Content-Type" : "application/json; charset=utf-8"}
    data = {"text": f"```{text}```"}
    requests.post(SLACK_URL, headers=headers, json=data)

# import httpx

# async def send_to_slack(text: str):
#     headers = {"Content-Type": "application/json; charset=utf-8"}
#     data = {"text": text}
#     async with httpx.AsyncClient() as client:
#         await client.post(SLACK_URL, headers=headers, json=data)

# import httpx

# async def send_to_slack(text: str):
#     headers = {"Content-Type": "application/json; charset=utf-8"}
#     data = {"text": text}
#     async with httpx.AsyncClient() as client:
#         await client.post(SLACK_URL, headers=headers, json=data)