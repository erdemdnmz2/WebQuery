import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Slack Bot Token (xoxb-...)
# Mesaj göndermek ve API çağrıları yapmak için kullanılır
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

# Slack App Token (xapp-...)
# Socket Mode ile olayları dinlemek için kullanılır
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# Admin Kanal ID'si
# Onay mesajlarının gönderileceği kanal
SLACK_ADMIN_CHANNEL = os.getenv("SLACK_ADMIN_CHANNEL")

# Konfigürasyon kontrolü
if not all([SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_ADMIN_CHANNEL]):
    logger.warning("Slack entegrasyonu için gerekli ortam değişkenleri eksik")
