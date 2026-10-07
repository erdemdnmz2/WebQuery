import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Slack Bot Token (xoxb-...)
# Used to send messages and make API calls.
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

# Slack App Token (xapp-...)
# Used to listen for events through Socket Mode.
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# Admin Kanal ID'si
# Channel where approval messages are sent.
SLACK_ADMIN_CHANNEL = os.getenv("SLACK_ADMIN_CHANNEL")

# Configuration check.
if not all([SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_ADMIN_CHANNEL]):
    logger.warning("Required environment variables for Slack integration are missing")
