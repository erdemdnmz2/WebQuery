# DBA Application

## English

### Overview
This project is a database management and query analysis tool for SQL Server. It provides user authentication, query risk analysis, and notification features (email, Slack). It is built with Python and uses SQLAlchemy for database connections.

### Features
- User authentication and session management
- Query risk analysis (SQL injection, DDL, risky, performance)
- Email and Slack notifications
- Rate limiting for queries
- Multiple database/server support
- Multi-query support (execute multiple queries in one request)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/erdemdnmz2/WebQuery
   cd dba_application
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**
   - Edit `config.py` for your database servers, connection strings, email, and Slack settings.
   - Example server configuration:
     ```python
     SERVER_NAMES = [
         "YOUR_SERVER_NAME"
     ]
     DATABASE_URL = (
         "mssql+aioodbc://localhost/your_db"
         "?driver=ODBC+Driver+18+for+SQL+Server"
         "&trusted_connection=yes"
         "&TrustServerCertificate=yes"
     )
     ```
   - Set your email and Slack webhook credentials.

4. **Run the application**
   ```bash
   python main.py
   ```

### Usage

- Users can log in and execute SQL queries.
- Queries are analyzed for risks before execution.
- Notifications are sent for risky queries.
- Admins can approve or reject risky queries.
- **Multi-query:** You can execute multiple SQL queries in a single request. The system will analyze each query separately for risks and process them accordingly.

---

## Türkçe

### Genel Bakış
Bu proje, SQL Server için bir veritabanı yönetim ve sorgu analiz aracıdır. Kullanıcı doğrulama, sorgu risk analizi ve bildirim (email, Slack) özellikleri sunar. Python ile geliştirilmiştir ve veritabanı bağlantıları için SQLAlchemy kullanır.

### Özellikler
- Kullanıcı doğrulama ve oturum yönetimi
- Sorgu risk analizi (SQL injection, DDL, riskli, performans)
- E-posta ve Slack bildirimleri
- Sorgular için hız sınırlama
- Çoklu veritabanı/sunucu desteği
- Çoklu sorgu desteği (tek istekte birden fazla sorgu çalıştırabilirsiniz)

### Kurulum

1. **Projeyi klonlayın**
   ```bash
   git clone https://github.com/erdemdnmz2/WebQuery
   cd dba_application
   ```

2. **Bağımlılıkları yükleyin**
   ```bash
   pip install -r requirements.txt
   ```

3. **Konfigürasyon**
   - `config.py` dosyasını veritabanı sunucularınız, bağlantı stringleri, e-posta ve Slack ayarları için düzenleyin.
   - Sunucu örneği:
     ```python
     SERVER_NAMES = [
         "SUNUCU_ADINIZ"
     ]
     DATABASE_URL = (
         "mssql+aioodbc://localhost/veritabani_adiniz"
         "?driver=ODBC+Driver+18+for+SQL+Server"
         "&trusted_connection=yes"
         "&TrustServerCertificate=yes"
     )
     ```
   - E-posta ve Slack webhook bilgilerinizi girin.

4. **Uygulamayı çalıştırın**
   ```bash
   python main.py
   ```

### Kullanım

- Kullanıcılar giriş yapıp SQL sorguları çalıştırabilir.
- Sorgular çalıştırılmadan önce risk analizi yapılır.
- Riskli sorgular için bildirim gönderilir.
- Yöneticiler riskli sorguları onaylayabilir veya reddedebilir.
- **Çoklu sorgu:** Tek bir istekte birden fazla SQL sorgusu çalıştırabilirsiniz. Sistem her sorguyu ayrı ayrı risk analizi yaparak işler.

---

**For more details, check the code comments and configuration files. / Daha fazla bilgi için kod açıklamalarını ve konfigürasyon dosyalarını inceleyin.**
