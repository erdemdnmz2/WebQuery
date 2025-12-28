import os
from dotenv import load_dotenv

load_dotenv()

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
    print("UYARI: Slack entegrasyonu için gerekli environment değişkenleri eksik!")
    print("Lütfen .env dosyasında SLACK_BOT_TOKEN, SLACK_APP_TOKEN ve SLACK_ADMIN_CHANNEL tanımlı olduğundan emin olun.")