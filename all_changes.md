# WebQuery B2B Güvenlik Sıkılaştırması & SaaS Migrasyonu - Değişiklik Raporu

Bu rapor, WebQuery platformunun B2B SaaS mimarisine geçişi, sıfır güven (zero-trust) ilkelerine dayalı güvenlik sıkılaştırmaları, durumsuz kimlik doğrulama, merkezi hata yönetimi, AST tabanlı sorgu güvenliği analizi ve gelişmiş denetim loglaması süreçlerinde yapılan tüm değişiklikleri modüler bir şekilde sunmaktadır.

## 🏗️ Mimari Genel Bakış (Neler Yapıldı?)

WebQuery uygulaması, kurumsal düzeyde (B2B) güvenli bir SQL yürütme platformuna dönüştürülmüştür. Bu kapsamda uygulanan temel mimari kararlar şunlardır:

1. **Merkezi Servis Hesabı Mimarisi (Centralized Service Account):**
   * Bireysel kullanıcıların hedef veritabanları için parola saklaması zorunluluğu kaldırılmıştır.
   * Bağlantılar, güvenli çevre değişkenlerinde tanımlanan kısıtlı yetkilere sahip merkezi servis hesapları (`CENTRAL_DB_USER` / `CENTRAL_DB_PASSWORD`) aracılığıyla dinamik olarak kurulur.
   * Yetkilendirme sıfır güven ilkesine dayanır ve her işlem detaylı bir şekilde `ActionLogging` denetim logu (audit trail) ile kaydedilir.

2. **Durumsuz (Stateless) Cookie Tabanlı JWT Yetkilendirmesi:**
   * Redis tabanlı parola önbelleğe alma mekanizması kaldırılmıştır.
   * Oturum yönetimi tamamen durumsuz (stateless) hale getirilerek, kriptografik olarak imzalanmış JWT token'ları güvenli, istemci tarafında değiştirilemeyen `HttpOnly` çerezlerinde (cookies) taşınmaya başlanmıştır.

3. **Gelişmiş Engine Cache ve Bağlantı Havuzu (Connection Pooling):**
   * Hedef veritabanlarına kurulan bağlantılar, asenkron bir `EngineCache` yapısı ile yönetilir.
   * `pool_size=0` olarak ayarlanarak sorgu bittiği anda veritabanı sunucusundaki boşta (idle) bağlantılar hemen kapatılır.
   * LRU (Least Recently Used) tahliye algoritması ve arka planda çalışan bir TTL (Time-To-Live) temizlik döngüsüyle kullanılmayan bağlantılar temizlenirken, o anda aktif sorgu çalıştıran (`checkedout > 0`) motorlar güvenle korunur.

4. **AST (Soyut Sözdizim Ağacı) Tabanlı Sorgu Güvenliği Analizi:**
   * Sorgular çalıştırılmadan önce `sqlglot` kütüphanesi kullanılarak parse edilir ve Soyut Sözdizim Ağacı (AST) seviyesinde analiz edilir.
   * Hedef veritabanının lehçesine (`tsql`, `mysql`, `postgres`) göre SQL Injection, yapısal DDL değişiklikleri (`DROP`, `ALTER`), koşulsuz riskli DML işlemleri (`WHERE` içermeyen `DELETE`/`UPDATE`) ve performans anomalileri (3'ten fazla join, indexes arama) otomatik tespit edilerek admin onayına yönlendirilir.

5. **Uçtan Uca Trace ID (İstek İzleme) ve Denetim Günlüğü:**
   * `TraceMiddleware` aracılığıyla her API isteğine benzersiz bir `Trace ID` (UUID) atanır ve `X-Request-ID` yanıt başlığı olarak istemciye sunulur.
   * Python `contextvars` kütüphanesi kullanılarak Trace ID ve Kullanıcı ID bilgileri, kod içinde parametre olarak taşınmaya gerek kalmaksızın tüm log yazıcılara (logging handlers) dinamik olarak bağlanır.

6. **Merkezi Hata Yönetimi ve Hata Dönüştürme (Exception Translation Pattern):**
   * Veritabanı ve altyapı seviyesindeki ham hatalar, servis sınırında yakalanarak anlamlı domain hatalarına (`WorkspaceNotFoundError`, `QueryExecutionError` vb.) dönüştürülür.
   * Küresel bir hata yakalayıcı (`exception_handler`), bu domain hatalarını yakalayarak detaylı trace logunu sisteme yazar ve istemciye sadece güvenli, standartlaştırılmış bir JSON hatası (`success: false`, `error_code`, `message`, `trace_id`) döner.

7. **Kapsamlı Test Altyapısı (Test Suite):**
   * Tüm bu katmanları (`conftest.py`, `pytest` entegrasyonu) SQLite asenkron bellek içi veritabanı (`sqlite+aiosqlite:///:memory:`) kullanarak test eden uçtan uca asenkron entegrasyon test suiti kurulmuştur.


## 📌 İçindekiler (Değişiklik Gösterge Paneli)
Aşağıdaki modüler yapıyı kullanarak ilgili kategorideki dosya değişikliklerini, Git diff'lerini ve dosya içeriklerini detaylıca inceleyebilirsiniz:

### Kategori 1: Ortak Altyapı ve Yardımcı Sınıflar (Common Core & Exceptions)
- [web_api/common/exceptions.py](#web_apicommonexceptionspy)
- [web_api/common/logging_config.py](#web_apicommonlogging_configpy)
- [web_api/common/limiter.py](#web_apicommonlimiterpy)
- [web_api/common/security.py](#web_apicommonsecuritypy)
- [web_api/common/__init__.py](#web_apicommon__init__py)

### Kategori 2: Güvenlik, Kimlik Doğrulama ve Middleware Katmanı (Security, Auth & Middlewares)
- [web_api/middlewares/trace_middleware.py](#web_apimiddlewarestrace_middlewarepy)
- [web_api/middlewares/auth_middleware.py](#web_apimiddlewaresauth_middlewarepy)
- [web_api/authentication/exceptions.py](#web_apiauthenticationexceptionspy)
- [web_api/authentication/config.py](#web_apiauthenticationconfigpy)
- [web_api/authentication/router.py](#web_apiauthenticationrouterpy)
- [web_api/authentication/services.py](#web_apiauthenticationservicespy)
- [web_api/authentication/__init__.py](#web_apiauthentication__init__py)

### Kategori 3: Veritabanı Erişim Katmanı ve Modeller (Database Provider, Models & Config)
- [web_api/database_provider/config.py](#web_apidatabase_providerconfigpy)
- [web_api/database_provider/database.py](#web_apidatabase_providerdatabasepy)
- [web_api/app_database/config.py](#web_apiapp_databaseconfigpy)
- [web_api/app_database/app_database.py](#web_apiapp_databaseapp_databasepy)
- [web_api/app_database/models.py](#web_apiapp_databasemodelspy)
- [web_api/app_database/__init__.py](#web_apiapp_database__init__py)

### Kategori 4: Sorgu Analizi ve Güvenli Yürütme (Query Execution, AST & Auditing)
- [web_api/query_execution/exceptions.py](#web_apiquery_executionexceptionspy)
- [web_api/query_execution/query_analyzer.py](#web_apiquery_executionquery_analyzerpy)
- [web_api/query_execution/services.py](#web_apiquery_executionservicespy)
- [web_api/query_execution/router.py](#web_apiquery_executionrouterpy)
- [web_api/query_execution/schemas.py](#web_apiquery_executionschemaspy)
- [web_api/query_execution/__init__.py](#web_apiquery_execution__init__py)

### Kategori 5: Çalışma Alanları Yönetimi (Workspace Management)
- [web_api/workspaces/exceptions.py](#web_apiworkspacesexceptionspy)
- [web_api/workspaces/router.py](#web_apiworkspacesrouterpy)
- [web_api/workspaces/services.py](#web_apiworkspacesservicespy)
- [web_api/workspaces/schemas.py](#web_apiworkspacesschemaspy)
- [web_api/workspaces/__init__.py](#web_apiworkspaces__init__py)

### Kategori 6: Yönetici Onay ve Veritabanı İşlemleri (Admin Operations & Approvals)
- [web_api/admin/exceptions.py](#web_apiadminexceptionspy)
- [web_api/admin/router.py](#web_apiadminrouterpy)
- [web_api/admin/services.py](#web_apiadminservicespy)
- [web_api/admin/schemas.py](#web_apiadminschemaspy)
- [web_api/admin/__init__.py](#web_apiadmin__init__py)

### Kategori 7: Ön Yüz (React/TypeScript Frontend) Ekranları
- [frontend/pages/Login.tsx](#frontendpageslogintsx)
- [frontend/pages/Register.tsx](#frontendpagesregistertsx)
- [frontend/pages/SqlEditor.tsx](#frontendpagessqleditortsx)
- [frontend/pages/Admin.tsx](#frontendpagesadmintsx)

### Kategori 8: Kapsamlı Entegrasyon ve Güvenlik Testleri (Testing Infrastructure)
- [web_api/tests/conftest.py](#web_apitestsconftestpy)
- [web_api/tests/integration/test_auth_api.py](#web_apitestsintegrationtest_auth_apipy)
- [web_api/tests/integration/test_admin_api.py](#web_apitestsintegrationtest_admin_apipy)
- [web_api/tests/integration/test_error_handling_and_trace.py](#web_apitestsintegrationtest_error_handling_and_tracepy)
- [web_api/tests/integration/test_notifications_and_slack.py](#web_apitestsintegrationtest_notifications_and_slackpy)
- [web_api/tests/integration/test_query_execution.py](#web_apitestsintegrationtest_query_executionpy)
- [web_api/tests/integration/test_workspaces.py](#web_apitestsintegrationtest_workspacespy)

### Kategori 9: Proje Yapılandırma ve Kök Dosyalar (Configuration & Root Setup)
- [web_api/dependencies.py](#web_apidependenciespy)
- [web_api/entrypoint.sh](#web_apientrypointsh)
- [.gitignore](#gitignore)
- [.env.example](#envexample)
- [README.md](#readmemd)
- [web_api/session/session_cache.py](#web_apisessionsession_cachepy)


---

## 🔍 Detaylı Dosya Değişiklikleri ve Kod Kod Diffs
> **İpucu:** Dosyaların satır satır değişikliklerini (Git Diff) ve tam kod içeriklerini görmek için ilgili başlık altındaki katlanabilir **Detayları Göster** butonlarına tıklayabilirsiniz. Bu sayede 7.000 satırdan uzun olan bu belgede kaybolmadan sadece ilgilendiğiniz kod bölümlerini kolayca inceleyebilirsiniz.


### 📂 Kategori 1: Ortak Altyapı ve Yardımcı Sınıflar (Common Core & Exceptions)
---

#### <a name="web_apicommonexceptionspy"></a> `web_api/common/exceptions.py`
**Açıklama:** Yeni eklenen bu modül, tüm servis katmanında kullanılacak olan `BaseServiceException` sınıfını tanımlar. Bu sınıf sayesinde düşük seviyeli altyapı hataları (SQLAlchemy, ODBC, network vb.) yakalanarak istemciye güvenli, standartlaştırılmış ve enterprise hata kodları içeren (`success: False`, `error_code`, `message`, `trace_id`) nesneler olarak dönüştürülür.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/common/exceptions.py b/web_api/common/exceptions.py
new file mode 100644
index 0000000..bd257c9
--- /dev/null
+++ b/web_api/common/exceptions.py
@@ -0,0 +1,23 @@
+"""
+Common Exceptions Module
+Contains the base service exception class for modular exception translation.
+"""
+from typing import Optional
+
+class BaseServiceException(Exception):
+    """
+    Base exception class for all business/service layer errors.
+    
+    Attributes:
+        message: Safe error message shown to the client.
+        status_code: HTTP status code mapped to this exception.
+        code: Enterprise error code string (e.g., WORKSPACE_NOT_FOUND).
+        original_exception: Underlying infrastructure exception (e.g., SQLAlchemyError).
+    """
+    status_code: int = 500
+    code: str = "INTERNAL_SERVER_ERROR"
+
+    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
+        self.message: str = message
+        self.original_exception: Optional[Exception] = original_exception
+        super().__init__(self.message)
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (exceptions.py)</summary>

```python
"""
Common Exceptions Module
Contains the base service exception class for modular exception translation.
"""
from typing import Optional

class BaseServiceException(Exception):
    """
    Base exception class for all business/service layer errors.
    
    Attributes:
        message: Safe error message shown to the client.
        status_code: HTTP status code mapped to this exception.
        code: Enterprise error code string (e.g., WORKSPACE_NOT_FOUND).
        original_exception: Underlying infrastructure exception (e.g., SQLAlchemyError).
    """
    status_code: int = 500
    code: str = "INTERNAL_SERVER_ERROR"

    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        self.message: str = message
        self.original_exception: Optional[Exception] = original_exception
        super().__init__(self.message)

```
</details>



#### <a name="web_apicommonlogging_configpy"></a> `web_api/common/logging_config.py`
**Açıklama:** `contextvars` kütüphanesini kullanarak istek yaşam döngüsü boyunca `Trace ID` ve `Kullanıcı ID` bilgilerini otomatik olarak taşıyan ve log formatına (`[Trace: ...] [User: ...]`) dinamik olarak enjekte eden özel yapılandırılmış log sistemini kurar.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/common/logging_config.py b/web_api/common/logging_config.py
new file mode 100644
index 0000000..c1daa4e
--- /dev/null
+++ b/web_api/common/logging_config.py
@@ -0,0 +1,51 @@
+"""
+Logging Configuration Module
+Configures structured logging with dynamic Trace ID and User ID tracking using contextvars.
+"""
+import logging
+from contextvars import ContextVar
+from typing import Any
+
+# Context variables to hold Request Trace ID and User ID throughout the request lifecycle
+trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
+user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
+
+class ContextFilter(logging.Filter):
+    """
+    logging.Filter that injects trace_id and user_id context variables into every log record.
+    """
+    def filter(self, record: logging.LogRecord) -> bool:
+        record.trace_id = trace_id_var.get()
+        record.user_id = user_id_var.get()
+        return True
+
+def setup_logging() -> None:
+    """
+    Initializes and configures the logging system with a custom formatter and context filters.
+    """
+    log_format: str = "%(asctime)s [%(levelname)s] [Trace: %(trace_id)s] [User: %(user_id)s] %(name)s: %(message)s"
+    
+    # Configure root logger
+    root_logger = logging.getLogger()
+    root_logger.setLevel(logging.INFO)
+    
+    # Clear existing handlers to prevent duplicate logs in some environments
+    if root_logger.hasHandlers():
+        root_logger.handlers.clear()
+        
+    # Console handler
+    console_handler = logging.StreamHandler()
+    console_handler.setLevel(logging.INFO)
+    
+    # Custom formatter
+    formatter = logging.Formatter(log_format)
+    console_handler.setFormatter(formatter)
+    
+    # Inject ContextFilter
+    context_filter = ContextFilter()
+    console_handler.addFilter(context_filter)
+    
+    root_logger.addHandler(console_handler)
+    
+    # Suppress verbose loggers from libraries if needed
+    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (logging_config.py)</summary>

```python
"""
Logging Configuration Module
Configures structured logging with dynamic Trace ID and User ID tracking using contextvars.
"""
import logging
from contextvars import ContextVar
from typing import Any

# Context variables to hold Request Trace ID and User ID throughout the request lifecycle
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

class ContextFilter(logging.Filter):
    """
    logging.Filter that injects trace_id and user_id context variables into every log record.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        record.user_id = user_id_var.get()
        return True

def setup_logging() -> None:
    """
    Initializes and configures the logging system with a custom formatter and context filters.
    """
    log_format: str = "%(asctime)s [%(levelname)s] [Trace: %(trace_id)s] [User: %(user_id)s] %(name)s: %(message)s"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers to prevent duplicate logs in some environments
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Custom formatter
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    
    # Inject ContextFilter
    context_filter = ContextFilter()
    console_handler.addFilter(context_filter)
    
    root_logger.addHandler(console_handler)
    
    # Suppress verbose loggers from libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

```
</details>



#### <a name="web_apicommonlimiterpy"></a> `web_api/common/limiter.py`
**Açıklama:** `slowapi` kütüphanesini kullanan ve tüm FastAPI router'ları tarafından paylaşılan merkezi hız sınırlayıcı (Rate Limiter) nesnesini tanımlar.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/common/limiter.py b/web_api/common/limiter.py
new file mode 100644
index 0000000..8cb1599
--- /dev/null
+++ b/web_api/common/limiter.py
@@ -0,0 +1,9 @@
+"""
+Rate Limiter Configuration Module
+Defines a central, shared Limiter instance to be used across all routers.
+"""
+from slowapi import Limiter
+from slowapi.util import get_remote_address
+
+# Define a shared limiter instance
+limiter: Limiter = Limiter(key_func=get_remote_address)
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (limiter.py)</summary>

```python
"""
Rate Limiter Configuration Module
Defines a central, shared Limiter instance to be used across all routers.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Define a shared limiter instance
limiter: Limiter = Limiter(key_func=get_remote_address)

```
</details>



#### <a name="web_apicommonsecuritypy"></a> `web_api/common/security.py`
**Açıklama:** Veritabanı sorgu sonuçlarındaki hassas sütunları (şifreler, e-postalar, kredi kartları, telefon numaraları, TCKN vb.) admin olmayan kullanıcılar için dinamik maskeleme (masking) algoritmalarıyla gizleyen ve geçici güvenli kimlik bilgileri üreten yardımcı modül.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/common/security.py b/web_api/common/security.py
new file mode 100644
index 0000000..959072a
--- /dev/null
+++ b/web_api/common/security.py
@@ -0,0 +1,91 @@
+"""
+Security Utilities Module
+Contains helpers for dynamic data masking and secure credential generation.
+"""
+import re
+import secrets
+import string
+from typing import List, Dict, Any, Set
+
+def generate_secure_credentials() -> tuple[str, str]:
+    """
+    Generates a secure random database username and a strong 32-character password.
+    
+    Returns:
+        tuple[str, str]: (username, password)
+    """
+    # Generate unique 8-character hex suffix for username
+    suffix = secrets.token_hex(4)
+    username = f"webquery_user_{suffix}"
+    
+    # Generate strong 32-character password
+    alphabet = string.ascii_letters + string.digits + "!@#$%^*()-_=+"
+    password = "".join(secrets.choice(alphabet) for _ in range(32))
+    
+    return username, password
+
+def mask_result_set(data: List[Dict[str, Any]], mask_columns: Set[str]) -> List[Dict[str, Any]]:
+    """
+    Masks sensitive columns in query results for non-admin users.
+    
+    Args:
+        data: The query result rows as a list of dictionaries.
+        mask_columns: A set of column names (lowercase) that should be masked.
+        
+    Returns:
+        List[Dict[str, Any]]: The masked result set.
+    """
+    if not data or not mask_columns:
+        return data
+        
+    # Convert mask columns to lowercase for case-insensitive matching
+    lower_mask_cols = {col.lower() for col in mask_columns}
+    
+    masked_data = []
+    for row in data:
+        masked_row = {}
+        for col_name, val in row.items():
+            col_lower = col_name.lower()
+            
+            if col_lower in lower_mask_cols and val is not None:
+                val_str = str(val)
+                # Apply dynamic masking rules based on value characteristics or column names
+                if "@" in val_str and "." in val_str:
+                    # Email masking: u***@domain.com
+                    parts = val_str.split("@", 1)
+                    username_part = parts[0]
+                    domain_part = parts[1]
+                    if len(username_part) > 1:
+                        masked_val = f"{username_part[0]}***@{domain_part}"
+                    else:
+                        masked_val = f"***@{domain_part}"
+                elif re.search(r"\d{12,19}", re.sub(r"[-\s]", "", val_str)):
+                    # Credit card masking: ****-****-****-1234
+                    digits_only = re.sub(r"[-\s]", "", val_str)
+                    last_4 = digits_only[-4:]
+                    masked_val = f"****-****-****-{last_4}"
+                elif col_lower in {"password", "pass_hash", "password_hash", "secret", "api_key", "private_key"}:
+                    # Full secret mask
+                    masked_val = "********"
+                elif re.match(r"^\+?[1-9]\d{1,14}$", re.sub(r"[-\s\(\)]", "", val_str)) and len(re.sub(r"[-\s\(\)]", "", val_str)) >= 7:
+                    # Phone masking: ***-***-1234
+                    clean_phone = re.sub(r"[-\s\(\)]", "", val_str)
+                    last_4 = clean_phone[-4:]
+                    masked_val = f"***-***-{last_4}"
+                elif len(val_str) >= 11 and val_str.isdigit() and (col_lower in {"tckn", "tc_kimlik", "ssn", "national_id"}):
+                    # TCKN/SSN mask: *******1234
+                    last_4 = val_str[-4:]
+                    masked_val = f"*******{last_4}"
+                else:
+                    # Generic partial masking: retains first and last char, masks the rest
+                    if len(val_str) > 2:
+                        masked_val = f"{val_str[0]}{'*' * (len(val_str) - 2)}{val_str[-1]}"
+                    else:
+                        masked_val = "**"
+            else:
+                masked_val = val
+                
+            masked_row[col_name] = masked_val
+        masked_data.append(masked_row)
+        
+    return masked_data
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (security.py)</summary>

```python
"""
Security Utilities Module
Contains helpers for dynamic data masking and secure credential generation.
"""
import re
import secrets
import string
from typing import List, Dict, Any, Set

def generate_secure_credentials() -> tuple[str, str]:
    """
    Generates a secure random database username and a strong 32-character password.
    
    Returns:
        tuple[str, str]: (username, password)
    """
    # Generate unique 8-character hex suffix for username
    suffix = secrets.token_hex(4)
    username = f"webquery_user_{suffix}"
    
    # Generate strong 32-character password
    alphabet = string.ascii_letters + string.digits + "!@#$%^*()-_=+"
    password = "".join(secrets.choice(alphabet) for _ in range(32))
    
    return username, password

def mask_result_set(data: List[Dict[str, Any]], mask_columns: Set[str]) -> List[Dict[str, Any]]:
    """
    Masks sensitive columns in query results for non-admin users.
    
    Args:
        data: The query result rows as a list of dictionaries.
        mask_columns: A set of column names (lowercase) that should be masked.
        
    Returns:
        List[Dict[str, Any]]: The masked result set.
    """
    if not data or not mask_columns:
        return data
        
    # Convert mask columns to lowercase for case-insensitive matching
    lower_mask_cols = {col.lower() for col in mask_columns}
    
    masked_data = []
    for row in data:
        masked_row = {}
        for col_name, val in row.items():
            col_lower = col_name.lower()
            
            if col_lower in lower_mask_cols and val is not None:
                val_str = str(val)
                # Apply dynamic masking rules based on value characteristics or column names
                if "@" in val_str and "." in val_str:
                    # Email masking: u***@domain.com
                    parts = val_str.split("@", 1)
                    username_part = parts[0]
                    domain_part = parts[1]
                    if len(username_part) > 1:
                        masked_val = f"{username_part[0]}***@{domain_part}"
                    else:
                        masked_val = f"***@{domain_part}"
                elif re.search(r"\d{12,19}", re.sub(r"[-\s]", "", val_str)):
                    # Credit card masking: ****-****-****-1234
                    digits_only = re.sub(r"[-\s]", "", val_str)
                    last_4 = digits_only[-4:]
                    masked_val = f"****-****-****-{last_4}"
                elif col_lower in {"password", "pass_hash", "password_hash", "secret", "api_key", "private_key"}:
                    # Full secret mask
                    masked_val = "********"
                elif re.match(r"^\+?[1-9]\d{1,14}$", re.sub(r"[-\s\(\)]", "", val_str)) and len(re.sub(r"[-\s\(\)]", "", val_str)) >= 7:
                    # Phone masking: ***-***-1234
                    clean_phone = re.sub(r"[-\s\(\)]", "", val_str)
                    last_4 = clean_phone[-4:]
                    masked_val = f"***-***-{last_4}"
                elif len(val_str) >= 11 and val_str.isdigit() and (col_lower in {"tckn", "tc_kimlik", "ssn", "national_id"}):
                    # TCKN/SSN mask: *******1234
                    last_4 = val_str[-4:]
                    masked_val = f"*******{last_4}"
                else:
                    # Generic partial masking: retains first and last char, masks the rest
                    if len(val_str) > 2:
                        masked_val = f"{val_str[0]}{'*' * (len(val_str) - 2)}{val_str[-1]}"
                    else:
                        masked_val = "**"
            else:
                masked_val = val
                
            masked_row[col_name] = masked_val
        masked_data.append(masked_row)
        
    return masked_data

```
</details>



#### <a name="web_apicommon__init__py"></a> `web_api/common/__init__.py`
**Açıklama:** `common` paketi altındaki temel bileşenleri dışa aktaran başlatma modülü.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/common/__init__.py b/web_api/common/__init__.py
new file mode 100644
index 0000000..9f432c7
--- /dev/null
+++ b/web_api/common/__init__.py
@@ -0,0 +1,6 @@
+from .exceptions import BaseServiceException
+from .logging_config import setup_logging
+from .limiter import limiter
+
+__all__ = ["BaseServiceException", "setup_logging", "limiter"]
+
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (__init__.py)</summary>

```python
from .exceptions import BaseServiceException
from .logging_config import setup_logging
from .limiter import limiter

__all__ = ["BaseServiceException", "setup_logging", "limiter"]


```
</details>




### 📂 Kategori 2: Güvenlik, Kimlik Doğrulama ve Middleware Katmanı (Security, Auth & Middlewares)
---

#### <a name="web_apimiddlewarestrace_middlewarepy"></a> `web_api/middlewares/trace_middleware.py`
**Açıklama:** Uygulamaya gelen her HTTP isteğine benzersiz bir UUID (`Trace ID`) atayan, bu ID'yi log context'ine bağlayan, istek çalışma süresini ölçerek loglayan ve yanıt başlıklarında (`X-Request-ID`) istemciye dönen middleware.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/middlewares/trace_middleware.py b/web_api/middlewares/trace_middleware.py
new file mode 100644
index 0000000..0581fa7
--- /dev/null
+++ b/web_api/middlewares/trace_middleware.py
@@ -0,0 +1,56 @@
+"""
+Trace Middleware Module
+Generates a unique Trace ID for every request, logs request metrics, and exposes the ID in response headers.
+"""
+import time
+import uuid
+import logging
+from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
+from starlette.responses import Response
+from fastapi import Request
+
+from common.logging_config import trace_id_var
+
+logger = logging.getLogger("web_api.trace")
+
+class TraceMiddleware(BaseHTTPMiddleware):
+    """
+    Middleware that establishes a unique Trace ID (Request ID) for tracking and auditing.
+    Logs request initiation, completion duration, and status code.
+    """
+    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
+        # 1. Resolve Trace ID (Check if client/gateway passed X-Request-ID, otherwise generate)
+        request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())
+        request.state.request_id = request_id
+        
+        # 2. Set Trace ID in contextvars for logging
+        trace_token = trace_id_var.set(request_id)
+        
+        # 3. Log request initiation
+        logger.info(f"Request started: {request.method} {request.url.path}")
+        
+        start_time: float = time.time()
+        try:
+            response: Response = await call_next(request)
+            
+            # 4. Measure and log request completion
+            process_time: float = (time.time() - start_time) * 1000
+            logger.info(
+                f"Request completed: {request.method} {request.url.path} - "
+                f"Status: {response.status_code} - Duration: {process_time:.2f}ms"
+            )
+            
+            # 5. Expose Trace ID in response headers
+            response.headers["X-Request-ID"] = request_id
+            return response
+        except Exception as e:
+            process_time: float = (time.time() - start_time) * 1000
+            logger.error(
+                f"Request crashed: {request.method} {request.url.path} - "
+                f"Error: {type(e).__name__} - Duration: {process_time:.2f}ms",
+                exc_info=e
+            )
+            raise e
+        finally:
+            # 6. Reset contextvars to prevent memory leaks or context contamination
+            trace_id_var.reset(trace_token)
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (trace_middleware.py)</summary>

```python
"""
Trace Middleware Module
Generates a unique Trace ID for every request, logs request metrics, and exposes the ID in response headers.
"""
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from fastapi import Request

from common.logging_config import trace_id_var

logger = logging.getLogger("web_api.trace")

class TraceMiddleware(BaseHTTPMiddleware):
    """
    Middleware that establishes a unique Trace ID (Request ID) for tracking and auditing.
    Logs request initiation, completion duration, and status code.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Resolve Trace ID (Check if client/gateway passed X-Request-ID, otherwise generate)
        request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 2. Set Trace ID in contextvars for logging
        trace_token = trace_id_var.set(request_id)
        
        # 3. Log request initiation
        logger.info(f"Request started: {request.method} {request.url.path}")
        
        start_time: float = time.time()
        try:
            response: Response = await call_next(request)
            
            # 4. Measure and log request completion
            process_time: float = (time.time() - start_time) * 1000
            logger.info(
                f"Request completed: {request.method} {request.url.path} - "
                f"Status: {response.status_code} - Duration: {process_time:.2f}ms"
            )
            
            # 5. Expose Trace ID in response headers
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            process_time: float = (time.time() - start_time) * 1000
            logger.error(
                f"Request crashed: {request.method} {request.url.path} - "
                f"Error: {type(e).__name__} - Duration: {process_time:.2f}ms",
                exc_info=e
            )
            raise e
        finally:
            # 6. Reset contextvars to prevent memory leaks or context contamination
            trace_id_var.reset(trace_token)

```
</details>



#### <a name="web_apimiddlewaresauth_middlewarepy"></a> `web_api/middlewares/auth_middleware.py`
**Açıklama:** Stateless (durumsuz) kimlik doğrulama mimarisine geçiş kapsamında, JWT erişim token'ını Authorization header'ı yerine daha güvenli olan `HttpOnly` çerezlerinden (cookies) okuyacak şekilde güncellenen ve kullanıcı kimlik bilgilerini istek durumuna (request state) bağlayan middleware.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/middlewares/auth_middleware.py b/web_api/middlewares/auth_middleware.py
index 3f08449..07b5ffe 100644
--- a/web_api/middlewares/auth_middleware.py
+++ b/web_api/middlewares/auth_middleware.py
@@ -7,49 +7,33 @@ from starlette.middleware.base import RequestResponseEndpoint
 from starlette.responses import Response as StarletteResponse
 from starlette.responses import RedirectResponse
 from fastapi import Request
+import os
 from authentication.services import verify_token, get_user_id_from_payload
-from dependencies import get_session_cache
 from fastapi.exceptions import HTTPException
 
 class AuthMiddleware(BaseHTTPMiddleware):
     """
-    JWT token ve session doğrulama middleware'i
+    JWT token validation middleware.
     
-    Her request'te:
-        1. Public endpoint kontrolü (login, register)
-        2. Cookie'den JWT token alınır
-        3. Token doğrulanır
-        4. Session geçerliliği kontrol edilir
-        5. Token/session geçersizse redirect veya 401 döner
-    
-    Public Endpoints (authentication bypass):
-        - /login, /register
-        - /api/login, /api/register
-    
-    Error Handling:
-        - API endpoint'leri: 401 JSON response
-        - Web sayfaları: /login'e redirect (cookie silme ile)
+    For every request:
+        1. Public endpoint check (login, register, health)
+        2. Retrieves JWT token from access_token cookie
+        3. Validates the token
+        4. If invalid/missing, responds with 401 (for APIs) or redirects to /login (for web pages)
     """
     
     async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
         """
-        Request'i işler, authentication kontrolü yapar
+        Processes the request, checking authentication.
         
         Args:
-            request: Gelen HTTP request
-            call_next: Sonraki middleware/endpoint handler
+            request: The incoming HTTP request.
+            call_next: The next middleware/endpoint handler.
         
         Returns:
-            StarletteResponse: Response nesnesi
-        
-        Flow:
-            1. Public endpoint ise -> direkt geç
-            2. Token yoksa -> 401 veya redirect
-            3. Token geçersizse -> 401 veya redirect (cookie sil)
-            4. Session expired ise -> 401 veya redirect
-            5. Her şey OK ise -> next middleware/handler
+            StarletteResponse: The HTTP response object.
         """
-        skip_auth_paths = [
+        skip_auth_paths: list[str] = [
             "/login", 
             "/register", 
             "/api/login", 
@@ -60,8 +44,7 @@ class AuthMiddleware(BaseHTTPMiddleware):
         if any(request.url.path.startswith(path) for path in skip_auth_paths):
             return await call_next(request)
         
-        # Token'ı sadece cookie'den al
-        token = request.cookies.get("access_token")
+        token: str | None = request.cookies.get("access_token")
         if not token:
             if request.url.path.startswith("/api/"):
                 return StarletteResponse(
@@ -71,33 +54,47 @@ class AuthMiddleware(BaseHTTPMiddleware):
                 )
             return RedirectResponse(url="/login", status_code=302)
         try:
-                payload = verify_token(token)
-                if not payload:
-                    raise HTTPException(status_code=401, detail="Invalid token")
-                user_id = get_user_id_from_payload(payload=payload)
-                if not user_id:
-                    raise HTTPException(status_code=401, detail="Invalid token")
-                session_cache = get_session_cache(request)
-                from authentication import config
-                if not session_cache.is_valid(int(user_id), timeout_minutes=config.SESSION_TIMEOUT):
-                    session_cache.remove(int(user_id))
-                    raise HTTPException(status_code=401, detail="Invalid session")
+            payload: dict | None = verify_token(token)
+            if not payload:
+                raise HTTPException(status_code=401, detail="Invalid token")
+            user_id: str | None = get_user_id_from_payload(payload=payload)
+            if not user_id:
+                raise HTTPException(status_code=401, detail="Invalid token")
+                
+            # Check JTI blacklist
+            jti = payload.get("jti")
+            if jti:
+                app_db = request.app.state.app_db
+                is_blacklisted = await app_db.is_token_blacklisted(jti)
+                if is_blacklisted:
+                    raise HTTPException(status_code=401, detail="Token has been revoked")
         except Exception as e:
-            print(e)
+            print(f"Auth verification failed: {e}")
             if request.url.path.startswith("/api/"):
                 return StarletteResponse(
                     content='{"detail":"Invalid token"}',
                     status_code=401,
                     media_type="application/json"
                 )
-            response = RedirectResponse(url="/login", status_code=302)
+            response: RedirectResponse = RedirectResponse(url="/login", status_code=302)
             response.delete_cookie(
                 key="access_token",
-                secure=False,
+                secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
                 samesite="strict",
                 httponly=True
             )
             return response
         
-        response = await call_next(request)
-        return response
\ No newline at end of file
+        user_token = None
+        if user_id:
+            request.state.user_id = user_id
+            from common.logging_config import user_id_var
+            user_token = user_id_var.set(user_id)
+        
+        try:
+            response: StarletteResponse = await call_next(request)
+            return response
+        finally:
+            if user_token:
+                from common.logging_config import user_id_var
+                user_id_var.reset(user_token)
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (auth_middleware.py)</summary>

```python
"""
Authentication Middleware
Her HTTP request için JWT token doğrulama ve session kontrolü yapar
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse
from starlette.responses import RedirectResponse
from fastapi import Request
import os
from authentication.services import verify_token, get_user_id_from_payload
from fastapi.exceptions import HTTPException

class AuthMiddleware(BaseHTTPMiddleware):
    """
    JWT token validation middleware.
    
    For every request:
        1. Public endpoint check (login, register, health)
        2. Retrieves JWT token from access_token cookie
        3. Validates the token
        4. If invalid/missing, responds with 401 (for APIs) or redirects to /login (for web pages)
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        """
        Processes the request, checking authentication.
        
        Args:
            request: The incoming HTTP request.
            call_next: The next middleware/endpoint handler.
        
        Returns:
            StarletteResponse: The HTTP response object.
        """
        skip_auth_paths: list[str] = [
            "/login", 
            "/register", 
            "/api/login", 
            "/api/register",
            "/health"
        ]
        
        if any(request.url.path.startswith(path) for path in skip_auth_paths):
            return await call_next(request)
        
        token: str | None = request.cookies.get("access_token")
        if not token:
            if request.url.path.startswith("/api/"):
                return StarletteResponse(
                    content='{"detail":"Token required"}',
                    status_code=401,
                    media_type="application/json"
                )
            return RedirectResponse(url="/login", status_code=302)
        try:
            payload: dict | None = verify_token(token)
            if not payload:
                raise HTTPException(status_code=401, detail="Invalid token")
            user_id: str | None = get_user_id_from_payload(payload=payload)
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
                
            # Check JTI blacklist
            jti = payload.get("jti")
            if jti:
                app_db = request.app.state.app_db
                is_blacklisted = await app_db.is_token_blacklisted(jti)
                if is_blacklisted:
                    raise HTTPException(status_code=401, detail="Token has been revoked")
        except Exception as e:
            print(f"Auth verification failed: {e}")
            if request.url.path.startswith("/api/"):
                return StarletteResponse(
                    content='{"detail":"Invalid token"}',
                    status_code=401,
                    media_type="application/json"
                )
            response: RedirectResponse = RedirectResponse(url="/login", status_code=302)
            response.delete_cookie(
                key="access_token",
                secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
                samesite="strict",
                httponly=True
            )
            return response
        
        user_token = None
        if user_id:
            request.state.user_id = user_id
            from common.logging_config import user_id_var
            user_token = user_id_var.set(user_id)
        
        try:
            response: StarletteResponse = await call_next(request)
            return response
        finally:
            if user_token:
                from common.logging_config import user_id_var
                user_id_var.reset(user_token)
```
</details>



#### <a name="web_apiauthenticationexceptionspy"></a> `web_api/authentication/exceptions.py`
**Açıklama:** Kimlik doğrulama süreçlerinde oluşan hatalar için `UserAlreadyExistsError` ve `InvalidCredentialsError` gibi özel domain hatalarını tanımlar.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/authentication/exceptions.py b/web_api/authentication/exceptions.py
new file mode 100644
index 0000000..fd42096
--- /dev/null
+++ b/web_api/authentication/exceptions.py
@@ -0,0 +1,15 @@
+"""
+Authentication Exceptions
+Custom exceptions for user authentication, registration, and session verification.
+"""
+from common.exceptions import BaseServiceException
+
+class UserAlreadyExistsError(BaseServiceException):
+    """Raised when registering a new user with an email that is already taken."""
+    status_code = 400
+    code = "USER_ALREADY_EXISTS"
+
+class InvalidCredentialsError(BaseServiceException):
+    """Raised when user login credentials verification fails."""
+    status_code = 401
+    code = "INVALID_CREDENTIALS"
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (exceptions.py)</summary>

```python
"""
Authentication Exceptions
Custom exceptions for user authentication, registration, and session verification.
"""
from common.exceptions import BaseServiceException

class UserAlreadyExistsError(BaseServiceException):
    """Raised when registering a new user with an email that is already taken."""
    status_code = 400
    code = "USER_ALREADY_EXISTS"

class InvalidCredentialsError(BaseServiceException):
    """Raised when user login credentials verification fails."""
    status_code = 401
    code = "INVALID_CREDENTIALS"

```
</details>



#### <a name="web_apiauthenticationconfigpy"></a> `web_api/authentication/config.py`
**Açıklama:** Kimlik doğrulama parametrelerini ve `.env` dosyasından okunan gizli anahtarları (secret keys) yöneten yapılandırma modülü.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/authentication/config.py b/web_api/authentication/config.py
index 0899479..926e3b8 100644
--- a/web_api/authentication/config.py
+++ b/web_api/authentication/config.py
@@ -4,7 +4,7 @@ Authentication Service Config
 import os
 from dotenv import load_dotenv
 
-# .env dosyasını yükle
+# Load .env file
 load_dotenv()
 
 SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (config.py)</summary>

```python
"""
Authentication Service Config
"""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))
COOKIE_TOKEN_EXPIRE_MINUTES = int(os.getenv("COOKIE_TOKEN_EXPIRE_MINUTES", str(60 * 60 * 24)))
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
RATE_LIMITER = os.getenv("RATE_LIMITER", "3/minute")

```
</details>



#### <a name="web_apiauthenticationrouterpy"></a> `web_api/authentication/router.py`
**Açıklama:** Kullanıcı kayıt ve giriş uç noktalarını, yeni durumsuz JWT cookie mimarisine ve merkezi hata/hız sınırlama sistemlerine uyumlu olacak şekilde güncellenen HTTP API yönlendiricisi.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/authentication/router.py b/web_api/authentication/router.py
index d08da4a..889345d 100644
--- a/web_api/authentication/router.py
+++ b/web_api/authentication/router.py
@@ -1,24 +1,26 @@
 """
-Authentication Router
-Login, register and user information endpoints
+Authentication Router Module
+FastAPI router for user login, registration, logout, and self-information.
+Strictly typed and documented.
 """
 from fastapi import APIRouter, HTTPException, Response, Request, Depends
-from datetime import datetime
-from cryptography.fernet import Fernet
-from slowapi import Limiter
-from slowapi.util import get_remote_address
+import os
+from typing import Any
+from common.limiter import limiter
+
+from authentication.exceptions import UserAlreadyExistsError
 
 from authentication import config
 from authentication import schemas
 from authentication.services import create_access_token, get_current_user
-from dependencies import get_app_db, get_db_provider, get_session_cache, get_fernet
-from session.session_cache import SessionCache
+from dependencies import get_app_db, get_db_provider
 from app_database.app_database import AppDatabase
 from database_provider import DatabaseProvider
+from app_database.models import User
 
 router = APIRouter(prefix="/api")
 
-limiter = Limiter(key_func=get_remote_address)
+# Using centralized limiter
 
 
 @router.post("/login", response_model=schemas.Token)
@@ -27,47 +29,48 @@ async def login(
     user: schemas.UserLogin,
     response: Response,
     request: Request,
-    app_db: AppDatabase = Depends(get_app_db),
-    db_provider: DatabaseProvider = Depends(get_db_provider),
-    session_cache: SessionCache = Depends(get_session_cache),
-    fernet: Fernet = Depends(get_fernet)
-):
+    app_db: AppDatabase = Depends(get_app_db)
+) -> dict[str, str]:
     """
     User login endpoint.
+    Verifies credentials, creates JWT token, and writes login logs.
     
-    Verifies credentials, creates JWT token, and initializes user session.
+    Args:
+        user: The user login credentials payload.
+        response: The FastAPI response object (used to set auth cookies).
+        request: The FastAPI request object (used for client IP logging).
+        app_db: The application database manager instance.
+        
+    Returns:
+        dict[str, str]: The access token response.
     """
     async with app_db.get_app_db() as db:
-        from app_database.models import User
         from sqlalchemy.future import select
         
         result = await db.execute(select(User).where(User.email == user.email))
-        authenticated_user = result.scalars().first()
+        authenticated_user: User | None = result.scalars().first()
         
         if not authenticated_user or not authenticated_user.check_password(user.password):
             raise HTTPException(status_code=400, detail="Invalid email or password")
         
-        user_id = int(authenticated_user.id)
-        username = str(authenticated_user.username)
+        user_id: int = int(authenticated_user.id)
         
         # Create JWT token
-        user_to_login = {"sub": str(user_id)}
-        token = create_access_token(user_to_login)
+        user_to_login: dict[str, str] = {"sub": str(user_id)}
+        token: str = create_access_token(user_to_login)
         
         response.set_cookie(
             key="access_token",
             value=token,
-            secure=False,
+            secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
             samesite="strict",
             httponly=True,
             max_age=config.COOKIE_TOKEN_EXPIRE_MINUTES
         )
         
-        client_ip = request.client.host
+        client_ip: str = request.client.host if request.client else "unknown"
         await app_db.create_login_log(user_id=user_id, client_ip=client_ip)
         
-        session_cache.add_to_cache(password=user.password, user_id=user_id)
-        
         return {"access_token": token}
 
 
@@ -77,33 +80,46 @@ async def register(
     user: schemas.UserCreate,
     response: Response,
     request: Request,
-    app_db: AppDatabase = Depends(get_app_db),
-    db_provider: DatabaseProvider = Depends(get_db_provider)
-):
+    app_db: AppDatabase = Depends(get_app_db)
+) -> dict[str, Any]:
     """
     New user registration endpoint.
-    
     Registers a new user if the email is not already taken.
+    
+    Args:
+        user: The user registration details payload.
+        response: The FastAPI response object.
+        request: The FastAPI request object.
+        app_db: The application database manager instance.
+        
+    Returns:
+        dict[str, any]: A dictionary indicating success or failure.
     """
     async with app_db.get_app_db() as db:
-        from app_database.models import User
         from sqlalchemy.future import select
         
         result = await db.execute(select(User).where(User.email == user.email))
-        existing_user = result.scalars().first()
+        existing_user: User | None = result.scalars().first()
         
         if existing_user:
-            raise HTTPException(status_code=400, detail="Email already registered")
+            raise UserAlreadyExistsError("Email already registered")
         
-        new_user = User(
+        new_user: User = User(
             username=user.username,
             email=user.email
         )
-        new_user.set_password(user.password)
+        try:
+            new_user.set_password(user.password)
+        except ValueError as e:
+            raise HTTPException(status_code=400, detail=str(e))
 
         db.add(new_user)
-        await db.commit()
-        await db.refresh(new_user)
+        try:
+            await db.commit()
+            await db.refresh(new_user)
+        except Exception as e:
+            await db.rollback()
+            raise HTTPException(status_code=500, detail=f"Database error during registration: {str(e)}")
         
         return {
             "success": True,
@@ -112,9 +128,15 @@ async def register(
 
 
 @router.get("/me", response_model=schemas.User)
-async def read_users_me(current_user=Depends(get_current_user)):
+async def read_users_me(current_user: User = Depends(get_current_user)) -> schemas.User:
     """
-    Returns current user information.
+    Returns current authenticated user information.
+    
+    Args:
+        current_user: The authenticated user instance.
+        
+    Returns:
+        schemas.User: The user details schema.
     """
     return schemas.User(
         username=current_user.username,
@@ -125,28 +147,51 @@ async def read_users_me(current_user=Depends(get_current_user)):
 @router.post("/logout")
 async def logout(
     response: Response,
-    current_user=Depends(get_current_user),
+    request: Request,
+    current_user: User = Depends(get_current_user),
     app_db: AppDatabase = Depends(get_app_db),
-    db_provider: DatabaseProvider = Depends(get_db_provider),
-    session_cache: SessionCache = Depends(get_session_cache)
-):
+    db_provider: DatabaseProvider = Depends(get_db_provider)
+) -> dict[str, str]:
     """
     User logout endpoint.
+    Clears auth cookie, updates logout logs, and closes user target database engines.
     
-    Clears auth cookie, updates logs, and closes user database connections.
+    Args:
+        response: The FastAPI response object.
+        request: The FastAPI request object.
+        current_user: The authenticated user instance.
+        app_db: The application database manager instance.
+        db_provider: The database provider instance.
+        
+    Returns:
+        dict[str, str]: A dictionary with success status.
     """
+    # Extract and blacklist the token if present
+    token = request.cookies.get("access_token")
+    if token:
+        try:
+            from jose import jwt
+            from authentication import config
+            from datetime import datetime, timezone
+            
+            payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
+            jti = payload.get("jti")
+            exp = payload.get("exp")
+            if jti and exp:
+                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
+                await app_db.blacklist_token(jti=jti, expires_at=expires_at)
+        except Exception as e:
+            print(f"Error blacklisting token on logout: {e}")
+
     # Clear token from cookie
     response.delete_cookie(
         key="access_token",
-        secure=False,
+        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
         samesite="strict",
         httponly=True
     )
     
     await app_db.update_login_log(user_id=current_user.id)
-    
     await db_provider.close_user_engines(current_user.id)
 
-    session_cache.remove(current_user.id)
-
     return {"message": "Successfully logged out"}
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (router.py)</summary>

```python
"""
Authentication Router Module
FastAPI router for user login, registration, logout, and self-information.
Strictly typed and documented.
"""
from fastapi import APIRouter, HTTPException, Response, Request, Depends
import os
from typing import Any
from common.limiter import limiter

from authentication.exceptions import UserAlreadyExistsError

from authentication import config
from authentication import schemas
from authentication.services import create_access_token, get_current_user
from dependencies import get_app_db, get_db_provider
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from app_database.models import User

router = APIRouter(prefix="/api")

# Using centralized limiter


@router.post("/login", response_model=schemas.Token)
@limiter.limit(config.RATE_LIMITER)
async def login(
    user: schemas.UserLogin,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db)
) -> dict[str, str]:
    """
    User login endpoint.
    Verifies credentials, creates JWT token, and writes login logs.
    
    Args:
        user: The user login credentials payload.
        response: The FastAPI response object (used to set auth cookies).
        request: The FastAPI request object (used for client IP logging).
        app_db: The application database manager instance.
        
    Returns:
        dict[str, str]: The access token response.
    """
    async with app_db.get_app_db() as db:
        from sqlalchemy.future import select
        
        result = await db.execute(select(User).where(User.email == user.email))
        authenticated_user: User | None = result.scalars().first()
        
        if not authenticated_user or not authenticated_user.check_password(user.password):
            raise HTTPException(status_code=400, detail="Invalid email or password")
        
        user_id: int = int(authenticated_user.id)
        
        # Create JWT token
        user_to_login: dict[str, str] = {"sub": str(user_id)}
        token: str = create_access_token(user_to_login)
        
        response.set_cookie(
            key="access_token",
            value=token,
            secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
            samesite="strict",
            httponly=True,
            max_age=config.COOKIE_TOKEN_EXPIRE_MINUTES
        )
        
        client_ip: str = request.client.host if request.client else "unknown"
        await app_db.create_login_log(user_id=user_id, client_ip=client_ip)
        
        return {"access_token": token}


@router.post("/register")
@limiter.limit(config.RATE_LIMITER)
async def register(
    user: schemas.UserCreate,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db)
) -> dict[str, Any]:
    """
    New user registration endpoint.
    Registers a new user if the email is not already taken.
    
    Args:
        user: The user registration details payload.
        response: The FastAPI response object.
        request: The FastAPI request object.
        app_db: The application database manager instance.
        
    Returns:
        dict[str, any]: A dictionary indicating success or failure.
    """
    async with app_db.get_app_db() as db:
        from sqlalchemy.future import select
        
        result = await db.execute(select(User).where(User.email == user.email))
        existing_user: User | None = result.scalars().first()
        
        if existing_user:
            raise UserAlreadyExistsError("Email already registered")
        
        new_user: User = User(
            username=user.username,
            email=user.email
        )
        try:
            new_user.set_password(user.password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        db.add(new_user)
        try:
            await db.commit()
            await db.refresh(new_user)
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error during registration: {str(e)}")
        
        return {
            "success": True,
            "message": "Registration successful! Redirecting to login page..."
        }


@router.get("/me", response_model=schemas.User)
async def read_users_me(current_user: User = Depends(get_current_user)) -> schemas.User:
    """
    Returns current authenticated user information.
    
    Args:
        current_user: The authenticated user instance.
        
    Returns:
        schemas.User: The user details schema.
    """
    return schemas.User(
        username=current_user.username,
        is_admin=current_user.is_admin if current_user.is_admin is not None else False
    )


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider)
) -> dict[str, str]:
    """
    User logout endpoint.
    Clears auth cookie, updates logout logs, and closes user target database engines.
    
    Args:
        response: The FastAPI response object.
        request: The FastAPI request object.
        current_user: The authenticated user instance.
        app_db: The application database manager instance.
        db_provider: The database provider instance.
        
    Returns:
        dict[str, str]: A dictionary with success status.
    """
    # Extract and blacklist the token if present
    token = request.cookies.get("access_token")
    if token:
        try:
            from jose import jwt
            from authentication import config
            from datetime import datetime, timezone
            
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
                await app_db.blacklist_token(jti=jti, expires_at=expires_at)
        except Exception as e:
            print(f"Error blacklisting token on logout: {e}")

    # Clear token from cookie
    response.delete_cookie(
        key="access_token",
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        samesite="strict",
        httponly=True
    )
    
    await app_db.update_login_log(user_id=current_user.id)
    await db_provider.close_user_engines(current_user.id)

    return {"message": "Successfully logged out"}
```
</details>



#### <a name="web_apiauthenticationservicespy"></a> `web_api/authentication/services.py`
**Açıklama:** JWT token oluşturma, doğrulama ve kullanıcı yetkilendirme servis mantığını, Türkçe yorum satırları İngilizceye çevrilerek ve cookie tabanlı akışa entegre edilerek güncellenen servis sınıfı.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/authentication/services.py b/web_api/authentication/services.py
index 52e2bfc..26f155c 100644
--- a/web_api/authentication/services.py
+++ b/web_api/authentication/services.py
@@ -1,11 +1,11 @@
 """
 Authentication Service Layer
-JWT token oluşturma, doğrulama ve kullanıcı yetkilendirme işlemleri
+JWT token generation, verification, and user authorization operations.
 """
 from datetime import datetime, timedelta, UTC
 from typing import Optional
 from jose import JWTError, jwt
-from fastapi import HTTPException, status, Request, Depends
+from fastapi import HTTPException, status, Request
 from sqlalchemy.future import select
 
 from authentication import config
@@ -16,31 +16,33 @@ from app_database.app_database import AppDatabase
 
 def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
     """
-    JWT access token oluşturur
+    Generates a new JWT access token.
     
     Args:
-        data: Token içeriği (genellikle {"sub": user_id})
-        expires_delta: Token geçerlilik süresi (varsayılan: config.ACCESS_TOKEN_EXPIRE_MINUTES)
-    
+        data: Payload content (typically {"sub": user_id}).
+        expires_delta: Token expiration duration (defaults to config.ACCESS_TOKEN_EXPIRE_MINUTES).
+        
     Returns:
-        JWT token string
+        str: Generated JWT token string.
     """
     to_encode = data.copy()
     expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
-    to_encode.update({"exp": expire})
+    import uuid
+    jti = uuid.uuid4().hex
+    to_encode.update({"exp": expire, "jti": jti})
     encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
     return encoded_jwt
 
 
 def verify_token(token: str) -> Optional[dict]:
     """
-    JWT token'ı doğrular
+    Validates a JWT token.
     
     Args:
-        token: JWT token string
-    
+        token: JWT token string.
+        
     Returns:
-        Token payload veya None
+        Optional[dict]: Decoded token payload if valid, otherwise None.
     """
     try:
         payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
@@ -51,13 +53,13 @@ def verify_token(token: str) -> Optional[dict]:
 
 def get_user_id_from_payload(payload: dict) -> Optional[str]:
     """
-    Token payload'ından user_id çıkarır
+    Extracts the user_id (sub) from the token payload.
     
     Args:
-        payload: JWT token payload
-    
+        payload: Decoded JWT token payload.
+        
     Returns:
-        User ID string veya None
+        Optional[str]: User ID string if present, otherwise None.
     """
     try:
         user_id = payload.get("sub")
@@ -70,26 +72,26 @@ async def get_current_user(
     request: Request
 ) -> User:
     """
-    Request'ten JWT token alır, doğrular ve User nesnesini döndürür
+    Extracts JWT token from Request, validates it, and returns the User object.
     
     Args:
-        request: FastAPI Request nesnesi
-    
+        request: FastAPI Request object.
+        
     Returns:
-        User: Authenticated user
-    
+        User: Authenticated user.
+        
     Raises:
-        HTTPException: Token geçersiz veya kullanıcı bulunamaz ise
+        HTTPException: If token is invalid or user is not found.
     """
-    # AppDatabase instance'ını request state'den al (Circular import önlemek için)
+    # Retrieve AppDatabase instance from request state to prevent circular imports
     app_db: AppDatabase = request.app.state.app_db
 
-    # Token'ı sadece cookie'den al
+    # Retrieve token solely from cookies
     token = request.cookies.get("access_token")
     
     credentials_exception = HTTPException(
         status_code=status.HTTP_401_UNAUTHORIZED,
-        detail="Geçersiz token",
+        detail="Invalid token",
         headers={"WWW-Authenticate": "Bearer"}
     )
     
@@ -99,14 +101,21 @@ async def get_current_user(
     try:
         payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
         user_id: str = payload.get("sub")
+        jti: str = payload.get("jti")
         if user_id is None:
             raise credentials_exception
         token_data = TokenData(sub=user_id)
     except JWTError as e:
         print(f"JWT Error: {str(e)}")
         raise credentials_exception
+        
+    # Check if token is blacklisted
+    if jti:
+        is_blacklisted = await app_db.is_token_blacklisted(jti)
+        if is_blacklisted:
+            raise credentials_exception
     
-    # AppDatabase'den user'ı çek
+    # Retrieve user from AppDatabase
     async with app_db.get_app_db() as db:
         result = await db.execute(select(User).filter(User.id == int(token_data.sub)))
         user = result.scalars().first()
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (services.py)</summary>

```python
"""
Authentication Service Layer
JWT token generation, verification, and user authorization operations.
"""
from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Request
from sqlalchemy.future import select

from authentication import config
from app_database.models import User
from authentication.schemas import TokenData
from app_database.app_database import AppDatabase


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a new JWT access token.
    
    Args:
        data: Payload content (typically {"sub": user_id}).
        expires_delta: Token expiration duration (defaults to config.ACCESS_TOKEN_EXPIRE_MINUTES).
        
    Returns:
        str: Generated JWT token string.
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    import uuid
    jti = uuid.uuid4().hex
    to_encode.update({"exp": expire, "jti": jti})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Validates a JWT token.
    
    Args:
        token: JWT token string.
        
    Returns:
        Optional[dict]: Decoded token payload if valid, otherwise None.
    """
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_id_from_payload(payload: dict) -> Optional[str]:
    """
    Extracts the user_id (sub) from the token payload.
    
    Args:
        payload: Decoded JWT token payload.
        
    Returns:
        Optional[str]: User ID string if present, otherwise None.
    """
    try:
        user_id = payload.get("sub")
        return user_id
    except Exception:
        return None


async def get_current_user(
    request: Request
) -> User:
    """
    Extracts JWT token from Request, validates it, and returns the User object.
    
    Args:
        request: FastAPI Request object.
        
    Returns:
        User: Authenticated user.
        
    Raises:
        HTTPException: If token is invalid or user is not found.
    """
    # Retrieve AppDatabase instance from request state to prevent circular imports
    app_db: AppDatabase = request.app.state.app_db

    # Retrieve token solely from cookies
    token = request.cookies.get("access_token")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(sub=user_id)
    except JWTError as e:
        print(f"JWT Error: {str(e)}")
        raise credentials_exception
        
    # Check if token is blacklisted
    if jti:
        is_blacklisted = await app_db.is_token_blacklisted(jti)
        if is_blacklisted:
            raise credentials_exception
    
    # Retrieve user from AppDatabase
    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).filter(User.id == int(token_data.sub)))
        user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    
    return user

```
</details>



#### <a name="web_apiauthentication__init__py"></a> `web_api/authentication/__init__.py`
**Açıklama:** Paket seviyesinde kimlik doğrulama hata sınıflarını dışa aktaran başlatma modülü.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/authentication/__init__.py b/web_api/authentication/__init__.py
index e69de29..34a84a4 100644
--- a/web_api/authentication/__init__.py
+++ b/web_api/authentication/__init__.py
@@ -0,0 +1,3 @@
+from .exceptions import UserAlreadyExistsError, InvalidCredentialsError
+
+__all__ = ["UserAlreadyExistsError", "InvalidCredentialsError"]
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (__init__.py)</summary>

```python
from .exceptions import UserAlreadyExistsError, InvalidCredentialsError

__all__ = ["UserAlreadyExistsError", "InvalidCredentialsError"]

```
</details>




### 📂 Kategori 3: Veritabanı Erişim Katmanı ve Modeller (Database Provider, Models & Config)
---

#### <a name="web_apidatabase_providerconfigpy"></a> `web_api/database_provider/config.py`
**Açıklama:** Hedef veritabanı sürücü yapılandırmalarını barındıran ve sorguların hedef sistemlerde güvenle yürütülebilmesi için `.env` üzerinden yönetilen merkezi servis hesabı (`CENTRAL_DB_USER` / `CENTRAL_DB_PASSWORD`) parametrelerini sisteme dahil eden yapılandırma modülü.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/database_provider/config.py b/web_api/database_provider/config.py
index 80654bb..a5ee2d4 100644
--- a/web_api/database_provider/config.py
+++ b/web_api/database_provider/config.py
@@ -1,15 +1,15 @@
 """
 Database Provider Configuration
-Erişilebilir SQL Server instance listesi ve connection string template
+List of accessible SQL Server instances and connection string templates.
 """
 import os
 from typing import List
 from dotenv import load_dotenv
 
-# .env dosyasını yükle
+# Load .env file
 load_dotenv()
 
-# Environment'tan virgülle ayrılmış server listesi al, yoksa default kullan
+# Retrieve comma-separated server list from environment, otherwise use default
 _server_list = os.getenv("SQL_SERVER_NAMES", "localhost")
 SERVER_NAMES: List[str] = [s.strip() for s in _server_list.split(",") if s.strip()]
 
@@ -17,6 +17,10 @@ SERVER_NAMES: List[str] = [s.strip() for s in _server_list.split(",") if s.strip
 DB_USER = os.getenv("DB_USER", "sa")
 DB_PASSWORD = os.getenv("DB_PASSWORD", "")
 
+# Central service account credentials for executing queries on target databases
+CENTRAL_DB_USER: str = os.getenv("CENTRAL_DB_USER", DB_USER)
+CENTRAL_DB_PASSWORD: str = os.getenv("CENTRAL_DB_PASSWORD", DB_PASSWORD)
+
 # Engine Cache Cleanup Interval (seconds)
 # Default: 1800 seconds (30 minutes)
 TIME_INTERVAL_FOR_CACHE = int(os.getenv("ENGINE_CACHE_TTL_SECONDS", "1800"))
@@ -31,13 +35,13 @@ TECHNOLOGY_DRIVER_MAP = {
 
 def get_driver_for_technology(technology: str) -> str:
     """
-    Database technology'sine göre uygun driver'ı döndürür.
+    Returns the appropriate driver for a given database technology.
     
     Args:
-        technology: Database teknolojisi (mssql, mysql, postgresql, vb.)
+        technology: Database technology (e.g., mssql, mysql, postgresql, etc.).
         
     Returns:
-        str: İlgili driver adı (aioodbc, aiomysql, asyncpg)
+        str: Corresponding driver name (e.g., aioodbc, aiomysql, asyncpg).
         
     Example:
         >>> get_driver_for_technology("mssql")
@@ -50,22 +54,23 @@ def get_driver_for_technology(technology: str) -> str:
     tech = technology.lower().strip()
     return TECHNOLOGY_DRIVER_MAP.get(tech, "aioodbc")  # default: aioodbc
 
-# Connection string builder fonksiyonları
+
+# Connection string builder functions
 def create_connection_string(tech: str, driver: str, username: str, password: str, servername: str, database: str) -> str:
     """
-    Kullanıcıya özel database connection string oluşturur.
-    Technology'ye göre uygun format kullanır.
+    Generates a database connection string using centralized or custom credentials.
+    Formats the string dynamically based on the technology.
     
     Args:
-        tech: Kullanılacak teknoloji örn: mssql, mysql, postgresql
-        driver: Kullanılacak driver örn: aioodbc, aiomysql, asyncpg
-        username: Database kullanıcı adı
-        password: Database şifresi
-        servername: Database server adı (ör: localhost, server1)
-        database: Bağlanılacak veritabanı adı
+        tech: Database technology e.g., mssql, mysql, postgresql.
+        driver: Database driver e.g., aioodbc, aiomysql, asyncpg.
+        username: Database username.
+        password: Database password.
+        servername: Database server hostname or IP.
+        database: Target database name.
         
     Returns:
-        str: İstenilen connection string
+        str: Formatted connection string.
     """
     tech = tech.lower()
     
@@ -84,7 +89,7 @@ def create_connection_string(tech: str, driver: str, username: str, password: st
         # PostgreSQL
         return f"postgresql+{driver}://{username}:{password}@{servername}/{database}"
     else:
-        # Default olarak MSSQL formatını kullan
+        # Fallback to MSSQL format
         return (
             f"{tech}+{driver}://{username}:{password}@{servername}/{database}"
             "?driver=ODBC+Driver+18+for+SQL+Server"
@@ -92,19 +97,20 @@ def create_connection_string(tech: str, driver: str, username: str, password: st
             "&connection timeout=30"
         )
 
+
 def get_master_connection_string(server: str) -> str:
     """
-    Master database'e bağlanmak için connection string oluşturur.
-    Veritabanı listesini almak için kullanılır (sys.databases sorgusu).
+    Generates a connection string for connecting to the master database.
+    Used for administrative metadata retrieval (e.g., sys.databases query).
     
     Args:
-        server: SQL Server instance adı
+        server: SQL Server instance name or address.
         
     Returns:
-        str: Master database için connection string
+        str: Connection string for the master database.
         
     Note:
-        DB_USER ve DB_PASSWORD environment variable'larından alınır
+        DB_USER and DB_PASSWORD are fetched from the environment variables.
     """
     return (
         f"mssql+aioodbc://{DB_USER}:{DB_PASSWORD}@{server}/master"
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (config.py)</summary>

```python
"""
Database Provider Configuration
List of accessible SQL Server instances and connection string templates.
"""
import os
from typing import List
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Retrieve comma-separated server list from environment, otherwise use default
_server_list = os.getenv("SQL_SERVER_NAMES", "localhost")
SERVER_NAMES: List[str] = [s.strip() for s in _server_list.split(",") if s.strip()]

# SQL Server authentication credentials
DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Central service account credentials for executing queries on target databases
CENTRAL_DB_USER: str = os.getenv("CENTRAL_DB_USER", DB_USER)
CENTRAL_DB_PASSWORD: str = os.getenv("CENTRAL_DB_PASSWORD", DB_PASSWORD)

# Engine Cache Cleanup Interval (seconds)
# Default: 1800 seconds (30 minutes)
TIME_INTERVAL_FOR_CACHE = int(os.getenv("ENGINE_CACHE_TTL_SECONDS", "1800"))

# Technology to Driver mapping
TECHNOLOGY_DRIVER_MAP = {
    "mssql": "aioodbc",
    "mysql": "aiomysql",
    "postgresql": "asyncpg",
    "postgres": "asyncpg",  
}

def get_driver_for_technology(technology: str) -> str:
    """
    Returns the appropriate driver for a given database technology.
    
    Args:
        technology: Database technology (e.g., mssql, mysql, postgresql, etc.).
        
    Returns:
        str: Corresponding driver name (e.g., aioodbc, aiomysql, asyncpg).
        
    Example:
        >>> get_driver_for_technology("mssql")
        'aioodbc'
        >>> get_driver_for_technology("mysql")
        'aiomysql'
        >>> get_driver_for_technology("postgresql")
        'asyncpg'
    """
    tech = technology.lower().strip()
    return TECHNOLOGY_DRIVER_MAP.get(tech, "aioodbc")  # default: aioodbc


# Connection string builder functions
def create_connection_string(tech: str, driver: str, username: str, password: str, servername: str, database: str) -> str:
    """
    Generates a database connection string using centralized or custom credentials.
    Formats the string dynamically based on the technology.
    
    Args:
        tech: Database technology e.g., mssql, mysql, postgresql.
        driver: Database driver e.g., aioodbc, aiomysql, asyncpg.
        username: Database username.
        password: Database password.
        servername: Database server hostname or IP.
        database: Target database name.
        
    Returns:
        str: Formatted connection string.
    """
    tech = tech.lower()
    
    if tech == "mssql":
        # Microsoft SQL Server
        return (
            f"mssql+{driver}://{username}:{password}@{servername}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
            "&connection timeout=30"
        )
    elif tech == "mysql":
        # MySQL
        return f"mysql+{driver}://{username}:{password}@{servername}/{database}"
    elif tech == "postgresql" or tech == "postgres":
        # PostgreSQL
        return f"postgresql+{driver}://{username}:{password}@{servername}/{database}"
    else:
        # Fallback to MSSQL format
        return (
            f"{tech}+{driver}://{username}:{password}@{servername}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
            "&connection timeout=30"
        )


def get_master_connection_string(server: str) -> str:
    """
    Generates a connection string for connecting to the master database.
    Used for administrative metadata retrieval (e.g., sys.databases query).
    
    Args:
        server: SQL Server instance name or address.
        
    Returns:
        str: Connection string for the master database.
        
    Note:
        DB_USER and DB_PASSWORD are fetched from the environment variables.
    """
    return (
        f"mssql+aioodbc://{DB_USER}:{DB_PASSWORD}@{server}/master"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )

```
</details>



#### <a name="web_apidatabase_providerdatabasepy"></a> `web_api/database_provider/database.py`
**Açıklama:** LRU (Least Recently Used) tahliye algoritması ve arka planda çalışan TTL (Time-To-Live) temizlik mekanizmasıyla donatılmış, boşta bağlantı tutmayan (`pool_size=0`) akıllı veritabanı motoru önbelleğini (`EngineCache`) ve dinamik oturum üretimini yöneten sağlayıcı sınıf.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/database_provider/database.py b/web_api/database_provider/database.py
index a2a74b5..579eacc 100644
--- a/web_api/database_provider/database.py
+++ b/web_api/database_provider/database.py
@@ -1,17 +1,18 @@
-from sqlalchemy import text
-from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
+"""
+Database Provider Module
+Manages database engines caching and session provisioning using centralized credentials.
+All functions and classes are strictly typed.
+"""
+from sqlalchemy.ext.asyncio import async_sessionmaker
 from typing import Dict, Any
-import os
-import  app_database.models as models
+import app_database.models as models
 from database_provider.config import (
-    SERVER_NAMES, 
     create_connection_string, 
-    get_master_connection_string,
-    get_driver_for_technology
+    get_driver_for_technology,
+    CENTRAL_DB_USER,
+    CENTRAL_DB_PASSWORD
 )
-from sqlalchemy.future import select
 from contextlib import asynccontextmanager
-from sqlalchemy.exc import SQLAlchemyError
 from .engine_cache import EngineCache
 
 class DatabaseProvider:
@@ -25,27 +26,27 @@ class DatabaseProvider:
         self.db_info: Dict[str, Dict[str, Any]] = {}
         # Format: {servername: {"databases": [list], "technology": str}}
 
-    def set_db_info(self, info: Dict[str, Dict[str, Any]]):
+    def set_db_info(self, info: Dict[str, Dict[str, Any]]) -> None:
         """
         Sets database configuration information.
         
         Args:
-            info: Database configuration dictionary
+            info: Database configuration dictionary.
         """
         self.db_info = info
     
     @asynccontextmanager
     async def get_session(self, user: models.User, servername: str, database_name: str):
         """
-        Provides user-specific async database session.
+        Provides user-specific async database session using centralized credentials.
         
         Args:
-            user: User model
-            servername: Server instance name
-            database_name: Target database name
+            user: User model.
+            servername: Server instance name.
+            database_name: Target database name.
             
         Yields:
-            AsyncSession: SQLAlchemy async session
+            AsyncSession: SQLAlchemy async session.
         """
         
         # Server validation
@@ -76,8 +77,8 @@ class DatabaseProvider:
             driver=driver,
             servername=servername,
             database=database_name,
-            username=user.username,
-            password=user.password,
+            username=CENTRAL_DB_USER,
+            password=CENTRAL_DB_PASSWORD,
         )
         
         engine = await self.engine_cache.get_engine(conn_str, owner_id=user.id)
@@ -89,33 +90,35 @@ class DatabaseProvider:
             finally:
                 await session.close()
 
-    async def close_engines(self):
+    async def start_cache_loop(self) -> None:
         """
-        Tüm kullanıcıların tüm engine'lerini kapatır ve kaynakları serbest bırakır.
-        Uygulama kapanırken çağrılmalıdır.
+        Starts the background engine cache cleanup loop.
+        Should be called during application startup.
+        """
+        await self.engine_cache.start_loop()
+
+    async def close_engines(self) -> None:
+        """
+        Closes all engines for all users and releases resources.
+        Should be called when the application shuts down.
         """
         await self.engine_cache.stop_loop()
 
-    async def close_user_engines(self, user_id: int):
+    async def close_user_engines(self, user_id: int) -> None:
         """
-        Belirli bir kullanıcının tüm engine'lerini kapatır.
-        Kullanıcı logout olduğunda çağrılır.
+        Closes all database engines for a specific user.
+        Called when a user logs out.
         
         Args:
-            user_id: Kapatılacak kullanıcının ID'si
+            user_id: The ID of the user whose engines should be closed.
         """
         await self.engine_cache.close_user_engines(user_id) 
     
-    def get_db_info_db(self):
+    def get_db_info_db(self) -> Dict[str, Dict[str, Any]]:
         """
-        Tüm sunuculardaki veritabanı bilgilerini döndürür.
+        Returns database configuration information for all servers.
         
         Returns:
-            Dict[str, Dict[str, Any]]: {
-                servername: {
-                    "databases": [database_names],
-                    "technology": str
-                }
-            }
+            Dict[str, Dict[str, Any]]: Configuration mapping of servers to their databases and technology.
         """
         return self.db_info
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (database.py)</summary>

```python
"""
Database Provider Module
Manages database engines caching and session provisioning using centralized credentials.
All functions and classes are strictly typed.
"""
from sqlalchemy.ext.asyncio import async_sessionmaker
from typing import Dict, Any
import app_database.models as models
from database_provider.config import (
    create_connection_string, 
    get_driver_for_technology,
    CENTRAL_DB_USER,
    CENTRAL_DB_PASSWORD
)
from contextlib import asynccontextmanager
from .engine_cache import EngineCache

class DatabaseProvider:
    """
    Manages SQL Server database connections.
    """
    
    def __init__(self):
        """Initializes DatabaseProvider."""
        self.engine_cache: EngineCache = EngineCache()
        self.db_info: Dict[str, Dict[str, Any]] = {}
        # Format: {servername: {"databases": [list], "technology": str}}

    def set_db_info(self, info: Dict[str, Dict[str, Any]]) -> None:
        """
        Sets database configuration information.
        
        Args:
            info: Database configuration dictionary.
        """
        self.db_info = info
    
    @asynccontextmanager
    async def get_session(self, user: models.User, servername: str, database_name: str):
        """
        Provides user-specific async database session using centralized credentials.
        
        Args:
            user: User model.
            servername: Server instance name.
            database_name: Target database name.
            
        Yields:
            AsyncSession: SQLAlchemy async session.
        """
        
        # Server validation
        if servername not in self.db_info:
            raise ValueError(
                f"Server '{servername}' not found in database configuration. "
                f"Available servers: {list(self.db_info.keys())}. "
                f"Please add it to the Databases table."
            )
        
        server_info = self.db_info[servername]
        
        # Database validation
        available_databases = server_info.get("databases", [])
        if database_name not in available_databases:
            raise ValueError(
                f"Database '{database_name}' not found for server '{servername}'. "
                f"Available databases: {available_databases}. "
                f"Please add it to the Databases table."
            )
        
        # Get technology and driver
        tech = server_info.get("technology", "mssql")
        driver = get_driver_for_technology(tech)

        conn_str = create_connection_string(
            tech=tech,
            driver=driver,
            servername=servername,
            database=database_name,
            username=CENTRAL_DB_USER,
            password=CENTRAL_DB_PASSWORD,
        )
        
        engine = await self.engine_cache.get_engine(conn_str, owner_id=user.id)

        AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def start_cache_loop(self) -> None:
        """
        Starts the background engine cache cleanup loop.
        Should be called during application startup.
        """
        await self.engine_cache.start_loop()

    async def close_engines(self) -> None:
        """
        Closes all engines for all users and releases resources.
        Should be called when the application shuts down.
        """
        await self.engine_cache.stop_loop()

    async def close_user_engines(self, user_id: int) -> None:
        """
        Closes all database engines for a specific user.
        Called when a user logs out.
        
        Args:
            user_id: The ID of the user whose engines should be closed.
        """
        await self.engine_cache.close_user_engines(user_id) 
    
    def get_db_info_db(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns database configuration information for all servers.
        
        Returns:
            Dict[str, Dict[str, Any]]: Configuration mapping of servers to their databases and technology.
        """
        return self.db_info
```
</details>



#### <a name="web_apiapp_databaseconfigpy"></a> `web_api/app_database/config.py`
**Açıklama:** WebQuery uygulamasının kendi metaverilerini (kullanıcılar, loglar, çalışma alanları) sakladığı veritabanının bağlantı ayarlarını ve İngilizce dokümantasyon güncellemelerini içeren yapılandırma modülü.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/app_database/config.py b/web_api/app_database/config.py
index 03d686c..e3e15f4 100644
--- a/web_api/app_database/config.py
+++ b/web_api/app_database/config.py
@@ -1,13 +1,13 @@
 """
 Application Database Configuration
 
-Uygulama veritabanı bağlantı ayarları.
-Kullanıcı yönetimi, loglama ve workspace verilerini tutan veritabanı için kullanılır.
+Application metadata database connection settings.
+Used for user management, auditing logs, and workspace configuration storage.
 
 Environment Variables:
-    DB_USER: SQL Server kullanıcı adı (default: "sa")
-    DB_PASSWORD: SQL Server şifresi (default: "")
-    APP_DATABASE_URL: Tam connection string (override için)
+    DB_USER: SQL Server username (default: "sa")
+    DB_PASSWORD: SQL Server password (default: "")
+    APP_DATABASE_URL: Full connection string (optional override)
 """
 import os
 from dotenv import load_dotenv
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (config.py)</summary>

```python
"""
Application Database Configuration

Application metadata database connection settings.
Used for user management, auditing logs, and workspace configuration storage.

Environment Variables:
    DB_USER: SQL Server username (default: "sa")
    DB_PASSWORD: SQL Server password (default: "")
    APP_DATABASE_URL: Full connection string (optional override)
"""
import os
from dotenv import load_dotenv

load_dotenv(".env.production")
load_dotenv()

db_user = os.getenv("DB_USER", "sa")
db_password = os.getenv("DB_PASSWORD", "")
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME", "dba_application_db")

DATABASE_URL = os.getenv(
    "APP_DATABASE_URL",
    (
        f"mssql+aioodbc://{db_user}:{db_password}@{db_host}/{db_name}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )
)
```
</details>



#### <a name="web_apiapp_databaseapp_databasepy"></a> `web_api/app_database/app_database.py`
**Açıklama:** Uygulama metaveri veritabanına asenkron bağlantı oturumları sağlayan ve circular import risklerini önlemek için optimize edilen yardımcı sınıf.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/app_database/app_database.py b/web_api/app_database/app_database.py
index b451d70..b4afe49 100644
--- a/web_api/app_database/app_database.py
+++ b/web_api/app_database/app_database.py
@@ -9,7 +9,7 @@ from datetime import datetime
 from contextlib import asynccontextmanager
 from sqlalchemy.sql import select
 
-from app_database.models import User, ActionLogging, LoginLogging, QueryData, Workspace, Base, Databases
+from app_database.models import User, ActionLogging, LoginLogging, QueryData, Workspace, Base, Databases, BlacklistedToken, MaskingRule
 from database_provider import DatabaseProvider
 from app_database.schemas import UserCreate
 from typing import Dict, Any
@@ -119,7 +119,7 @@ class AppDatabase:
                 log_id = created_log.id
             return log_id
     
-    async def update_log(self, log_id, successfull: bool, error: str = None, row_count: int = None):
+    async def update_log(self, log_id, successfull: bool, error: str = None, row_count: int = None, applied_masking_rules: str = None):
         """
         Updates query execution log (result record)
         
@@ -128,6 +128,7 @@ class AppDatabase:
             successfull: Is query successful?
             error: Error message (if failed)
             row_count: Returned row count (if successful)
+            applied_masking_rules: JSON string of applied masking rules (optional)
         
         Note:
             - If failed: ErrorMessage and isSuccessfull are updated
@@ -147,6 +148,8 @@ class AppDatabase:
                         log.ExecutionDurationMS = int(duration.total_seconds() * 1000)
                         log.isSuccessfull = True
                         log.row_count = row_count
+                        if applied_masking_rules:
+                            log.applied_masking_rules = applied_masking_rules
 
     async def create_login_log(self, user_id: int, client_ip):
         """
@@ -230,12 +233,40 @@ class AppDatabase:
                 
                 for database in databases:
                     servername = database.servername
-                    
                     if servername not in db_info:
                         db_info[servername] = {
                             "databases": [],
                             "technology": database.technology
                         }
-                    
-                    db_info[servername]["databases"].append(database.database_name)                
-                return db_info
\ No newline at end of file
+                    db_info[servername]["databases"].append(database.database_name)
+                return db_info
+
+    async def blacklist_token(self, jti: str, expires_at: datetime) -> None:
+        """
+        Registers a new blacklisted JTI token upon user logout.
+        """
+        async with self.get_app_db() as db:
+            async with db.begin():
+                blacklisted = BlacklistedToken(jti=jti, expires_at=expires_at)
+                db.add(blacklisted)
+
+    async def is_token_blacklisted(self, jti: str) -> bool:
+        """
+        Checks if a JTI token has been blacklisted.
+        """
+        async with self.get_app_db() as db:
+            result = await db.execute(
+                select(BlacklistedToken).where(BlacklistedToken.jti == jti)
+            )
+            blacklisted = result.scalars().first()
+            return blacklisted is not None
+
+    async def get_masking_rules(self, database_id: int) -> list[MaskingRule]:
+        """
+        Retrieves active masking rules for a specific database.
+        """
+        async with self.get_app_db() as db:
+            result = await db.execute(
+                select(MaskingRule).where(MaskingRule.database_id == database_id, MaskingRule.is_active == True)
+            )
+            return list(result.scalars().all())
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (app_database.py)</summary>

```python
"""
Application Database Manager
Application database operations (user, log, workspace CRUD)
"""
from app_database.config import DATABASE_URL

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from datetime import datetime
from contextlib import asynccontextmanager
from sqlalchemy.sql import select

from app_database.models import User, ActionLogging, LoginLogging, QueryData, Workspace, Base, Databases, BlacklistedToken, MaskingRule
from database_provider import DatabaseProvider
from app_database.schemas import UserCreate
from typing import Dict, Any


class AppDatabase:
    """
    Application database management class.
    
    Handles user management, logging, and workspace operations.
    Manages async database connections.
    """
    
    def __init__(self):
        """
        Initializes AppDatabase and configures the connection pool.
        """
        kwargs = {
            "pool_pre_ping": False
        }
        
        if not DATABASE_URL.startswith("sqlite"):
            kwargs.update({
                "pool_size": 20,
                "max_overflow": 30,
                "pool_timeout": 20,
                "pool_recycle": 3600
            })

        self.app_engine = create_async_engine(
            DATABASE_URL,
            **kwargs
        )

        self.AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=True, bind=self.app_engine)

    @asynccontextmanager
    async def get_app_db(self):
        """
        Async database session context manager.
        """
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def create_tables(self):
        """
        Creates all tables in the database if they don't exist.
        """
        async with self.app_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create_user(db: AsyncSession, user: UserCreate):
        """
        Creates a new user.
        
        Args:
            db: Async database session
            user: User creation schema
        
        Returns:
            Dict: Result message
        """
        created_user = User(
            username = user.username,
            email = user.email
        )
        created_user.set_password(user.password)
        db.add(created_user)
        await db.commit()
        await db.refresh(created_user)
        
        return {
            "success": True,
            "message": "Registration successful! Redirecting to login page..."
        }

    async def create_log(self, user: User, query: str, machine_name: str, approved_execution: bool = False):
        """
        Creates query execution log (initial record)
        
        Args:
            user: User executing the query
            query: Executed SQL query
            machine_name: SQL Server instance name
        
        Returns:
            ActionLogging: Created log record
        
        Note:
            Log is created initially, result is updated with update_log
        """
        async with self.get_app_db() as db:
            async with db.begin():
                created_log = ActionLogging(
                    user_id = user.id,
                    username = user.username,
                    query_date = datetime.now(),
                    query = query,
                    machine_name = machine_name,
                    approved_execution = approved_execution
                )
                db.add(created_log)
                await db.flush()
                log_id = created_log.id
            return log_id
    
    async def update_log(self, log_id, successfull: bool, error: str = None, row_count: int = None, applied_masking_rules: str = None):
        """
        Updates query execution log (result record)
        
        Args:
            log_id: Log ID to update
            successfull: Is query successful?
            error: Error message (if failed)
            row_count: Returned row count (if successful)
            applied_masking_rules: JSON string of applied masking rules (optional)
        
        Note:
            - If failed: ErrorMessage and isSuccessfull are updated
            - If successful: ExecutionDurationMS, isSuccessfull and row_count are updated
        """
        async with self.get_app_db() as db:
            async with db.begin():
                result = await db.execute(select(ActionLogging).where(ActionLogging.id == log_id))
                log = result.scalars().first()

                if log:
                    if not successfull:
                        log.ErrorMessage = error
                        log.isSuccessfull = False
                    else:
                        duration = datetime.now() - log.query_date
                        log.ExecutionDurationMS = int(duration.total_seconds() * 1000)
                        log.isSuccessfull = True
                        log.row_count = row_count
                        if applied_masking_rules:
                            log.applied_masking_rules = applied_masking_rules

    async def create_login_log(self, user_id: int, client_ip):
        """
        Creates user login log
        
        Args:
            user_id: ID of the user logging in
            client_ip: Request IP address
        
        Note:
            logout_date is initially NULL, updated with update_login_log on logout
        """
        async with self.get_app_db() as db:
            async with db.begin():
                created_log = LoginLogging(
                    user_id = user_id,
                    login_date = datetime.now(),
                    client_ip = client_ip
                )
                db.add(created_log)

    async def update_login_log(self, user_id: int):
        """
        Updates user logout log
        
        Args:
            user_id: ID of the user logging out
        
        Note:
            - Finds the active log record where logout_date is NULL
            - Updates logout_date and login_duration_ms
            - Prints warning if active record is not found
        """
        async with self.get_app_db() as db:
            async with db.begin():
                result = await db.execute(
                    select(LoginLogging)
                    .where(LoginLogging.user_id == user_id)
                    .where(LoginLogging.logout_date.is_(None))
                )
                log = result.scalars().first()
                if log:
                    log.logout_date = datetime.now()
                    duration = datetime.now() - log.login_date
                    log.login_duration_ms = int(duration.total_seconds() * 1000)
                else:
                    print(f"Active login record for user {user_id}")
        
    async def get_db_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns database information per server.
        Includes database list and technology information for each server.
        
        Returns:
            Dict[str, Dict[str, Any]]: {
                servername: {
                    "databases": [database_names],
                    "technology": "mssql" | "mysql" | "postgresql"
                }
            }
        
        Example:
            {
                "localhost": {
                    "databases": ["Northwind", "AdventureWorks"],
                    "technology": "mssql"
                },
                "mysql-server-1": {
                    "databases": ["ecommerce", "analytics"],
                    "technology": "mysql"
                }
            }
        """
        async with self.get_app_db() as db:
            async with db.begin():
                result = await db.execute(
                    select(Databases)
                )
                databases = result.scalars().all()
                db_info : Dict[str, Dict[str, Any]] = {}
                
                for database in databases:
                    servername = database.servername
                    if servername not in db_info:
                        db_info[servername] = {
                            "databases": [],
                            "technology": database.technology
                        }
                    db_info[servername]["databases"].append(database.database_name)
                return db_info

    async def blacklist_token(self, jti: str, expires_at: datetime) -> None:
        """
        Registers a new blacklisted JTI token upon user logout.
        """
        async with self.get_app_db() as db:
            async with db.begin():
                blacklisted = BlacklistedToken(jti=jti, expires_at=expires_at)
                db.add(blacklisted)

    async def is_token_blacklisted(self, jti: str) -> bool:
        """
        Checks if a JTI token has been blacklisted.
        """
        async with self.get_app_db() as db:
            result = await db.execute(
                select(BlacklistedToken).where(BlacklistedToken.jti == jti)
            )
            blacklisted = result.scalars().first()
            return blacklisted is not None

    async def get_masking_rules(self, database_id: int) -> list[MaskingRule]:
        """
        Retrieves active masking rules for a specific database.
        """
        async with self.get_app_db() as db:
            result = await db.execute(
                select(MaskingRule).where(MaskingRule.database_id == database_id, MaskingRule.is_active == True)
            )
            return list(result.scalars().all())
```
</details>



#### <a name="web_apiapp_databasemodelspy"></a> `web_api/app_database/models.py`
**Açıklama:** SQLAlchemy modellerini sadeleştiren, kullanılmayan cache tablolarını temizleyen ve `Databases`, `User`, `Workspace`, `QueryData`, `ActionLogging` modelleri arasındaki ilişkileri asenkron çalışmaya uygun şekilde düzenleyen model tanımları.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/app_database/models.py b/web_api/app_database/models.py
index 2b41d21..534ebc0 100644
--- a/web_api/app_database/models.py
+++ b/web_api/app_database/models.py
@@ -2,10 +2,15 @@
 Application Database Models
 SQLAlchemy ORM models for the application database
 """
+import base64
+import os
+import re
+import bcrypt
 from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
 from sqlalchemy.dialects.mssql import DATETIME2, VARCHAR, NVARCHAR, UNIQUEIDENTIFIER, TEXT as MSSQL_TEXT
 from sqlalchemy.orm import relationship, declarative_base
-import bcrypt
+from sqlalchemy.types import TypeDecorator
+from cryptography.fernet import Fernet
 
 Base = declarative_base()
 
@@ -16,6 +21,43 @@ AppNVarChar = String().with_variant(NVARCHAR(length=None), "mssql")
 AppText = Text().with_variant(MSSQL_TEXT(), "mssql")
 AppUUID = String(36).with_variant(UNIQUEIDENTIFIER(), "mssql")
 
+class EncryptedText(TypeDecorator):
+    """
+    SQLAlchemy TypeDecorator that transparently encrypts and decrypts text at rest using AES (Fernet).
+    Uses QUERY_ENCRYPTION_KEY environment variable.
+    """
+    impl = Text
+    
+    _fernet = None
+
+    @classmethod
+    def _get_fernet(cls):
+        if cls._fernet is None:
+            key = os.getenv("QUERY_ENCRYPTION_KEY")
+            if not key:
+                # Generate a consistent fallback key for testing/development
+                key = base64.urlsafe_b64encode(b"thirty-two-bytes-consistent-key!")
+            cls._fernet = Fernet(key)
+        return cls._fernet
+
+    def process_bind_param(self, value, dialect):
+        if value is None:
+            return value
+        fernet = self._get_fernet()
+        encrypted_bytes = fernet.encrypt(value.encode("utf-8"))
+        return encrypted_bytes.decode("utf-8")
+
+    def process_result_value(self, value, dialect):
+        if value is None:
+            return value
+        fernet = self._get_fernet()
+        try:
+            decrypted_bytes = fernet.decrypt(value.encode("utf-8"))
+            return decrypted_bytes.decode("utf-8")
+        except Exception:
+            # Fallback to returning raw value if decryption fails (e.g. for legacy plaintext data)
+            return value
+
 class User(Base):
     """
     User model.
@@ -27,13 +69,34 @@ class User(Base):
     email = Column(String(50), unique=True)
     is_admin = Column(Boolean)
 
-    def set_password(self, plain_password):
-        """Hashes plain text password with bcrypt and stores it"""
-        salt = bcrypt.gensalt()
+    def set_password(self, plain_password: str) -> None:
+        """
+        Hashes plain text password with bcrypt and stores it, enforcing B2B security policy.
+        
+        Args:
+            plain_password: The raw password string to hash.
+            
+        Raises:
+            ValueError: If the password does not meet security policies.
+        """
+        if len(plain_password) < 12:
+            raise ValueError("Şifre en az 12 karakter olmalıdır.")
+        if not re.search(r'[A-Z]', plain_password) or not re.search(r'[0-9]', plain_password):
+            raise ValueError("Şifre en az bir büyük harf ve bir rakam içermelidir.")
+            
+        salt: bytes = bcrypt.gensalt(rounds=14)
         self.password = bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')
     
-    def check_password(self, plain_password):
-        """Compares plain text password with hashed password"""
+    def check_password(self, plain_password: str) -> bool:
+        """
+        Compares plain text password with hashed password.
+        
+        Args:
+            plain_password: The raw password string to check.
+            
+        Returns:
+            bool: True if password matches, False otherwise.
+        """
         return bcrypt.checkpw(plain_password.encode('utf-8'), self.password.encode('utf-8'))
 
 class ActionLogging(Base):
@@ -45,13 +108,14 @@ class ActionLogging(Base):
     user_id = Column(Integer, ForeignKey(User.id), index=True, nullable=False)
     username = Column(String(50), index=True, nullable=False)
     query_date = Column(AppDateTime, nullable=False)
-    query = Column(AppText, nullable=False)
+    query = Column(EncryptedText, nullable=False)
     machine_name = Column(String(50), index=True, nullable=False)
     ExecutionDurationMS = Column(Integer, nullable=True)
     row_count = Column(Integer, nullable=True)
     isSuccessfull = Column(Boolean, nullable=True)
     ErrorMessage = Column(AppText, nullable=True)
     approved_execution = Column(Boolean, nullable=True, default=False)
+    applied_masking_rules = Column(AppText, nullable=True)
 
 class LoginLogging(Base):
     """
@@ -63,17 +127,18 @@ class LoginLogging(Base):
     login_date = Column(AppDateTime, nullable=False)
     client_ip = Column(String, nullable=False)
     logout_date = Column(AppDateTime, nullable=True)
+    login_duration_ms = Column(Integer, nullable=True)
 
 class QueryData(Base):
     """
     User query storage model.
     """
     __tablename__ = "QueryData"
-    id = Column(Integer, primary_key=True, index=True,autoincrement=True)
+    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
     user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
     servername = Column(String(50))
     database_name = Column(String(50))
-    query = Column(AppText, nullable=False)
+    query = Column(EncryptedText, nullable=False)
     uuid = Column(AppUUID, nullable=False, index=True)
     status = Column(String(50), nullable=False)
     risk_type = Column(String(50), nullable=True)
@@ -96,4 +161,27 @@ class Databases(Base):
     id = Column(Integer, primary_key=True, index=True, autoincrement=True)
     servername = Column(String(100), nullable=False)
     database_name = Column(String(100), nullable=False)
-    technology = Column(String(100), nullable=False)
\ No newline at end of file
+    technology = Column(String(100), nullable=False)
+    db_username = Column(String(100), nullable=True)
+    db_password = Column(EncryptedText, nullable=True)
+
+class MaskingRule(Base):
+    """
+    Table and column level masking rules defined by admin.
+    """
+    __tablename__ = "MaskingRules"
+    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
+    database_id = Column(Integer, ForeignKey("Databases.id"), nullable=False)
+    table_name = Column(String(100), nullable=False)
+    column_name = Column(String(100), nullable=False)
+    masking_type = Column(String(50), default="default")
+    is_active = Column(Boolean, default=True)
+
+class BlacklistedToken(Base):
+    """
+    Blacklisted JTI tokens upon logout.
+    """
+    __tablename__ = "BlacklistedTokens"
+    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
+    jti = Column(String(100), unique=True, index=True, nullable=False)
+    expires_at = Column(AppDateTime, nullable=False)
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (models.py)</summary>

```python
"""
Application Database Models
SQLAlchemy ORM models for the application database
"""
import base64
import os
import re
import bcrypt
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.dialects.mssql import DATETIME2, VARCHAR, NVARCHAR, UNIQUEIDENTIFIER, TEXT as MSSQL_TEXT
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.types import TypeDecorator
from cryptography.fernet import Fernet

Base = declarative_base()

# Define cross-db compatible types
AppDateTime = DateTime().with_variant(DATETIME2(precision=7), "mssql")
AppVarChar = String().with_variant(VARCHAR(length=None), "mssql")
AppNVarChar = String().with_variant(NVARCHAR(length=None), "mssql")
AppText = Text().with_variant(MSSQL_TEXT(), "mssql")
AppUUID = String(36).with_variant(UNIQUEIDENTIFIER(), "mssql")

class EncryptedText(TypeDecorator):
    """
    SQLAlchemy TypeDecorator that transparently encrypts and decrypts text at rest using AES (Fernet).
    Uses QUERY_ENCRYPTION_KEY environment variable.
    """
    impl = Text
    
    _fernet = None

    @classmethod
    def _get_fernet(cls):
        if cls._fernet is None:
            key = os.getenv("QUERY_ENCRYPTION_KEY")
            if not key:
                # Generate a consistent fallback key for testing/development
                key = base64.urlsafe_b64encode(b"thirty-two-bytes-consistent-key!")
            cls._fernet = Fernet(key)
        return cls._fernet

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        fernet = self._get_fernet()
        encrypted_bytes = fernet.encrypt(value.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        fernet = self._get_fernet()
        try:
            decrypted_bytes = fernet.decrypt(value.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except Exception:
            # Fallback to returning raw value if decryption fails (e.g. for legacy plaintext data)
            return value

class User(Base):
    """
    User model.
    """
    __tablename__ = 'Users'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String)
    email = Column(String(50), unique=True)
    is_admin = Column(Boolean)

    def set_password(self, plain_password: str) -> None:
        """
        Hashes plain text password with bcrypt and stores it, enforcing B2B security policy.
        
        Args:
            plain_password: The raw password string to hash.
            
        Raises:
            ValueError: If the password does not meet security policies.
        """
        if len(plain_password) < 12:
            raise ValueError("Şifre en az 12 karakter olmalıdır.")
        if not re.search(r'[A-Z]', plain_password) or not re.search(r'[0-9]', plain_password):
            raise ValueError("Şifre en az bir büyük harf ve bir rakam içermelidir.")
            
        salt: bytes = bcrypt.gensalt(rounds=14)
        self.password = bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, plain_password: str) -> bool:
        """
        Compares plain text password with hashed password.
        
        Args:
            plain_password: The raw password string to check.
            
        Returns:
            bool: True if password matches, False otherwise.
        """
        return bcrypt.checkpw(plain_password.encode('utf-8'), self.password.encode('utf-8'))

class ActionLogging(Base):
    """
    Query execution log model.
    """
    __tablename__ = 'ActionLogging'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey(User.id), index=True, nullable=False)
    username = Column(String(50), index=True, nullable=False)
    query_date = Column(AppDateTime, nullable=False)
    query = Column(EncryptedText, nullable=False)
    machine_name = Column(String(50), index=True, nullable=False)
    ExecutionDurationMS = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    isSuccessfull = Column(Boolean, nullable=True)
    ErrorMessage = Column(AppText, nullable=True)
    approved_execution = Column(Boolean, nullable=True, default=False)
    applied_masking_rules = Column(AppText, nullable=True)

class LoginLogging(Base):
    """
    User login/logout log model.
    """
    __tablename__ = "LoginLogging"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    login_date = Column(AppDateTime, nullable=False)
    client_ip = Column(String, nullable=False)
    logout_date = Column(AppDateTime, nullable=True)
    login_duration_ms = Column(Integer, nullable=True)

class QueryData(Base):
    """
    User query storage model.
    """
    __tablename__ = "QueryData"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    servername = Column(String(50))
    database_name = Column(String(50))
    query = Column(EncryptedText, nullable=False)
    uuid = Column(AppUUID, nullable=False, index=True)
    status = Column(String(50), nullable=False)
    risk_type = Column(String(50), nullable=True)
    
class Workspace(Base):
    """
    User workspace model.
    """
    __tablename__ = "Workspaces"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    query_id = Column(Integer, ForeignKey("QueryData.id"), nullable=False, unique=True)
    show_results = Column(Boolean, nullable=True, default=None)
    query_data = relationship("QueryData")

class Databases(Base):
    __tablename__ = "Databases"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    servername = Column(String(100), nullable=False)
    database_name = Column(String(100), nullable=False)
    technology = Column(String(100), nullable=False)
    db_username = Column(String(100), nullable=True)
    db_password = Column(EncryptedText, nullable=True)

class MaskingRule(Base):
    """
    Table and column level masking rules defined by admin.
    """
    __tablename__ = "MaskingRules"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    database_id = Column(Integer, ForeignKey("Databases.id"), nullable=False)
    table_name = Column(String(100), nullable=False)
    column_name = Column(String(100), nullable=False)
    masking_type = Column(String(50), default="default")
    is_active = Column(Boolean, default=True)

class BlacklistedToken(Base):
    """
    Blacklisted JTI tokens upon logout.
    """
    __tablename__ = "BlacklistedTokens"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    jti = Column(String(100), unique=True, index=True, nullable=False)
    expires_at = Column(AppDateTime, nullable=False)
```
</details>



#### <a name="web_apiapp_database__init__py"></a> `web_api/app_database/__init__.py`
**Açıklama:** Uygulama veritabanı paket başlatma dosyası.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/app_database/__init__.py b/web_api/app_database/__init__.py
index 72dca4d..8a88289 100644
--- a/web_api/app_database/__init__.py
+++ b/web_api/app_database/__init__.py
@@ -1 +1,3 @@
-from .app_database import AppDatabase
\ No newline at end of file
+from .app_database import AppDatabase
+
+__all__ = ["AppDatabase"]
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (__init__.py)</summary>

```python
from .app_database import AppDatabase

__all__ = ["AppDatabase"]
```
</details>




### 📂 Kategori 4: Sorgu Analizi ve Güvenli Yürütme (Query Execution, AST & Auditing)
---

#### <a name="web_apiquery_executionexceptionspy"></a> `web_api/query_execution/exceptions.py`
**Açıklama:** Sorgu çalıştırma hataları için `QueryExecutionError` ve AST analiz engellemeleri için `QueryAnalysisRejectedError` özel domain hatalarını tanımlar.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/query_execution/exceptions.py b/web_api/query_execution/exceptions.py
new file mode 100644
index 0000000..e175855
--- /dev/null
+++ b/web_api/query_execution/exceptions.py
@@ -0,0 +1,15 @@
+"""
+Query Execution Exceptions
+Custom exceptions for the query execution and security analysis service layer.
+"""
+from common.exceptions import BaseServiceException
+
+class QueryExecutionError(BaseServiceException):
+    """Raised when a SQL query execution fails inside the target database."""
+    status_code = 400
+    code = "QUERY_EXECUTION_FAILED"
+
+class QueryAnalysisRejectedError(BaseServiceException):
+    """Raised when a query fails the AST security analysis and is sent for admin approval."""
+    status_code = 400
+    code = "QUERY_REJECTED_BY_ANALYZER"
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (exceptions.py)</summary>

```python
"""
Query Execution Exceptions
Custom exceptions for the query execution and security analysis service layer.
"""
from common.exceptions import BaseServiceException

class QueryExecutionError(BaseServiceException):
    """Raised when a SQL query execution fails inside the target database."""
    status_code = 400
    code = "QUERY_EXECUTION_FAILED"

class QueryAnalysisRejectedError(BaseServiceException):
    """Raised when a query fails the AST security analysis and is sent for admin approval."""
    status_code = 400
    code = "QUERY_REJECTED_BY_ANALYZER"

```
</details>



#### <a name="web_apiquery_executionquery_analyzerpy"></a> `web_api/query_execution/query_analyzer.py`
**Açıklama:** Sorguları çalıştırmadan önce `sqlglot` kütüphanesini kullanarak Soyut Sözdizim Ağacı (AST) seviyesinde analiz eden ve SQL Injection, DDL değişiklikleri, koşulsuz riskli DML işlemleri ile performans anomalilerini hedef veritabanı lehçesine (`tsql`, `mysql`, `postgres`) göre tespit eden gelişmiş güvenlik modülü.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/query_execution/query_analyzer.py b/web_api/query_execution/query_analyzer.py
index 7987ca1..8b5a077 100644
--- a/web_api/query_execution/query_analyzer.py
+++ b/web_api/query_execution/query_analyzer.py
@@ -15,38 +15,42 @@ class RiskLevel(Enum):
 
 class QueryAnalyzer:
     """
-    Analyzes SQL queries for security and performance using Abstract Syntax Trees (AST)
-    
-    Checked risks:
-        - SQL Injection / Privilege Escalation (EXECUTE AS, EXEC)
-        - DDL commands (CREATE, DROP, ALTER, TRUNCATE)
-        - Risky DML commands (DELETE/UPDATE without WHERE clause)
-        - Performance issues (multiple JOINs, CROSS JOIN, wildcard LIKE)
+    Analyzes SQL queries for security and performance using Abstract Syntax Trees (AST).
+    All methods are strictly typed and documented.
     """
     
-    def __init__(self):
+    max_joins: int
+
+    def __init__(self) -> None:
+        """Initializes the QueryAnalyzer with risk thresholds."""
         self.max_joins = 3
 
-    def analyze(self, query: str):
+    def analyze(self, query: str, technology: str = "mssql") -> dict[str, any]:
         """
-        Analyzes SQL query and performs risk assessment using sqlglot
+        Analyzes SQL query and performs risk assessment using sqlglot with target database dialect.
         
         Args:
-            query: SQL query to analyze
+            query: SQL query to analyze.
+            technology: Target database technology (e.g., mssql, mysql, postgresql).
         
         Returns:
-            Dict: {
-                "risk_type": str | None (risk type, None if none),
-                "return": bool (can query be executed?)
-            }
+            dict[str, any]: A dictionary containing risk_type (str | None) and return (bool).
         """
-        result = {"risk_type": None, "return": True}
-        q = query.strip()
+        result: dict[str, any] = {"risk_type": None, "return": True}
+        q: str = query.strip()
+        
+        # Map technology to sqlglot dialect
+        dialect_map: dict[str, str] = {
+            "mssql": "tsql",
+            "mysql": "mysql",
+            "postgresql": "postgres",
+            "postgres": "postgres"
+        }
+        dialect: str = dialect_map.get(technology.lower().strip(), "tsql")
         
         try:
-            # Parse all statements in the query.
-            # Using tsql dialect since WebQuery often interacts with MSSQL.
-            statements = sqlglot.parse(q, read="tsql")
+            # Parse all statements in the query using the matched dialect.
+            statements = sqlglot.parse(q, read=dialect)
         except sqlglot.errors.ParseError:
             # If the SQL is malformed or uses obfuscated syntax that breaks the parser,
             # block it entirely to prevent bypasses.
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (query_analyzer.py)</summary>

```python
"""
Query Analyzer
SQL query security and performance analysis via AST parsing
"""
import sqlglot
from sqlglot import exp
from enum import Enum

class RiskLevel(Enum):
    """Query risk levels"""
    SQL_INJECTION = "sql_injection_risk"
    DDL_PATTERN = "ddl_pattern"
    RISKY_PATTERN = "risky_pattern"
    PERFORMANCE = "performance_risk"

class QueryAnalyzer:
    """
    Analyzes SQL queries for security and performance using Abstract Syntax Trees (AST).
    All methods are strictly typed and documented.
    """
    
    max_joins: int

    def __init__(self) -> None:
        """Initializes the QueryAnalyzer with risk thresholds."""
        self.max_joins = 3

    def analyze(self, query: str, technology: str = "mssql") -> dict[str, any]:
        """
        Analyzes SQL query and performs risk assessment using sqlglot with target database dialect.
        
        Args:
            query: SQL query to analyze.
            technology: Target database technology (e.g., mssql, mysql, postgresql).
        
        Returns:
            dict[str, any]: A dictionary containing risk_type (str | None) and return (bool).
        """
        result: dict[str, any] = {"risk_type": None, "return": True}
        q: str = query.strip()
        
        # Map technology to sqlglot dialect
        dialect_map: dict[str, str] = {
            "mssql": "tsql",
            "mysql": "mysql",
            "postgresql": "postgres",
            "postgres": "postgres"
        }
        dialect: str = dialect_map.get(technology.lower().strip(), "tsql")
        
        try:
            # Parse all statements in the query using the matched dialect.
            statements = sqlglot.parse(q, read=dialect)
        except sqlglot.errors.ParseError:
            # If the SQL is malformed or uses obfuscated syntax that breaks the parser,
            # block it entirely to prevent bypasses.
            result["risk_type"] = RiskLevel.SQL_INJECTION.value
            result["return"] = False
            return result
            
        for stmt in statements:
            if not stmt:
                continue
                
            if self._check_sql_injection(stmt):
                result["risk_type"] = RiskLevel.SQL_INJECTION.value
                result["return"] = False
                return result
                
            if self._check_ddl(stmt):
                result["risk_type"] = RiskLevel.DDL_PATTERN.value
                result["return"] = False
                return result
                
            if self._check_risky_dml(stmt):
                result["risk_type"] = RiskLevel.RISKY_PATTERN.value
                result["return"] = False
                return result
                
            if self._check_performance(stmt):
                result["risk_type"] = RiskLevel.PERFORMANCE.value
                result["return"] = False
                return result
                
        return result

    def _check_sql_injection(self, stmt: exp.Expression) -> bool:
        """Check for privilege escalation or dynamic execution."""
        for cmd in stmt.find_all(exp.Command):
            sql_upper = cmd.sql().upper()
            if any(danger in sql_upper for danger in ["EXECUTE AS", "XP_CMDSHELL", "EXEC ", "EXEC("]):
                return True
        return False

    def _check_ddl(self, stmt: exp.Expression) -> bool:
        """Check for structural changes to the database."""
        ddl_types = (exp.Drop, exp.Create, exp.AlterTable, exp.TruncateTable)
        if isinstance(stmt, ddl_types):
            return True
        # Also check nested nodes
        for _ in stmt.find_all(ddl_types):
            return True
        return False

    def _check_risky_dml(self, stmt: exp.Expression) -> bool:
        """Check for UPDATE or DELETE without a WHERE clause."""
        dml_types = (exp.Delete, exp.Update)
        for node in stmt.find_all(dml_types):
            if not node.args.get("where"):
                return True
        return False

    def _check_performance(self, stmt: exp.Expression) -> bool:
        """Check for heavy joins or leading/trailing wildcards."""
        joins = list(stmt.find_all(exp.Join))
        
        if len(joins) >= self.max_joins:
            return True
            
        for j in joins:
            if "CROSS" in j.sql().upper():
                return True
                
        for like in stmt.find_all(exp.Like):
            pattern = like.expression.name if hasattr(like.expression, 'name') else ""
            if pattern.startswith("%") and pattern.endswith("%"):
                return True
                
        return False

```
</details>



#### <a name="web_apiquery_executionservicespy"></a> `web_api/query_execution/services.py`
**Açıklama:** Sorguların hedef veritabanlarında merkezi servis hesabı üzerinden asenkron olarak yürütülmesini sağlayan, admin olmayan kullanıcıların sonuçlarını dinamik olarak maskeleyen, hata durumlarında `QueryExecutionError` fırlatan ve her sorguyu detaylı olarak denetim loguna (audit trail) kaydeden servis sınıfı.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/query_execution/services.py b/web_api/query_execution/services.py
index d08b49a..a8fe579 100644
--- a/web_api/query_execution/services.py
+++ b/web_api/query_execution/services.py
@@ -1,11 +1,12 @@
 """
-Query Execution Service Layer
-Query execution, analysis and logging operations
+Query Execution Service Module
+Contains the core QueryService responsible for analyzing, executing, and logging SQL queries.
+Strictly typed and documented.
 """
 from sqlalchemy.sql import text
 from sqlalchemy.ext.asyncio import AsyncSession
 from datetime import datetime, timezone
-from typing import Dict, Any
+from typing import Dict, Any, List
 
 import uuid
 
@@ -15,69 +16,110 @@ from app_database.app_database import AppDatabase
 from app_database.models import User, QueryData, Workspace
 
 from query_execution.query_analyzer import QueryAnalyzer
-
 from notification import NotificationService
 
+import logging
+from common.exceptions import BaseServiceException
+from query_execution.exceptions import QueryExecutionError, QueryAnalysisRejectedError
+
+logger = logging.getLogger(__name__)
+
 class QueryService:
     """
-    Query execution and logging service
-    
-    Executes SQL queries, analyzes them and logs the results.
-    Performs query security check for non-admin users.
+    Query execution, security analysis, and logging service.
+    Coordinates risk analysis and target database execution under strict auditing.
     """
     
-    def __init__(self, database_provider: DatabaseProvider, app_db: AppDatabase, notification_service: NotificationService):
+    database_provider: DatabaseProvider
+    app_db: AppDatabase
+    analyzer: QueryAnalyzer
+    notification_service: NotificationService
+
+    def __init__(self, database_provider: DatabaseProvider, app_db: AppDatabase, notification_service: NotificationService) -> None:
         """
-        Initializes QueryService
+        Initializes the QueryService with required providers.
         
         Args:
-            database_provider: Database connection provider
-            app_db: Application database (for logging)
+            database_provider: The target database connections provider.
+            app_db: The application metadata database manager.
+            notification_service: The notifications service.
         """
         self.database_provider = database_provider
         self.app_db = app_db
         self.analyzer = QueryAnalyzer()
         self.notification_service = notification_service
 
-    async def execute_query(self, query: str, user: User, server_name: str, database_name: str) -> Dict[str, Any]:
+    async def execute_query(self, query: str, user: User, server_name: str, database_name: str, ad_hoc_mask_columns: List[str] = None) -> Dict[str, Any]:
         """
-        Executes, analyzes, and logs the SQL query.
+        Analyzes, logs, and executes the SQL query against the target database.
+        If the query is identified as risky, it is routed for admin approval.
         
         Args:
-            query: SQL query to execute
-            user: User executing the query
-            server_name: SQL Server instance name
-            database_name: Target database name
-        
+            query: The SQL query to analyze and execute.
+            user: The authenticated user executing the query.
+            server_name: The target SQL server instance name.
+            database_name: The target database name.
+            ad_hoc_mask_columns: Temporary columns to mask for this transaction (optional).
+            
         Returns:
-            Dict[str, Any]: Execution result
+            Dict[str, Any]: The execution results, rows, or error details.
         """
-        log_id = None
+        log_id: int | None = None
         try:
+            logger.info(f"Initiating query execution on server '{server_name}', database '{database_name}'")
             log_id = await self.app_db.create_log(user=user, query=query, machine_name=server_name)
-            query_analysis = self.analyzer.analyze(query)
+            
+            # Fetch persistent database masking rules & merge with user ad-hoc rules
+            db_id = None
+            masking_cols = set()
+            async with self.app_db.get_app_db() as db_session:
+                from sqlalchemy.future import select
+                from app_database.models import Databases
+                db_result = await db_session.execute(
+                    select(Databases).where(Databases.servername == server_name, Databases.database_name == database_name)
+                )
+                db_entry = db_result.scalars().first()
+                if db_entry:
+                    db_id = db_entry.id
+            
+            if db_id:
+                rules = await self.app_db.get_masking_rules(db_id)
+                for rule in rules:
+                    masking_cols.add(rule.column_name.lower())
+            
+            if ad_hoc_mask_columns:
+                for col in ad_hoc_mask_columns:
+                    masking_cols.add(col.lower())
+
+            # Resolve target database technology from the database provider config
+            server_info: Dict[str, Any] = self.database_provider.db_info.get(server_name, {})
+            technology: str = server_info.get("technology", "mssql")
+            
+            query_analysis: Dict[str, Any] = self.analyzer.analyze(query, technology=technology)
+            
             if not query_analysis["return"] and not user.is_admin:
-                error_msg = f"Query rejected: {query_analysis['risk_type']}"
+                error_msg: str = f"Query rejected: {query_analysis['risk_type']}"
                 await self.app_db.update_log(log_id=log_id, successfull=False, error=error_msg)
                 
                 try:
                     async with self.app_db.get_app_db() as db_session:
-                        query_uuid = str(uuid.uuid4())
-                        query_data = QueryData(
+                        query_uuid: str = str(uuid.uuid4())
+                        query_data: QueryData = QueryData(
                             user_id=user.id,
                             servername=server_name,
                             database_name=database_name,
                             query=query,
                             uuid=query_uuid,
-                            status="waiting_for_approval"
+                            status="waiting_for_approval",
+                            risk_type=query_analysis.get('risk_type')
                         )
                         db_session.add(query_data)
                         await db_session.flush()
                         
-                        query_data_id = query_data.id
+                        query_data_id: int = query_data.id
                         
-                        workspace_name = f"Pending: {query[:50]}..." if len(query) > 50 else f"Pending: {query}"
-                        workspace = Workspace(
+                        workspace_name: str = f"Pending: {query[:50]}..." if len(query) > 50 else f"Pending: {query}"
+                        workspace: Workspace = Workspace(
                             user_id=user.id,
                             name=workspace_name,
                             description=f"Risk Type: {query_analysis.get('risk_type', 'UNKNOWN')} - Waiting for admin approval",
@@ -87,18 +129,17 @@ class QueryService:
                         db_session.add(workspace)
                         await db_session.flush()
                         
-                        workspace_id = workspace.id
-                        
+                        workspace_id: int = workspace.id
                         await db_session.commit()
                         
-                    print(f"Query saved for approval - Workspace ID: {workspace_id}, UUID: {query_uuid}")
+                    logger.info(f"Query saved for approval - Workspace ID: {workspace_id}, UUID: {query_uuid}")
                 except Exception as save_exc:
-                    print(f"Failed to save query for approval: {type(save_exc).__name__}: {save_exc}")
+                    logger.error(f"Failed to save query for approval: {type(save_exc).__name__}: {save_exc}")
                 
                 try:
                     if self.notification_service:
-                        request_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
-                        await self.notification_service.send_approval_notifivation(
+                        request_time: str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
+                        await self.notification_service.send_approval_notification(
                             request_id=query_uuid,
                             username=getattr(user, 'username', str(getattr(user, 'id', 'unknown'))),
                             request_time=request_time,
@@ -108,13 +149,12 @@ class QueryService:
                             query=query
                         )
                 except Exception as notif_exc:
-                    print(f"Notification send error: {type(notif_exc).__name__}: {notif_exc}")
+                    logger.error(f"Notification send error: {type(notif_exc).__name__}: {notif_exc}")
+                
+                raise QueryAnalysisRejectedError(
+                    message=f"{error_msg}. Query saved to your workspaces and sent for admin approval."
+                )
                 
-                return {
-                    "response_type": "error",
-                    "data": [],
-                    "error": f"{error_msg}. Query saved to your workspaces and sent for admin approval."
-                }
             async with self.database_provider.get_session(
                 user=user,
                 servername=server_name,
@@ -122,38 +162,81 @@ class QueryService:
             ) as session:
                 sql_query = text(query)
                 result = await session.execute(sql_query)
-                rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
-                row_count = len(rows)
-                if row_count > config.MAX_ROW_COUNT_LIMIT:
-                    rows = rows[:config.MAX_ROW_COUNT_LIMIT]
-                    message = f"{row_count} rows found, showing first {config.MAX_ROW_COUNT_LIMIT}"
+                
+                row_count: int = 0
+                message: str = ""
+                result_data: Dict[str, Any] = {}
+                
+                if result.returns_rows:
+                    rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
+                    row_count = len(rows)
+                    if row_count >= config.MAX_ROW_COUNT_LIMIT:
+                        message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"
+                    else:
+                        message = f"{row_count} rows returned"
+                    
+                    raw_data = [dict(row._mapping) for row in rows]
+                    if not user.is_admin and masking_cols:
+                        from common.security import mask_result_set
+                        raw_data = mask_result_set(raw_data, masking_cols)
+                        
+                    result_data = {
+                        "response_type": "data",
+                        "data": raw_data,
+                        "message": message
+                    }
                 else:
+                    row_count = result.rowcount if result.rowcount is not None else 0
                     message = f"{row_count} rows affected"
-                result_data = {
-                    "response_type": "data",
-                    "data": [dict(row._mapping) for row in rows],
-                    "message": message
-                }
+                    result_data = {
+                        "response_type": "data",
+                        "data": [],
+                        "message": message
+                    }
+                
+                import json
+                applied_rules_str = json.dumps(list(masking_cols)) if masking_cols else None
                 await self.app_db.update_log(
                     log_id=log_id,
                     successfull=True,
-                    row_count=row_count
+                    row_count=row_count,
+                    applied_masking_rules=applied_rules_str
                 )
+                
                 if row_count > config.MAX_ROW_COUNT_WARNING:
-                    print(f"Warning: Query returned {row_count} rows")
+                    logger.warning(f"Query returned high row count: {row_count} rows")
+                
+                logger.info(f"Query executed successfully. Result: {message}")
                 return result_data
+                
+        except BaseServiceException:
+            # Re-raise already translated service exceptions
+            raise
         except Exception as e:
-            error_msg = str(e)
-            print(f"Query execution error: {error_msg}")
+            error_msg: str = str(e)
+            logger.error(f"Query execution failed: {error_msg}")
             if log_id:
                 await self.app_db.update_log(
                     log_id=log_id,
                     successfull=False,
                     error=error_msg
                 )
-            return {
-                "response_type": "error",
-                "data": [],
-                "error": error_msg
-            }
+            raise QueryExecutionError(error_msg, original_exception=e)
+
+    async def get_active_masking_rules(self, servername: str, database_name: str) -> list[str]:
+        """
+        Retrieves column names that are persistently masked for a given server and database.
+        """
+        async with self.app_db.get_app_db() as db:
+            from sqlalchemy.future import select
+            from app_database.models import Databases
+            db_result = await db.execute(
+                select(Databases).where(Databases.servername == servername, Databases.database_name == database_name)
+            )
+            db_entry = db_result.scalars().first()
+            if not db_entry:
+                return []
+            
+            rules = await self.app_db.get_masking_rules(db_entry.id)
+            return [r.column_name.lower() for r in rules]
  
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (services.py)</summary>

```python
"""
Query Execution Service Module
Contains the core QueryService responsible for analyzing, executing, and logging SQL queries.
Strictly typed and documented.
"""
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Dict, Any, List

import uuid

from query_execution import config
from database_provider import DatabaseProvider
from app_database.app_database import AppDatabase
from app_database.models import User, QueryData, Workspace

from query_execution.query_analyzer import QueryAnalyzer
from notification import NotificationService

import logging
from common.exceptions import BaseServiceException
from query_execution.exceptions import QueryExecutionError, QueryAnalysisRejectedError

logger = logging.getLogger(__name__)

class QueryService:
    """
    Query execution, security analysis, and logging service.
    Coordinates risk analysis and target database execution under strict auditing.
    """
    
    database_provider: DatabaseProvider
    app_db: AppDatabase
    analyzer: QueryAnalyzer
    notification_service: NotificationService

    def __init__(self, database_provider: DatabaseProvider, app_db: AppDatabase, notification_service: NotificationService) -> None:
        """
        Initializes the QueryService with required providers.
        
        Args:
            database_provider: The target database connections provider.
            app_db: The application metadata database manager.
            notification_service: The notifications service.
        """
        self.database_provider = database_provider
        self.app_db = app_db
        self.analyzer = QueryAnalyzer()
        self.notification_service = notification_service

    async def execute_query(self, query: str, user: User, server_name: str, database_name: str, ad_hoc_mask_columns: List[str] = None) -> Dict[str, Any]:
        """
        Analyzes, logs, and executes the SQL query against the target database.
        If the query is identified as risky, it is routed for admin approval.
        
        Args:
            query: The SQL query to analyze and execute.
            user: The authenticated user executing the query.
            server_name: The target SQL server instance name.
            database_name: The target database name.
            ad_hoc_mask_columns: Temporary columns to mask for this transaction (optional).
            
        Returns:
            Dict[str, Any]: The execution results, rows, or error details.
        """
        log_id: int | None = None
        try:
            logger.info(f"Initiating query execution on server '{server_name}', database '{database_name}'")
            log_id = await self.app_db.create_log(user=user, query=query, machine_name=server_name)
            
            # Fetch persistent database masking rules & merge with user ad-hoc rules
            db_id = None
            masking_cols = set()
            async with self.app_db.get_app_db() as db_session:
                from sqlalchemy.future import select
                from app_database.models import Databases
                db_result = await db_session.execute(
                    select(Databases).where(Databases.servername == server_name, Databases.database_name == database_name)
                )
                db_entry = db_result.scalars().first()
                if db_entry:
                    db_id = db_entry.id
            
            if db_id:
                rules = await self.app_db.get_masking_rules(db_id)
                for rule in rules:
                    masking_cols.add(rule.column_name.lower())
            
            if ad_hoc_mask_columns:
                for col in ad_hoc_mask_columns:
                    masking_cols.add(col.lower())

            # Resolve target database technology from the database provider config
            server_info: Dict[str, Any] = self.database_provider.db_info.get(server_name, {})
            technology: str = server_info.get("technology", "mssql")
            
            query_analysis: Dict[str, Any] = self.analyzer.analyze(query, technology=technology)
            
            if not query_analysis["return"] and not user.is_admin:
                error_msg: str = f"Query rejected: {query_analysis['risk_type']}"
                await self.app_db.update_log(log_id=log_id, successfull=False, error=error_msg)
                
                try:
                    async with self.app_db.get_app_db() as db_session:
                        query_uuid: str = str(uuid.uuid4())
                        query_data: QueryData = QueryData(
                            user_id=user.id,
                            servername=server_name,
                            database_name=database_name,
                            query=query,
                            uuid=query_uuid,
                            status="waiting_for_approval",
                            risk_type=query_analysis.get('risk_type')
                        )
                        db_session.add(query_data)
                        await db_session.flush()
                        
                        query_data_id: int = query_data.id
                        
                        workspace_name: str = f"Pending: {query[:50]}..." if len(query) > 50 else f"Pending: {query}"
                        workspace: Workspace = Workspace(
                            user_id=user.id,
                            name=workspace_name,
                            description=f"Risk Type: {query_analysis.get('risk_type', 'UNKNOWN')} - Waiting for admin approval",
                            query_id=query_data_id,
                            show_results=None
                        )
                        db_session.add(workspace)
                        await db_session.flush()
                        
                        workspace_id: int = workspace.id
                        await db_session.commit()
                        
                    logger.info(f"Query saved for approval - Workspace ID: {workspace_id}, UUID: {query_uuid}")
                except Exception as save_exc:
                    logger.error(f"Failed to save query for approval: {type(save_exc).__name__}: {save_exc}")
                
                try:
                    if self.notification_service:
                        request_time: str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                        await self.notification_service.send_approval_notification(
                            request_id=query_uuid,
                            username=getattr(user, 'username', str(getattr(user, 'id', 'unknown'))),
                            request_time=request_time,
                            database_name=database_name,
                            servername=server_name,
                            risk_type=query_analysis.get('risk_type', 'UNKNOWN'),
                            query=query
                        )
                except Exception as notif_exc:
                    logger.error(f"Notification send error: {type(notif_exc).__name__}: {notif_exc}")
                
                raise QueryAnalysisRejectedError(
                    message=f"{error_msg}. Query saved to your workspaces and sent for admin approval."
                )
                
            async with self.database_provider.get_session(
                user=user,
                servername=server_name,
                database_name=database_name
            ) as session:
                sql_query = text(query)
                result = await session.execute(sql_query)
                
                row_count: int = 0
                message: str = ""
                result_data: Dict[str, Any] = {}
                
                if result.returns_rows:
                    rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
                    row_count = len(rows)
                    if row_count >= config.MAX_ROW_COUNT_LIMIT:
                        message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"
                    else:
                        message = f"{row_count} rows returned"
                    
                    raw_data = [dict(row._mapping) for row in rows]
                    if not user.is_admin and masking_cols:
                        from common.security import mask_result_set
                        raw_data = mask_result_set(raw_data, masking_cols)
                        
                    result_data = {
                        "response_type": "data",
                        "data": raw_data,
                        "message": message
                    }
                else:
                    row_count = result.rowcount if result.rowcount is not None else 0
                    message = f"{row_count} rows affected"
                    result_data = {
                        "response_type": "data",
                        "data": [],
                        "message": message
                    }
                
                import json
                applied_rules_str = json.dumps(list(masking_cols)) if masking_cols else None
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=True,
                    row_count=row_count,
                    applied_masking_rules=applied_rules_str
                )
                
                if row_count > config.MAX_ROW_COUNT_WARNING:
                    logger.warning(f"Query returned high row count: {row_count} rows")
                
                logger.info(f"Query executed successfully. Result: {message}")
                return result_data
                
        except BaseServiceException:
            # Re-raise already translated service exceptions
            raise
        except Exception as e:
            error_msg: str = str(e)
            logger.error(f"Query execution failed: {error_msg}")
            if log_id:
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=False,
                    error=error_msg
                )
            raise QueryExecutionError(error_msg, original_exception=e)

    async def get_active_masking_rules(self, servername: str, database_name: str) -> list[str]:
        """
        Retrieves column names that are persistently masked for a given server and database.
        """
        async with self.app_db.get_app_db() as db:
            from sqlalchemy.future import select
            from app_database.models import Databases
            db_result = await db.execute(
                select(Databases).where(Databases.servername == servername, Databases.database_name == database_name)
            )
            db_entry = db_result.scalars().first()
            if not db_entry:
                return []
            
            rules = await self.app_db.get_masking_rules(db_entry.id)
            return [r.column_name.lower() for r in rules]
 
```
</details>



#### <a name="web_apiquery_executionrouterpy"></a> `web_api/query_execution/router.py`
**Açıklama:** Sorgu çalıştırma isteklerini alan, kullanıcının yetki düzeyine göre AST risk analizini tetikleyen, risk durumunda onay akışını başlatan ve merkezi rate limiter ile korunan HTTP API uç noktası.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/query_execution/router.py b/web_api/query_execution/router.py
index 16eeb9b..89115ad 100644
--- a/web_api/query_execution/router.py
+++ b/web_api/query_execution/router.py
@@ -1,25 +1,23 @@
 """
-Query Execution Router
-SQL query çalıştırma endpoint'leri
+Query Execution Router Module
+FastAPI router for single and multiple SQL query execution.
+All routes are strictly typed and documented.
 """
 from fastapi import APIRouter, Depends, HTTPException, Request
-from typing import List
-from slowapi import Limiter
-from slowapi.util import get_remote_address
+from typing import List, Any
+from common.limiter import limiter
 
 from query_execution import config
 from query_execution import schemas as query_models
 from query_execution.services import QueryService
 from authentication.services import get_current_user
-from dependencies import get_app_db, get_db_provider, get_session_cache, get_query_service
-from app_database.app_database import AppDatabase
+from dependencies import get_db_provider, get_query_service
 from database_provider import DatabaseProvider
 from app_database.models import User
-from session.session_cache import SessionCache
 
 router = APIRouter(prefix="/api")
 
-limiter = Limiter(key_func=get_remote_address)
+# Using centralized limiter
 
 
 @router.post("/execute_query", response_model=query_models.SQLResponse)
@@ -28,91 +26,95 @@ async def execute_query(
     request: Request,
     query_request: query_models.SQLQuery,
     current_user: User = Depends(get_current_user),
-    query_service: QueryService = Depends(get_query_service),
-    session_cache: SessionCache = Depends(get_session_cache)
-):
+    query_service: QueryService = Depends(get_query_service)
+) -> dict[str, Any]:
     """
-    Tek bir SQL query'sini çalıştırır
+    Executes a single SQL query via the query execution service.
     
-    1. Session kontrolü (kullanıcının session'ı hala geçerli mi?)
-    2. Query'yi çalıştır
-    3. Sonucu döndür
+    Args:
+        request: The FastAPI request object.
+        query_request: The SQL query execution request payload.
+        current_user: The authenticated user instance.
+        query_service: The query execution service instance.
+        
+    Returns:
+        dict[str, Any]: The query execution results or error response.
     """
-    from authentication import config
-    if session_cache.is_valid(current_user.id, timeout_minutes=config.SESSION_TIMEOUT):
-        try:
-            plain_pw = session_cache.get_password(current_user.id)
-            current_user.password = plain_pw
-        except Exception:
-            raise HTTPException(status_code=401, detail="Session password error")
-    else:
-        raise HTTPException(status_code=401, detail="Session expired")
-
-    # Query'yi çalıştır
-    result = await query_service.execute_query(
+    result: dict[str, Any] = await query_service.execute_query(
         query=query_request.query,
         user=current_user,
         server_name=query_request.servername,
-        database_name=query_request.database_name
+        database_name=query_request.database_name,
+        ad_hoc_mask_columns=query_request.ad_hoc_mask_columns
     )
-    
     return result
 
+
 @router.post("/multiple_query", response_model=query_models.MultipleQueryResponse)
 async def multiple_query(
     request: query_models.MultipleQueryRequest,
     current_user: User = Depends(get_current_user),
-    query_service: QueryService = Depends(get_query_service),
-    session_cache: SessionCache = Depends(get_session_cache)
-):
+    query_service: QueryService = Depends(get_query_service)
+) -> query_models.MultipleQueryResponse:
     """
-    Birden fazla SQL query'sini sırayla çalıştırır
+    Executes multiple SQL queries sequentially.
     
-    1. Session kontrolü
-    2. Query count kontrolü (max: config.MULTIPLE_QUERY_COUNT)
-    3. Her query'yi sırayla çalıştır
-    4. Tüm sonuçları döndür
+    Args:
+        request: The multiple SQL queries request payload.
+        current_user: The authenticated user instance.
+        query_service: The query execution service instance.
+        
+    Returns:
+        query_models.MultipleQueryResponse: The list of results for each executed query.
     """
-    from authentication import config
-    if session_cache.is_valid(current_user.id, timeout_minutes=config.SESSION_TIMEOUT):
-        try:
-            plain_pw = session_cache.get_password(current_user.id)
-            current_user.password = plain_pw
-        except Exception:
-            raise HTTPException(status_code=401, detail="Session password error")
-    else:
-        raise HTTPException(status_code=401, detail="Session expired")
-    
     if len(request.execution_info) > config.MULTIPLE_QUERY_COUNT:
         raise HTTPException(
             status_code=400,
             detail=f"Too many queries. Maximum: {config.MULTIPLE_QUERY_COUNT}"
         )
     
-    results = []
+    results: List[dict[str, Any]] = []
     
     for execution_info in request.execution_info:
-        result = await query_service.execute_query(
+        result: dict[str, Any] = await query_service.execute_query(
             query=execution_info.query,
             user=current_user,
             server_name=execution_info.servername,
-            database_name=execution_info.database_name
+            database_name=execution_info.database_name,
+            ad_hoc_mask_columns=execution_info.ad_hoc_mask_columns
         )
         results.append(result)
     
     return query_models.MultipleQueryResponse(results=results)
 
+
 @router.get("/database_information", response_model=query_models.DatabaseInformationResponse)
 async def get_database_information(
     current_user: User = Depends(get_current_user),
     db_provider: DatabaseProvider = Depends(get_db_provider)
-):
+) -> dict[str, Any]:
     """
-    Kullanıcının erişebildiği veritabanlarının listesini döndürür
+    Returns the list of databases accessible to the user per server.
     
+    Args:
+        current_user: The authenticated user instance.
+        db_provider: The database provider instance.
+        
     Returns:
-        {servername: [database_names]} formatında dictionary
+        dict[str, Any]: A mapping of servers to databases.
     """
-    db_info = db_provider.get_db_info_db()
-    
+    db_info: dict[str, Any] = db_provider.get_db_info_db()
     return {"db_info": db_info}
+
+@router.get("/masking_rules", response_model=List[str])
+async def get_masking_rules(
+    servername: str,
+    database_name: str,
+    current_user: User = Depends(get_current_user),
+    query_service: QueryService = Depends(get_query_service)
+) -> List[str]:
+    """
+    Returns the list of column names persistently masked by admin for the given server and database.
+    """
+    rules = await query_service.get_active_masking_rules(servername, database_name)
+    return rules
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (router.py)</summary>

```python
"""
Query Execution Router Module
FastAPI router for single and multiple SQL query execution.
All routes are strictly typed and documented.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Any
from common.limiter import limiter

from query_execution import config
from query_execution import schemas as query_models
from query_execution.services import QueryService
from authentication.services import get_current_user
from dependencies import get_db_provider, get_query_service
from database_provider import DatabaseProvider
from app_database.models import User

router = APIRouter(prefix="/api")

# Using centralized limiter


@router.post("/execute_query", response_model=query_models.SQLResponse)
@limiter.limit(config.RATE_LIMITER)
async def execute_query(
    request: Request,
    query_request: query_models.SQLQuery,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service)
) -> dict[str, Any]:
    """
    Executes a single SQL query via the query execution service.
    
    Args:
        request: The FastAPI request object.
        query_request: The SQL query execution request payload.
        current_user: The authenticated user instance.
        query_service: The query execution service instance.
        
    Returns:
        dict[str, Any]: The query execution results or error response.
    """
    result: dict[str, Any] = await query_service.execute_query(
        query=query_request.query,
        user=current_user,
        server_name=query_request.servername,
        database_name=query_request.database_name,
        ad_hoc_mask_columns=query_request.ad_hoc_mask_columns
    )
    return result


@router.post("/multiple_query", response_model=query_models.MultipleQueryResponse)
async def multiple_query(
    request: query_models.MultipleQueryRequest,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service)
) -> query_models.MultipleQueryResponse:
    """
    Executes multiple SQL queries sequentially.
    
    Args:
        request: The multiple SQL queries request payload.
        current_user: The authenticated user instance.
        query_service: The query execution service instance.
        
    Returns:
        query_models.MultipleQueryResponse: The list of results for each executed query.
    """
    if len(request.execution_info) > config.MULTIPLE_QUERY_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Too many queries. Maximum: {config.MULTIPLE_QUERY_COUNT}"
        )
    
    results: List[dict[str, Any]] = []
    
    for execution_info in request.execution_info:
        result: dict[str, Any] = await query_service.execute_query(
            query=execution_info.query,
            user=current_user,
            server_name=execution_info.servername,
            database_name=execution_info.database_name,
            ad_hoc_mask_columns=execution_info.ad_hoc_mask_columns
        )
        results.append(result)
    
    return query_models.MultipleQueryResponse(results=results)


@router.get("/database_information", response_model=query_models.DatabaseInformationResponse)
async def get_database_information(
    current_user: User = Depends(get_current_user),
    db_provider: DatabaseProvider = Depends(get_db_provider)
) -> dict[str, Any]:
    """
    Returns the list of databases accessible to the user per server.
    
    Args:
        current_user: The authenticated user instance.
        db_provider: The database provider instance.
        
    Returns:
        dict[str, Any]: A mapping of servers to databases.
    """
    db_info: dict[str, Any] = db_provider.get_db_info_db()
    return {"db_info": db_info}

@router.get("/masking_rules", response_model=List[str])
async def get_masking_rules(
    servername: str,
    database_name: str,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service)
) -> List[str]:
    """
    Returns the list of column names persistently masked by admin for the given server and database.
    """
    rules = await query_service.get_active_masking_rules(servername, database_name)
    return rules

```
</details>



#### <a name="web_apiquery_executionschemaspy"></a> `web_api/query_execution/schemas.py`
**Açıklama:** Sorgu istek ve yanıt şemalarına `servername` ve `database_name` gibi yeni parametreleri ekleyen Pydantic şema tanımları.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/query_execution/schemas.py b/web_api/query_execution/schemas.py
index f0bd646..c39c55e 100644
--- a/web_api/query_execution/schemas.py
+++ b/web_api/query_execution/schemas.py
@@ -11,6 +11,7 @@ class SQLQuery(BaseModel):
     servername: str
     database_name: str
     query: str
+    ad_hoc_mask_columns: Optional[List[str]] = None
 
 
 class SQLResponse(BaseModel):
@@ -26,6 +27,7 @@ class ExecutionInfo(BaseModel):
     servername: str
     database_name: str
     query: str
+    ad_hoc_mask_columns: Optional[List[str]] = None
 
 
 class MultipleQueryRequest(BaseModel):
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (schemas.py)</summary>

```python
"""
Query Execution Schemas
Pydantic models for query execution endpoints
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class SQLQuery(BaseModel):
    """Single SQL query request"""
    servername: str
    database_name: str
    query: str
    ad_hoc_mask_columns: Optional[List[str]] = None


class SQLResponse(BaseModel):
    """SQL query response"""
    response_type: str  # "data" or "error"
    data: List[Dict[str, Any]]
    message: Optional[str] = None
    error: Optional[str] = None


class ExecutionInfo(BaseModel):
    """Execution information for multiple queries"""
    servername: str
    database_name: str
    query: str
    ad_hoc_mask_columns: Optional[List[str]] = None


class MultipleQueryRequest(BaseModel):
    """Multiple query execution request"""
    execution_info: List[ExecutionInfo]


class MultipleQueryResponse(BaseModel):
    """Multiple query execution response"""
    results: List[SQLResponse]


class DatabaseInformationResponse(BaseModel):
    """
    Database information response with server metadata
    
    Format:
        {
            servername: {
                "databases": [database_names],
                "technology": "mssql" | "mysql" | "postgresql"
            }
        }
    """
    db_info: Dict[str, Dict[str, Any]]

```
</details>



#### <a name="web_apiquery_execution__init__py"></a> `web_api/query_execution/__init__.py`
**Açıklama:** Sorgu yürütme paketi dışa aktarımları.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/query_execution/__init__.py b/web_api/query_execution/__init__.py
index 6cad07f..fe0fc58 100644
--- a/web_api/query_execution/__init__.py
+++ b/web_api/query_execution/__init__.py
@@ -1 +1,4 @@
-from .services import QueryService
\ No newline at end of file
+from .services import QueryService
+from .exceptions import QueryExecutionError, QueryAnalysisRejectedError
+
+__all__ = ["QueryService", "QueryExecutionError", "QueryAnalysisRejectedError"]
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (__init__.py)</summary>

```python
from .services import QueryService
from .exceptions import QueryExecutionError, QueryAnalysisRejectedError

__all__ = ["QueryService", "QueryExecutionError", "QueryAnalysisRejectedError"]
```
</details>




### 📂 Kategori 5: Çalışma Alanları Yönetimi (Workspace Management)
---

#### <a name="web_apiworkspacesexceptionspy"></a> `web_api/workspaces/exceptions.py`
**Açıklama:** Çalışma alanları için `WorkspaceNotFoundError` ve yetkisiz erişim denemeleri için `WorkspaceAccessDeniedError` özel domain hatalarını tanımlar.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/workspaces/exceptions.py b/web_api/workspaces/exceptions.py
new file mode 100644
index 0000000..d461ce4
--- /dev/null
+++ b/web_api/workspaces/exceptions.py
@@ -0,0 +1,15 @@
+"""
+Workspaces Exceptions
+Custom exceptions for the workspaces service layer.
+"""
+from common.exceptions import BaseServiceException
+
+class WorkspaceNotFoundError(BaseServiceException):
+    """Raised when a requested workspace is not found."""
+    status_code = 404
+    code = "WORKSPACE_NOT_FOUND"
+
+class WorkspaceAccessDeniedError(BaseServiceException):
+    """Raised when a user attempts to access a workspace they do not own."""
+    status_code = 403
+    code = "WORKSPACE_ACCESS_DENIED"
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (exceptions.py)</summary>

```python
"""
Workspaces Exceptions
Custom exceptions for the workspaces service layer.
"""
from common.exceptions import BaseServiceException

class WorkspaceNotFoundError(BaseServiceException):
    """Raised when a requested workspace is not found."""
    status_code = 404
    code = "WORKSPACE_NOT_FOUND"

class WorkspaceAccessDeniedError(BaseServiceException):
    """Raised when a user attempts to access a workspace they do not own."""
    status_code = 403
    code = "WORKSPACE_ACCESS_DENIED"

```
</details>



#### <a name="web_apiworkspacesrouterpy"></a> `web_api/workspaces/router.py`
**Açıklama:** Çalışma alanı CRUD (oluşturma, okuma, güncelleme, silme) işlemlerini gerçekleştiren ve hata yönetimini yeni exception mimarisine adapte eden HTTP yönlendiricisi.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/workspaces/router.py b/web_api/workspaces/router.py
index f416357..918264f 100644
--- a/web_api/workspaces/router.py
+++ b/web_api/workspaces/router.py
@@ -2,14 +2,14 @@
 Workspace Router
 User workspace (saved query) management endpoints
 """
+from typing import Any
 from fastapi import APIRouter, Depends, status, HTTPException, Response, Request
-from fastapi.responses import FileResponse
-from .schemas import *
+from .schemas import WorkspaceCreate, WorkspaceUpdate, WorkspaceList, WorkspaceExecutionRequest
 
-from dependencies import get_app_db, get_workspace_service, ensure_owner, get_session_cache, get_db_provider
+from dependencies import get_app_db, get_workspace_service, ensure_owner, get_db_provider
 from authentication.services import get_current_user
 
-from app_database.models import User, Workspace, QueryData
+from app_database.models import User, Workspace
 from app_database import AppDatabase
 
 from .services import WorkspaceService
@@ -149,34 +149,45 @@ async def get_workspace_by_id(
 @router.post("/execute_workspace/{workspace_id}", response_model=query_models.SQLResponse)
 async def execute_workspace(
     workspace_id: int,
-    request: Request,
+    execution_request: WorkspaceExecutionRequest = None,
     current_user: User = Depends(get_current_user),
     workspace_service: WorkspaceService = Depends(get_workspace_service),
     app_db: AppDatabase = Depends(get_app_db),
-    session_cache = Depends(get_session_cache),
     db_provider: DatabaseProvider = Depends(get_db_provider)
-):
+) -> dict[str, Any]:
     """
-    Execute the stored query for a workspace server-side.
+    Execute the stored query for a workspace server-side using centralized credentials.
 
     Requirements:
-    - User must have a valid session.
+    - User must have a valid JWT session.
     - Workspace must exist.
     - Workspace.show_results must be True and queryData.status == 'approved_with_results'.
 
     Only the workspace_id is accepted from the client to avoid arbitrary SQL execution.
+    
+    Args:
+        workspace_id: ID of the workspace to execute.
+        execution_request: The workspace execution request payload.
+        current_user: The authenticated user instance.
+        workspace_service: The workspace service instance.
+        app_db: The application database manager.
+        db_provider: The database provider instance.
+        
+    Returns:
+        dict[str, Any]: The query execution results or error details.
     """
-    # Delegate execution to WorkspaceService which enforces approval rules (including session validation)
-    result = await workspace_service.execute_workspace(
+    # Delegate execution to WorkspaceService which enforces approval rules (using centralized credentials)
+    ad_hoc = execution_request.ad_hoc_mask_columns if execution_request else None
+    result: dict[str, Any] = await workspace_service.execute_workspace(
         workspace_id=workspace_id,
         current_user=current_user,
-        session_cache=session_cache,
-        db_provider=db_provider
+        db_provider=db_provider,
+        ad_hoc_mask_columns=ad_hoc
     )
 
     if result.get("response_type") == "error":
         # map to HTTP errors for common cases
-        err = result.get("error", "Execution failed")
+        err: str = str(result.get("error", "Execution failed"))
         if "not found" in err.lower():
             raise HTTPException(status_code=404, detail=err)
         if "not approved" in err.lower() or "not approved for execution" in err.lower():
@@ -187,16 +198,3 @@ async def execute_workspace(
 
     return result
 
-
-@router.get("/workspaces/{workspace_id}/execute", response_class=FileResponse)
-def workspace_execute_page(
-    workspace_id: int,
-    current_user: User = Depends(get_current_user),
-    _ws: Workspace = Depends(ensure_owner)
-):
-    """
-    Serve a lightweight workspace execution page (static HTML).
-
-    Access is limited to the workspace owner by the `ensure_owner` dependency.
-    """
-    return FileResponse("templates/workspace_execute.html")
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (router.py)</summary>

```python
"""
Workspace Router
User workspace (saved query) management endpoints
"""
from typing import Any
from fastapi import APIRouter, Depends, status, HTTPException, Response, Request
from .schemas import WorkspaceCreate, WorkspaceUpdate, WorkspaceList, WorkspaceExecutionRequest

from dependencies import get_app_db, get_workspace_service, ensure_owner, get_db_provider
from authentication.services import get_current_user

from app_database.models import User, Workspace
from app_database import AppDatabase

from .services import WorkspaceService
from query_execution import schemas as query_models
from database_provider import DatabaseProvider

router = APIRouter(prefix="/api")

@router.post("/workspaces")
async def create_workspace(
    request: WorkspaceCreate,
    current_user : User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Creates a new workspace
    
    Args:
        request: Workspace creation data (name, query, servername, database)
    
    Returns:
        Dict: {"success": true, "workspace_id": int}
    
    Raises:
        HTTPException 400: If workspace cannot be created
    """
    async with app_db.get_app_db() as db:
        result = await service.create_workspace(db=db, workspace_data=request, user_id=current_user.id)
    if result.get("success"):
        return result
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Workspace could not be created."))

@router.get("/workspaces", response_model=WorkspaceList)
async def get_workspaces(
    current_user : User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Lists all workspaces of the user
    
    Returns:
        WorkspaceList: List of workspaces belonging to the user
    """
    async with app_db.get_app_db() as db:
        workspaces = await service.get_workspace_by_id(db, current_user.id)
        return {"workspaces": workspaces}

@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: int,
    _ws: Workspace = Depends(ensure_owner),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Deletes a workspace
    
    Args:
        workspace_id: ID of the workspace to delete
    
    Returns:
        Response: 200 OK
    
    Raises:
        HTTPException 400: If workspace cannot be deleted
    
    Note:
        Related queryData record is also deleted
    """
    async with app_db.get_app_db() as db:
        success = await service.delete_workspace_by_id(workspace_id, db=db)
        if success:
            return Response(status_code=status.HTTP_200_OK)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace could not be deleted.")

@router.put("/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: int,
    request: WorkspaceUpdate,
    _ws: Workspace = Depends(ensure_owner),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Updates workspace (query and/or status)
    
    Args:
        workspace_id: ID of the workspace to update
        request: Update data (query, status)
    
    Returns:
        Response: 200 OK
    
    Raises:
        HTTPException 400: If workspace cannot be updated
    """
    async with app_db.get_app_db() as db:
        success = await service.update_workspace(db, workspace_id, query=request.query, status=request.status)
        if success:
            return Response(status_code=status.HTTP_200_OK)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace could not be updated.")
        
@router.get("/get_workspace_by_id/{workspace_id}")
async def get_workspace_by_id(
    workspace_id: int,
    _ws: Workspace = Depends(ensure_owner),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Retrieves workspace details by ID
    
    Args:
        workspace_id: ID of the workspace to retrieve details for
    
    Returns:
        Dict: Workspace details (name, query, servername, database, status)
    
    Raises:
        HTTPException 404: If workspace is not found or does not belong to the user
    
    Note:
        Only workspace owner can access
    """
    async with app_db.get_app_db() as db:
        result = await service.get_workspace_detail_by_id(db, workspace_id, _ws.user_id)
        if not result:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return result


@router.post("/execute_workspace/{workspace_id}", response_model=query_models.SQLResponse)
async def execute_workspace(
    workspace_id: int,
    execution_request: WorkspaceExecutionRequest = None,
    current_user: User = Depends(get_current_user),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider)
) -> dict[str, Any]:
    """
    Execute the stored query for a workspace server-side using centralized credentials.

    Requirements:
    - User must have a valid JWT session.
    - Workspace must exist.
    - Workspace.show_results must be True and queryData.status == 'approved_with_results'.

    Only the workspace_id is accepted from the client to avoid arbitrary SQL execution.
    
    Args:
        workspace_id: ID of the workspace to execute.
        execution_request: The workspace execution request payload.
        current_user: The authenticated user instance.
        workspace_service: The workspace service instance.
        app_db: The application database manager.
        db_provider: The database provider instance.
        
    Returns:
        dict[str, Any]: The query execution results or error details.
    """
    # Delegate execution to WorkspaceService which enforces approval rules (using centralized credentials)
    ad_hoc = execution_request.ad_hoc_mask_columns if execution_request else None
    result: dict[str, Any] = await workspace_service.execute_workspace(
        workspace_id=workspace_id,
        current_user=current_user,
        db_provider=db_provider,
        ad_hoc_mask_columns=ad_hoc
    )

    if result.get("response_type") == "error":
        # map to HTTP errors for common cases
        err: str = str(result.get("error", "Execution failed"))
        if "not found" in err.lower():
            raise HTTPException(status_code=404, detail=err)
        if "not approved" in err.lower() or "not approved for execution" in err.lower():
            raise HTTPException(status_code=403, detail=err)
        if "session" in err.lower():
            raise HTTPException(status_code=401, detail=err)
        raise HTTPException(status_code=400, detail=err)

    return result


```
</details>



#### <a name="web_apiworkspacesservicespy"></a> `web_api/workspaces/services.py`
**Açıklama:** Kullanıcıların sorgularını kaydettiği çalışma alanlarının iş mantığını yöneten, yetki kontrollerini gerçekleştiren ve hata durumlarında doğrudan domain hataları fırlatan servis katmanı.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/workspaces/services.py b/web_api/workspaces/services.py
index ea677ed..c0d118f 100644
--- a/web_api/workspaces/services.py
+++ b/web_api/workspaces/services.py
@@ -2,7 +2,8 @@
 Workspace Service Layer
 User workspace (saved query) management operations
 """
-from app_database.models import QueryData, Workspace
+from typing import Any, List, Dict
+from app_database.models import QueryData, Workspace, Databases
 from app_database.app_database import AppDatabase
 from sqlalchemy.ext.asyncio import AsyncSession
 import uuid
@@ -11,9 +12,14 @@ from sqlalchemy.sql import select
 from sqlalchemy.sql import text
 from query_execution import config as query_config
 from database_provider import DatabaseProvider
-from session.session_cache import SessionCache
 from app_database.models import User
 
+import logging
+from common.exceptions import BaseServiceException
+from workspaces.exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError
+
+logger = logging.getLogger(__name__)
+
 class WorkspaceService:
     """
     Workspace CRUD operations service
@@ -72,8 +78,8 @@ class WorkspaceService:
             return {"success": True, "workspace_id": workspace.id}
         except Exception as e:
             await db.rollback()
-            print(f"Error creating workspace: {e}")
-            return {"success": False, "error": str(e)}
+            logger.error(f"Error creating workspace: {e}")
+            raise BaseServiceException(f"Error creating workspace: {str(e)}", original_exception=e)
         
     async def get_workspace_by_id(self, db: AsyncSession, user_id: int):
         """
@@ -135,7 +141,7 @@ class WorkspaceService:
             workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
             workspace = workspace_result.scalars().first()
             if not workspace:
-                return False
+                raise WorkspaceNotFoundError("Workspace not found")
             
             query_id = workspace.query_id
             
@@ -149,10 +155,12 @@ class WorkspaceService:
             
             await db.commit()
             return True
+        except BaseServiceException:
+            raise
         except Exception as e:
             await db.rollback()
-            print(f"Error deleting workspace: {e}")
-            return False
+            logger.error(f"Error deleting workspace: {e}")
+            raise BaseServiceException(f"Error deleting workspace: {str(e)}", original_exception=e)
     
     async def update_workspace(self, db: AsyncSession, workspace_id: int, query: str = None, status: str = None):
         """
@@ -171,12 +179,12 @@ class WorkspaceService:
             workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
             workspace = workspace_result.scalars().first()
             if not workspace:
-                return False
+                raise WorkspaceNotFoundError("Workspace not found")
             
             query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
             query_data = query_result.scalars().first()
             if not query_data:
-                return False
+                raise WorkspaceNotFoundError("Query data not found for this workspace")
             
             if query:
                 query_data.query = query
@@ -184,10 +192,12 @@ class WorkspaceService:
                 query_data.status = status
             await db.commit()
             return True
+        except BaseServiceException:
+            raise
         except Exception as e:
             await db.rollback()
-            print(f"Error updating workspace: {e}")
-            return False
+            logger.error(f"Error updating workspace: {e}")
+            raise BaseServiceException(f"Error updating workspace: {str(e)}", original_exception=e)
     
     async def get_workspace_detail_by_id(self, db: AsyncSession, workspace_id: int, user_id: int):
         """
@@ -203,12 +213,16 @@ class WorkspaceService:
         """
         workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
         workspace = workspace_result.scalars().first()
-        if not workspace or workspace.user_id != user_id:
-            return None
+        if not workspace:
+            raise WorkspaceNotFoundError("Workspace not found")
+        if workspace.user_id != user_id:
+            raise WorkspaceAccessDeniedError("You do not own this workspace")
+            
         query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
         query_data = query_result.scalars().first()
         if not query_data:
-            return None
+            raise WorkspaceNotFoundError("Query data not found for this workspace")
+            
         return {
             "id": workspace.id,
             "name": workspace.name,
@@ -222,68 +236,101 @@ class WorkspaceService:
             "is_owner": True
         }
 
-    async def execute_workspace(self, workspace_id: int, current_user: User, session_cache: SessionCache, db_provider: DatabaseProvider):
+    async def execute_workspace(self, workspace_id: int, current_user: User, db_provider: DatabaseProvider, ad_hoc_mask_columns: list[str] = None) -> dict[str, Any]:
         """
         Executes a stored workspace query after enforcing approval rules.
+        Uses centralized service account credentials, requiring no user password caching.
 
         Args:
-            workspace_id: ID of the workspace to execute
-            current_user: Calling user
-            session_cache: SessionCache instance
-            db_provider: DatabaseProvider instance
+            workspace_id: ID of the workspace to execute.
+            current_user: The authenticated calling user instance.
+            db_provider: The database connection provider.
+            ad_hoc_mask_columns: Temporary columns to mask for this transaction (optional).
 
         Returns:
-            Dict: Execution result
+            dict[str, Any]: A dictionary containing execution status and data or error details.
         """
-        # Session validation
-        from authentication import config as auth_config
-        try:
-            if session_cache.is_valid(current_user.id, timeout_minutes=auth_config.SESSION_TIMEOUT):
-                plain_pw = session_cache.get_password(current_user.id)
-                current_user.password = plain_pw
-            else:
-                return {"response_type": "error", "data": [], "error": "Session expired"}
-        except Exception:
-            return {"response_type": "error", "data": [], "error": "Session password error"}
-
         # Load workspace and query
         async with self.app_db.get_app_db() as db:
             workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
-            workspace = workspace_result.scalars().first()
+            workspace: Workspace | None = workspace_result.scalars().first()
             if not workspace:
-                return {"response_type": "error", "data": [], "error": "Workspace not found"}
+                raise WorkspaceNotFoundError("Workspace not found")
+
+            if workspace.user_id != current_user.id:
+                raise WorkspaceAccessDeniedError("You do not own this workspace")
 
             query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
-            query_data = query_result.scalars().first()
+            query_data: QueryData | None = query_result.scalars().first()
             if not query_data:
-                return {"response_type": "error", "data": [], "error": "Query data not found"}
+                raise WorkspaceNotFoundError("Query data not found for this workspace")
+                
             # enforce approval
             if not workspace.show_results or query_data.status != "approved_with_results":
-                return {"response_type": "error", "data": [], "error": "This workspace is not approved for execution"}
+                from query_execution.exceptions import QueryAnalysisRejectedError
+                raise QueryAnalysisRejectedError("This workspace is not approved for execution")
 
-        log_id = None
+        log_id: int | None = None
         try:
+            logger.info(f"Executing approved workspace {workspace_id} on server '{query_data.servername}'")
             log_id = await self.app_db.create_log(user=current_user, query=query_data.query, machine_name=query_data.servername, approved_execution=True)
 
-            async with db_provider.get_session(user=current_user, servername=query_data.servername, database_name=query_data.database_name) as session:
-                sql_query = text(query_data.query)
-                result = await session.execute(sql_query)
-                rows = result.fetchmany(size=query_config.MAX_ROW_COUNT_LIMIT)
-                row_count = len(rows)
-
-                if row_count > query_config.MAX_ROW_COUNT_LIMIT:
-                    rows = rows[:query_config.MAX_ROW_COUNT_LIMIT]
-                    message = f"Truncated to MAX_ROW_COUNT_LIMIT ({query_config.MAX_ROW_COUNT_LIMIT})"
-                else:
-                    message = f"{row_count} rows affected"
-
-                result_data = [dict(row._mapping) for row in rows]
+            # Fetch persistent database masking rules & merge with user ad-hoc rules
+            db_id = None
+            masking_cols = set()
+            async with self.app_db.get_app_db() as db_session:
+                db_result = await db_session.execute(
+                    select(Databases).where(Databases.servername == query_data.servername, Databases.database_name == query_data.database_name)
+                )
+                db_entry = db_result.scalars().first()
+                if db_entry:
+                    db_id = db_entry.id
+            
+            if db_id:
+                rules = await self.app_db.get_masking_rules(db_id)
+                for rule in rules:
+                    masking_cols.add(rule.column_name.lower())
+            
+            if ad_hoc_mask_columns:
+                for col in ad_hoc_mask_columns:
+                    masking_cols.add(col.lower())
 
-            await self.app_db.update_log(log_id=log_id, successfull=True, row_count=row_count)
+            async with db_provider.get_session(user=current_user, servername=query_data.servername, database_name=query_data.database_name) as session:
+                  sql_query = text(query_data.query)
+                  result = await session.execute(sql_query)
+                  
+                  row_count: int = 0
+                  message: str = ""
+                  result_data: list[dict[str, Any]] = []
+                  
+                  if result.returns_rows:
+                      rows = result.fetchmany(size=query_config.MAX_ROW_COUNT_LIMIT)
+                      row_count = len(rows)
+                      if row_count >= query_config.MAX_ROW_COUNT_LIMIT:
+                          message = f"Truncated to MAX_ROW_COUNT_LIMIT ({query_config.MAX_ROW_COUNT_LIMIT})"
+                      else:
+                          message = f"{row_count} rows returned"
+                      
+                      result_data = [dict(row._mapping) for row in rows]
+                      if not current_user.is_admin and masking_cols:
+                          from common.security import mask_result_set
+                          result_data = mask_result_set(result_data, masking_cols)
+                  else:
+                      row_count = result.rowcount if result.rowcount is not None else 0
+                      message = f"{row_count} rows affected"
+                      result_data = []
 
+            import json
+            applied_rules_str = json.dumps(list(masking_cols)) if masking_cols else None
+            await self.app_db.update_log(log_id=log_id, successfull=True, row_count=row_count, applied_masking_rules=applied_rules_str)
+            
+            logger.info(f"Workspace {workspace_id} executed successfully. Result: {message}")
             return {"response_type": "data", "data": result_data, "message": message}
 
+        except BaseServiceException:
+            raise
         except Exception as e:
             if log_id:
                 await self.app_db.update_log(log_id=log_id, successfull=False, error=str(e))
-            return {"response_type": "error", "data": [], "error": str(e)}
\ No newline at end of file
+            from query_execution.exceptions import QueryExecutionError
+            raise QueryExecutionError(str(e), original_exception=e)
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (services.py)</summary>

```python
"""
Workspace Service Layer
User workspace (saved query) management operations
"""
from typing import Any, List, Dict
from app_database.models import QueryData, Workspace, Databases
from app_database.app_database import AppDatabase
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from .schemas import WorkspaceInfo, WorkspaceCreate
from sqlalchemy.sql import select
from sqlalchemy.sql import text
from query_execution import config as query_config
from database_provider import DatabaseProvider
from app_database.models import User

import logging
from common.exceptions import BaseServiceException
from workspaces.exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError

logger = logging.getLogger(__name__)

class WorkspaceService:
    """
    Workspace CRUD operations service
    
    Manages users' operations of storing, editing, deleting,
    and listing queries in workspaces.
    
    Attributes:
        app_db: Application database instance
    """

    def __init__(self, app_db: AppDatabase):
        """
        Initializes WorkspaceService
        
        Args:
            app_db: AppDatabase instance
        """
        self.app_db = app_db

    async def create_workspace(self, db: AsyncSession, workspace_data: WorkspaceCreate, user_id: int):
        """
        Creates a new workspace.
        
        Args:
            db: Async database session
            workspace_data: Workspace creation schema
            user_id: ID of the user creating the workspace
        
        Returns:
            Dict: Result with workspace_id or error
        """
        try:
            new_query_data = QueryData(
                    user_id=user_id,
                    servername=workspace_data.servername,
                    database_name=workspace_data.database_name,
                    query=workspace_data.query,
                    uuid=str(uuid.uuid4()),
                    status="saved_in_workspace"
                )
            
            db.add(new_query_data)
            await db.flush()

            """Workspace creation operation"""
            workspace = Workspace(
                name=workspace_data.name,
                description=workspace_data.description,
                user_id=user_id,
                query_id=new_query_data.id
            )
            db.add(workspace)
            await db.commit()
            await db.refresh(workspace)
            return {"success": True, "workspace_id": workspace.id}
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating workspace: {e}")
            raise BaseServiceException(f"Error creating workspace: {str(e)}", original_exception=e)
        
    async def get_workspace_by_id(self, db: AsyncSession, user_id: int):
        """
        Retrieves all workspaces for the user.
        
        Args:
            db: Async database session
            user_id: ID of the user whose workspaces will be retrieved
        
        Returns:
            List[WorkspaceInfo]: List of workspaces (can be empty)
        """
        
        results = await db.execute(
            select(Workspace).where(Workspace.user_id == user_id)
        )
        workspaces = results.scalars().all()
        if not workspaces:
            return []

        query_ids = [ws.query_id for ws in workspaces]

        query_data_results = await db.execute(
            select(QueryData).where(QueryData.id.in_(query_ids))
        )
        query_data_map = {qd.id: qd for qd in query_data_results.scalars().all()}

        workspace_list = []
        for ws in workspaces:
            query_data = query_data_map.get(ws.query_id)
            if query_data:
                print(f"[DEBUG] Workspace {ws.id}: status={query_data.status}, show_results={getattr(ws, 'show_results', None)}")
                workspace_list.append(WorkspaceInfo(
                    id=ws.id,
                    name=ws.name,
                    description=ws.description,
                    query=query_data.query,
                    servername=query_data.servername,
                    database_name=query_data.database_name,
                    status=query_data.status,
                    show_results=getattr(ws, 'show_results', None),
                    owner_id=ws.user_id,
                    is_owner=True
                ))
        return workspace_list
    
    async def delete_workspace_by_id(self, workspace_id: int, db: AsyncSession):
        """
        Deletes workspace and related queryData.
        
        Args:
            workspace_id: ID of the workspace to delete
            db: Async database session
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                raise WorkspaceNotFoundError("Workspace not found")
            
            query_id = workspace.query_id
            
            await db.delete(workspace)
            
            if query_id:
                query_result = await db.execute(select(QueryData).where(QueryData.id == query_id))
                query_data = query_result.scalars().first()
                if query_data:
                    await db.delete(query_data)
            
            await db.commit()
            return True
        except BaseServiceException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting workspace: {e}")
            raise BaseServiceException(f"Error deleting workspace: {str(e)}", original_exception=e)
    
    async def update_workspace(self, db: AsyncSession, workspace_id: int, query: str = None, status: str = None):
        """
        Updates workspace query or status.
        
        Args:
            db: Async database session
            workspace_id: ID of the workspace to update
            query: New query (optional)
            status: New status (optional)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                raise WorkspaceNotFoundError("Workspace not found")
            
            query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
            query_data = query_result.scalars().first()
            if not query_data:
                raise WorkspaceNotFoundError("Query data not found for this workspace")
            
            if query:
                query_data.query = query
            if status:
                query_data.status = status
            await db.commit()
            return True
        except BaseServiceException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating workspace: {e}")
            raise BaseServiceException(f"Error updating workspace: {str(e)}", original_exception=e)
    
    async def get_workspace_detail_by_id(self, db: AsyncSession, workspace_id: int, user_id: int):
        """
        Retrieves details of a specific workspace.
        
        Args:
            db: Async database session
            workspace_id: ID of the workspace to retrieve details for
            user_id: ID of the requesting user (for authorization check)
        
        Returns:
            Dict | None: Workspace details or None
        """
        workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
        workspace = workspace_result.scalars().first()
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found")
        if workspace.user_id != user_id:
            raise WorkspaceAccessDeniedError("You do not own this workspace")
            
        query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
        query_data = query_result.scalars().first()
        if not query_data:
            raise WorkspaceNotFoundError("Query data not found for this workspace")
            
        return {
            "id": workspace.id,
            "name": workspace.name,
            "description": workspace.description,
            "query": query_data.query,
            "servername": query_data.servername,
            "database_name": query_data.database_name,
            "status": query_data.status,
            "show_results": getattr(workspace, 'show_results', None),
            "owner_id": workspace.user_id,
            "is_owner": True
        }

    async def execute_workspace(self, workspace_id: int, current_user: User, db_provider: DatabaseProvider, ad_hoc_mask_columns: list[str] = None) -> dict[str, Any]:
        """
        Executes a stored workspace query after enforcing approval rules.
        Uses centralized service account credentials, requiring no user password caching.

        Args:
            workspace_id: ID of the workspace to execute.
            current_user: The authenticated calling user instance.
            db_provider: The database connection provider.
            ad_hoc_mask_columns: Temporary columns to mask for this transaction (optional).

        Returns:
            dict[str, Any]: A dictionary containing execution status and data or error details.
        """
        # Load workspace and query
        async with self.app_db.get_app_db() as db:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace: Workspace | None = workspace_result.scalars().first()
            if not workspace:
                raise WorkspaceNotFoundError("Workspace not found")

            if workspace.user_id != current_user.id:
                raise WorkspaceAccessDeniedError("You do not own this workspace")

            query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
            query_data: QueryData | None = query_result.scalars().first()
            if not query_data:
                raise WorkspaceNotFoundError("Query data not found for this workspace")
                
            # enforce approval
            if not workspace.show_results or query_data.status != "approved_with_results":
                from query_execution.exceptions import QueryAnalysisRejectedError
                raise QueryAnalysisRejectedError("This workspace is not approved for execution")

        log_id: int | None = None
        try:
            logger.info(f"Executing approved workspace {workspace_id} on server '{query_data.servername}'")
            log_id = await self.app_db.create_log(user=current_user, query=query_data.query, machine_name=query_data.servername, approved_execution=True)

            # Fetch persistent database masking rules & merge with user ad-hoc rules
            db_id = None
            masking_cols = set()
            async with self.app_db.get_app_db() as db_session:
                db_result = await db_session.execute(
                    select(Databases).where(Databases.servername == query_data.servername, Databases.database_name == query_data.database_name)
                )
                db_entry = db_result.scalars().first()
                if db_entry:
                    db_id = db_entry.id
            
            if db_id:
                rules = await self.app_db.get_masking_rules(db_id)
                for rule in rules:
                    masking_cols.add(rule.column_name.lower())
            
            if ad_hoc_mask_columns:
                for col in ad_hoc_mask_columns:
                    masking_cols.add(col.lower())

            async with db_provider.get_session(user=current_user, servername=query_data.servername, database_name=query_data.database_name) as session:
                  sql_query = text(query_data.query)
                  result = await session.execute(sql_query)
                  
                  row_count: int = 0
                  message: str = ""
                  result_data: list[dict[str, Any]] = []
                  
                  if result.returns_rows:
                      rows = result.fetchmany(size=query_config.MAX_ROW_COUNT_LIMIT)
                      row_count = len(rows)
                      if row_count >= query_config.MAX_ROW_COUNT_LIMIT:
                          message = f"Truncated to MAX_ROW_COUNT_LIMIT ({query_config.MAX_ROW_COUNT_LIMIT})"
                      else:
                          message = f"{row_count} rows returned"
                      
                      result_data = [dict(row._mapping) for row in rows]
                      if not current_user.is_admin and masking_cols:
                          from common.security import mask_result_set
                          result_data = mask_result_set(result_data, masking_cols)
                  else:
                      row_count = result.rowcount if result.rowcount is not None else 0
                      message = f"{row_count} rows affected"
                      result_data = []

            import json
            applied_rules_str = json.dumps(list(masking_cols)) if masking_cols else None
            await self.app_db.update_log(log_id=log_id, successfull=True, row_count=row_count, applied_masking_rules=applied_rules_str)
            
            logger.info(f"Workspace {workspace_id} executed successfully. Result: {message}")
            return {"response_type": "data", "data": result_data, "message": message}

        except BaseServiceException:
            raise
        except Exception as e:
            if log_id:
                await self.app_db.update_log(log_id=log_id, successfull=False, error=str(e))
            from query_execution.exceptions import QueryExecutionError
            raise QueryExecutionError(str(e), original_exception=e)
```
</details>



#### <a name="web_apiworkspacesschemaspy"></a> `web_api/workspaces/schemas.py`
**Açıklama:** Çalışma alanları için girdi doğrulama ve çıktı serileştirme kurallarını belirleyen Pydantic şemaları.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/workspaces/schemas.py b/web_api/workspaces/schemas.py
index 9337726..847e24b 100644
--- a/web_api/workspaces/schemas.py
+++ b/web_api/workspaces/schemas.py
@@ -59,4 +59,9 @@ class WorkspaceUpdate(BaseModel):
         status: Status to update (optional)
     """
     query: str
-    status: Optional[str] = None
\ No newline at end of file
+    status: Optional[str] = None
+
+
+class WorkspaceExecutionRequest(BaseModel):
+    """Workspace execution request containing ad-hoc columns to mask"""
+    ad_hoc_mask_columns: Optional[List[str]] = None
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (schemas.py)</summary>

```python
"""
Workspace Schemas
Pydantic models for workspace endpoints
"""
from pydantic import BaseModel
from typing import Optional, List

class WorkspaceInfo(BaseModel):
    """
    Workspace information (response)
    
    Attributes:
        id: Workspace ID
        name: Workspace name
        description: Workspace description (optional)
        query: Saved SQL query
        servername: Target SQL Server
        database_name: Target database
        status: Query status (saved_in_workspace, waiting_for_approval, etc.)
    """
    id: int
    name: str
    description: Optional[str] = None
    query: str
    servername: str
    database_name: str
    status: str
    show_results: Optional[bool] = None
    owner_id: int
    is_owner: Optional[bool] = None

class WorkspaceCreate(BaseModel):
    """
    Workspace creation schema
    
    Attributes:
        name: Workspace name
        description: Workspace description (optional)
        query: SQL query to save
        servername: Target SQL Server
        database_name: Target database
    """
    name: str
    description: Optional[str] = None
    query: str
    servername: str
    database_name: str

class WorkspaceList(BaseModel):
    """Workspace list response schema"""
    workspaces: List[WorkspaceInfo]

class WorkspaceUpdate(BaseModel):
    """
    Workspace update schema
    
    Attributes:
        query: SQL query to update
        status: Status to update (optional)
    """
    query: str
    status: Optional[str] = None


class WorkspaceExecutionRequest(BaseModel):
    """Workspace execution request containing ad-hoc columns to mask"""
    ad_hoc_mask_columns: Optional[List[str]] = None
```
</details>



#### <a name="web_apiworkspaces__init__py"></a> `web_api/workspaces/__init__.py`
**Açıklama:** Çalışma alanı paketi başlatma dosyası.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/workspaces/__init__.py b/web_api/workspaces/__init__.py
index fb4791a..a6e4802 100644
--- a/web_api/workspaces/__init__.py
+++ b/web_api/workspaces/__init__.py
@@ -2,3 +2,7 @@
 Workspaces Module
 Kullanıcı workspace (kaydedilmiş query) yönetimi
 """
+from .services import WorkspaceService
+from .exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError
+
+__all__ = ["WorkspaceService", "WorkspaceNotFoundError", "WorkspaceAccessDeniedError"]
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (__init__.py)</summary>

```python
"""
Workspaces Module
Kullanıcı workspace (kaydedilmiş query) yönetimi
"""
from .services import WorkspaceService
from .exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError

__all__ = ["WorkspaceService", "WorkspaceNotFoundError", "WorkspaceAccessDeniedError"]

```
</details>




### 📂 Kategori 6: Yönetici Onay ve Veritabanı İşlemleri (Admin Operations & Approvals)
---

#### <a name="web_apiadminexceptionspy"></a> `web_api/admin/exceptions.py`
**Açıklama:** Yönetici işlemlerinde oluşabilecek özel hata sınıflarını barındıran modül.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/admin/exceptions.py b/web_api/admin/exceptions.py
new file mode 100644
index 0000000..fcdcab3
--- /dev/null
+++ b/web_api/admin/exceptions.py
@@ -0,0 +1,10 @@
+"""
+Admin Exceptions
+Custom exceptions for administrative services.
+"""
+from common.exceptions import BaseServiceException
+
+class DatabaseAlreadyExistsError(BaseServiceException):
+    """Raised when trying to register a database server/name combination that already exists."""
+    status_code = 400
+    code = "DATABASE_ALREADY_EXISTS"
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (exceptions.py)</summary>

```python
"""
Admin Exceptions
Custom exceptions for administrative services.
"""
from common.exceptions import BaseServiceException

class DatabaseAlreadyExistsError(BaseServiceException):
    """Raised when trying to register a database server/name combination that already exists."""
    status_code = 400
    code = "DATABASE_ALREADY_EXISTS"

```
</details>



#### <a name="web_apiadminrouterpy"></a> `web_api/admin/router.py`
**Açıklama:** Admin onay bekleyen sorguları listeleme, onaylama, reddetme ve veritabanı ekleme uç noktalarını asenkron olarak sunan HTTP API uç noktaları.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/admin/router.py b/web_api/admin/router.py
index 212e4ee..4481f0e 100644
--- a/web_api/admin/router.py
+++ b/web_api/admin/router.py
@@ -3,9 +3,18 @@ Admin Router
 Admin query approval/rejection endpoints
 """
 from fastapi import APIRouter, Depends, status, HTTPException, Response
-from .schemas import *
+from typing import List
+from .schemas import (
+    AdminApprovalsList, 
+    AdminPreviewResponse, 
+    ApprovalRequest, 
+    DatabaseAddRequest,
+    DatabaseListResponse,
+    DatabaseResponseSchema,
+    MaskingRuleSchema,
+    MaskingRulesSaveRequest
+)
 from dependencies import get_admin_service, admin_required
-from .schemas import ApprovalRequest
 from .services import AdminService
 from app_database.models import User
 
@@ -96,9 +105,84 @@ async def add_database(
     )
     
     if result.get("success"):
-        return {"message": result.get("message")}
+        return {
+            "message": result.get("message"),
+            "db_username": result.get("db_username"),
+            "db_password": result.get("db_password")
+        }
     else:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail=result.get("error", "Failed to add database")
         )
+
+@router.get("/databases", response_model=DatabaseListResponse)
+async def list_databases(
+    current_admin: User = Depends(admin_required),
+    service: AdminService = Depends(get_admin_service)
+):
+    """
+    Lists all registered databases in the system.
+    """
+    dbs = await service.list_databases()
+    return {"databases": [
+        DatabaseResponseSchema(
+            id=db.id,
+            servername=db.servername,
+            database_name=db.database_name,
+            technology=db.technology,
+            db_username=db.db_username
+        )
+        for db in dbs
+    ]}
+
+@router.get("/databases/{database_id}/discover_schema")
+async def discover_schema(
+    database_id: int,
+    current_admin: User = Depends(admin_required),
+    service: AdminService = Depends(get_admin_service)
+):
+    """
+    Inspects and returns the schema (tables and columns) of a database.
+    """
+    schema = await service.discover_schema(database_id, current_admin)
+    return schema
+
+@router.get("/databases/{database_id}/masking_rules", response_model=List[MaskingRuleSchema])
+async def get_masking_rules(
+    database_id: int,
+    current_admin: User = Depends(admin_required),
+    service: AdminService = Depends(get_admin_service)
+):
+    """
+    Gets all masking rules for a database.
+    """
+    rules = await service.get_all_masking_rules(database_id)
+    return [
+        MaskingRuleSchema(
+            table_name=r.table_name,
+            column_name=r.column_name,
+            masking_type=r.masking_type,
+            is_active=r.is_active
+        )
+        for r in rules
+    ]
+
+@router.post("/databases/{database_id}/masking_rules")
+async def save_masking_rules(
+    database_id: int,
+    request: MaskingRulesSaveRequest,
+    current_admin: User = Depends(admin_required),
+    service: AdminService = Depends(get_admin_service)
+):
+    """
+    Saves/updates the masking rules for a database.
+    """
+    success = await service.save_masking_rules(database_id, request.rules)
+    if success:
+        return {"success": True, "message": "Masking rules saved successfully"}
+    else:
+        raise HTTPException(
+            status_code=status.HTTP_400_BAD_REQUEST,
+            detail="Failed to save masking rules"
+        )
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (router.py)</summary>

```python
"""
Admin Router
Admin query approval/rejection endpoints
"""
from fastapi import APIRouter, Depends, status, HTTPException, Response
from typing import List
from .schemas import (
    AdminApprovalsList, 
    AdminPreviewResponse, 
    ApprovalRequest, 
    DatabaseAddRequest,
    DatabaseListResponse,
    DatabaseResponseSchema,
    MaskingRuleSchema,
    MaskingRulesSaveRequest
)
from dependencies import get_admin_service, admin_required
from .services import AdminService
from app_database.models import User

router = APIRouter(prefix="/api/admin")

@router.get("/queries_to_approve", response_model=AdminApprovalsList)
async def get_queries_to_approve(
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Returns the list of queries waiting for approval.
    """
    workspaces = await service.get_workspaces_for_approval()
    return {"waiting_approvals": workspaces}

@router.post("/approve_query/{workspace_id}")
async def approve_query(
    workspace_id: int,
    approval: ApprovalRequest,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Approves and executes the query.
    """
    # call service approve (sets show_results and query status)
    result = await service.approve(workspace_id, approval.show_results)

    if result.get("success"):
        return result
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to approve query")
        )

@router.post("/reject_query/{workspace_id}")
async def reject_query(
    workspace_id: int,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Rejects the query.
    """
    result = await service.reject_query_by_workspace_id(workspace_id)
    
    if result.get("success"):
        return Response(status_code=status.HTTP_200_OK)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to reject query")
        )

@router.post("/execute_for_preview/{workspace_id}", response_model=AdminPreviewResponse)
async def execute_for_preview(
    workspace_id: int,
    current_admin : User = Depends(admin_required),
    service : AdminService = Depends(get_admin_service)
):
    """
    Admin için workspace sorgusunu preview eder (önizleme)

    Admin yetkisi gerektirir. execute_for_preview, query'yi çalıştırır ancak status değiştirmez.
    """
    result = await service.execute_for_preview(workspace_id, current_admin)

    if isinstance(result, dict) and result.get("response_type") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error"))
    
    return result

@router.post("/add_database")
async def add_database(
    request: DatabaseAddRequest,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Adds a new database to the system.
    """
    result = await service.db_addition_service.add_database(
        servername=request.servername,
        database_name=request.database_name,
        tech_name=request.tech_name
    )
    
    if result.get("success"):
        return {
            "message": result.get("message"),
            "db_username": result.get("db_username"),
            "db_password": result.get("db_password")
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to add database")
        )

@router.get("/databases", response_model=DatabaseListResponse)
async def list_databases(
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Lists all registered databases in the system.
    """
    dbs = await service.list_databases()
    return {"databases": [
        DatabaseResponseSchema(
            id=db.id,
            servername=db.servername,
            database_name=db.database_name,
            technology=db.technology,
            db_username=db.db_username
        )
        for db in dbs
    ]}

@router.get("/databases/{database_id}/discover_schema")
async def discover_schema(
    database_id: int,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Inspects and returns the schema (tables and columns) of a database.
    """
    schema = await service.discover_schema(database_id, current_admin)
    return schema

@router.get("/databases/{database_id}/masking_rules", response_model=List[MaskingRuleSchema])
async def get_masking_rules(
    database_id: int,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Gets all masking rules for a database.
    """
    rules = await service.get_all_masking_rules(database_id)
    return [
        MaskingRuleSchema(
            table_name=r.table_name,
            column_name=r.column_name,
            masking_type=r.masking_type,
            is_active=r.is_active
        )
        for r in rules
    ]

@router.post("/databases/{database_id}/masking_rules")
async def save_masking_rules(
    database_id: int,
    request: MaskingRulesSaveRequest,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Saves/updates the masking rules for a database.
    """
    success = await service.save_masking_rules(database_id, request.rules)
    if success:
        return {"success": True, "message": "Masking rules saved successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to save masking rules"
        )

```
</details>



#### <a name="web_apiadminservicespy"></a> `web_api/admin/services.py`
**Açıklama:** Riskli bulunan sorguların admin onayından/reddedilmesinden geçirilmesi akışını yöneten, onaylanan sorguların önizleme işlemlerini ve sisteme yeni hedef veritabanı ekleme süreçlerini asenkron işlemlerle yürüten servis katmanı.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/admin/services.py b/web_api/admin/services.py
index b0440ff..f33752d 100644
--- a/web_api/admin/services.py
+++ b/web_api/admin/services.py
@@ -3,11 +3,20 @@ Admin Service Layer
 Admin approval and management operations for risky queries
 """
 from sqlalchemy.sql import select, text
-from app_database.models import QueryData, Workspace, User, Databases
+from typing import Any
+from app_database.models import QueryData, Workspace, User, Databases, MaskingRule
 from app_database.app_database import AppDatabase
 from database_provider import DatabaseProvider
-from .schemas import *
+from .schemas import AdminApprovals
 from query_execution import config
+
+import logging
+from common.exceptions import BaseServiceException
+from workspaces.exceptions import WorkspaceNotFoundError
+from .exceptions import DatabaseAlreadyExistsError
+
+logger = logging.getLogger(__name__)
+
 class BaseAdminService:
     """
     Base class for all admin services.
@@ -51,6 +60,92 @@ class AdminService(BaseAdminService):
     async def approve(self, workspace_id: int, show_results: bool):
         return await self.approval_service.approve(workspace_id, show_results)
 
+    async def list_databases(self) -> list[Databases]:
+        async with self.app_db.get_app_db() as db:
+            result = await db.execute(select(Databases))
+            return list(result.scalars().all())
+
+    async def discover_schema(self, database_id: int, admin_user: User) -> dict[str, list[str]]:
+        async with self.app_db.get_app_db() as db:
+            db_entry = await db.get(Databases, database_id)
+            if not db_entry:
+                return {}
+            servername = db_entry.servername
+            database_name = db_entry.database_name
+            
+        db_info = await self.app_db.get_db_info()
+        self.db_provider.set_db_info(db_info)
+        
+        from sqlalchemy import inspect
+        try:
+            async with self.db_provider.get_session(admin_user, servername, database_name) as session:
+                def get_schema(connection):
+                    inspector = inspect(connection)
+                    schema = {}
+                    
+                    # Retrieve all schemas in the database
+                    schemas = inspector.get_schema_names()
+                    system_schemas = {
+                        'sys', 'information_schema', 'guest', 'db_owner', 'db_accessadmin',
+                        'db_securityadmin', 'db_ddladmin', 'db_backupoperator',
+                        'db_datareader', 'db_datawriter', 'db_denydatareader', 'db_denydatawriter'
+                    }
+                    
+                    for schema_name in schemas:
+                        # Skip database role and system schemas
+                        if schema_name.lower() in system_schemas or schema_name.lower().startswith('db_'):
+                            continue
+                        
+                        try:
+                            # Retrieve all tables in this schema
+                            tables = inspector.get_table_names(schema=schema_name)
+                            for table_name in tables:
+                                # Format table names as "schema_name.table_name" for clear identification
+                                full_table_name = f"{schema_name}.{table_name}"
+                                schema[full_table_name] = [
+                                    col["name"] for col in inspector.get_columns(table_name, schema=schema_name)
+                                ]
+                        except Exception as e:
+                            logger.warning(f"Failed to inspect schema '{schema_name}' for database {database_id}: {e}")
+                            continue
+                            
+                    return schema
+
+                connection = await session.connection()
+                schema = await connection.run_sync(get_schema)
+                return schema
+        except Exception as e:
+            logger.error(f"Failed to discover schema for database {database_id}: {e}")
+            return {}
+
+    async def get_all_masking_rules(self, database_id: int) -> list[MaskingRule]:
+        async with self.app_db.get_app_db() as db:
+            result = await db.execute(
+                select(MaskingRule).where(MaskingRule.database_id == database_id)
+            )
+            return list(result.scalars().all())
+
+    async def save_masking_rules(self, database_id: int, rules_data: list) -> bool:
+        async with self.app_db.get_app_db() as db:
+            try:
+                from sqlalchemy import delete
+                await db.execute(delete(MaskingRule).where(MaskingRule.database_id == database_id))
+                for rule in rules_data:
+                    new_rule = MaskingRule(
+                        database_id=database_id,
+                        table_name=rule.table_name,
+                        column_name=rule.column_name,
+                        masking_type=rule.masking_type,
+                        is_active=rule.is_active
+                    )
+                    db.add(new_rule)
+                await db.commit()
+                return True
+            except Exception as e:
+                await db.rollback()
+                logger.error(f"Failed to save masking rules for database {database_id}: {e}")
+                return False
+
 class AdminApprovalService(BaseAdminService):
     """
     Sub-service handling admin approval operations.
@@ -130,10 +225,26 @@ class AdminApprovalService(BaseAdminService):
             async with self.db_provider.get_session(user, servername, database_name) as session:
                 sql_query = text(query_text)
                 result = await session.execute(sql_query)
-                rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
-                row_count = len(rows)
-
-                result_data = [dict(row._mapping) for row in rows]
+                
+                row_count: int = 0
+                message: str | None = None
+                result_data: list[dict[str, Any]] = []
+                columns: list[str] = []
+                
+                if result.returns_rows:
+                    rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
+                    row_count = len(rows)
+                    result_data = [dict(row._mapping) for row in rows]
+                    columns = list(result_data[0].keys()) if result_data else []
+                    if row_count >= config.MAX_ROW_COUNT_LIMIT:
+                        message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"
+                    else:
+                        message = f"{row_count} rows returned"
+                else:
+                    row_count = result.rowcount if result.rowcount is not None else 0
+                    message = f"{row_count} rows affected"
+                    result_data = []
+                    columns = []
             
             await self.app_db.update_log(
                 log_id=log_id,
@@ -141,11 +252,6 @@ class AdminApprovalService(BaseAdminService):
                 row_count=row_count
             )
 
-            columns = list(result_data[0].keys()) if result_data else []
-            message = None
-            if row_count > 0 and row_count == config.MAX_ROW_COUNT_LIMIT:
-                message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"
-
             return {
                 "response_type": "data",
                 "data": result_data,
@@ -199,71 +305,76 @@ class AdminApprovalService(BaseAdminService):
                 print(f"Error rejecting query: {e}")
                 return {"success": False, "error": str(e)}
             
-    async def approve(self, workspace_id: int, show_results: bool):
+    async def approve(self, workspace_id: int, show_results: bool) -> dict[str, Any]:
         """
-        Approves the query.
-        """
-        try:
-            async with self.app_db.get_app_db() as db:
-                result = await db.execute(
-                    text("SELECT query_id FROM Workspaces WHERE id = :workspace_id"),
-                    {"workspace_id": workspace_id}
-                )
-                row = result.first()
-                if not row:
-                    return {"success": False, "error": "Workspace not found"}
-                query_id = row[0]
-            
-            async with self.app_db.get_app_db() as db:
-                result = await db.execute(
-                    text("SELECT id FROM QueryData WHERE id = :query_id"),
-                    {"query_id": query_id}
-                )
-                if not result.first():
-                    return {"success": False, "error": "Query data not found"}
-            
-            if show_results:
-                new_status = "approved_with_results"
-                new_desc = "Approved by admin - User can execute"
-                show_results_val = 1
-            else:
-                new_status = "approved"
-                new_desc = "Approved by admin - User cannot execute"
-                show_results_val = 0
+        Approves a query, enabling execution for the user.
+        
+        Args:
+            workspace_id: The ID of the workspace containing the query.
+            show_results: If True, the user can see execution results; otherwise, they cannot.
             
-            async with self.app_db.get_app_db() as db:
-                result1 = await db.execute(
-                    text("UPDATE QueryData SET status = :status WHERE id = :id"),
-                    {"status": new_status, "id": query_id}
-                )
+        Returns:
+            dict[str, any]: A dictionary indicating success and the new query status.
+        """
+        async with self.app_db.get_app_db() as db:
+            try:
+                # 1. Fetch workspace by ID
+                workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
+                workspace: Workspace | None = workspace_result.scalars().first()
+                if not workspace:
+                    raise WorkspaceNotFoundError("Workspace not found")
                 
-                result2 = await db.execute(
-                    text("UPDATE Workspaces SET show_results = :show, description = :desc WHERE id = :id"),
-                    {"show": show_results_val, "desc": new_desc, "id": workspace_id}
-                )
+                # 2. Fetch related QueryData
+                query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
+                query_data: QueryData | None = query_result.scalars().first()
+                if not query_data:
+                    raise WorkspaceNotFoundError("Query data not found for this workspace")
+                
+                # 3. Update status and description
+                new_status: str = ""
+                new_desc: str = ""
+                if show_results:
+                    new_status = "approved_with_results"
+                    new_desc = "Approved by admin - User can execute"
+                    workspace.show_results = True
+                else:
+                    new_status = "approved"
+                    new_desc = "Approved by admin - User cannot execute"
+                    workspace.show_results = False
+                
+                query_data.status = new_status
+                workspace.description = new_desc
                 
                 await db.commit()
-            
-            return {
-                "success": True,
-                "status": new_status,
-                "message": f"Query approved successfully ({'executable' if show_results else 'not executable'})"
-            }
-        
-        except Exception as e:
-            print(f"Approval failed: {e}")
-            return {
-                "success": False,
-                "error": f"Approval failed: {str(e)}"
-            }
+                
+                logger.info(f"Query in workspace {workspace_id} approved by admin (Executable: {show_results})")
+                return {
+                    "success": True,
+                    "status": new_status,
+                    "message": f"Query approved successfully ({'executable' if show_results else 'not executable'})"
+                }
+            except BaseServiceException:
+                raise
+            except Exception as e:
+                await db.rollback()
+                logger.error(f"Approval failed for workspace {workspace_id}: {e}")
+                raise BaseServiceException(f"Approval failed: {str(e)}", original_exception=e)
 
 class AdminDBAdditionService(BaseAdminService):
     """
-    Service for adding new databases.
+    Service for adding new databases to the platform configuration.
     """
-    async def add_database(self, servername: str, database_name: str, tech_name: str):
+    async def add_database(self, servername: str, database_name: str, tech_name: str) -> dict[str, Any]:
         """
-        Adds a new database.
+        Adds a new database server and database configuration to the application databases.
+        
+        Args:
+            servername: The host/instance name of the SQL server.
+            database_name: The name of the database.
+            tech_name: The database technology/type (e.g., mssql, postgresql, mysql).
+            
+        Returns:
+            dict[str, any]: A dictionary containing execution status and a message or error.
         """
         async with self.app_db.get_app_db() as db:
             try:
@@ -272,14 +383,37 @@ class AdminDBAdditionService(BaseAdminService):
                     Databases.servername == servername, 
                     Databases.database_name == database_name
                 ))
-                if existing.scalars().first():
-                    return {"success": False, "error": "Database already exists"}
+                existing_db: Databases | None = existing.scalars().first()
+                if existing_db:
+                    raise DatabaseAlreadyExistsError("Database already exists")
+
+                from common.security import generate_secure_credentials
+                db_username, db_password = generate_secure_credentials()
 
-                database = Databases(servername=servername, database_name=database_name, tech_name=tech_name)
+                database: Databases = Databases(
+                    servername=servername, 
+                    database_name=database_name, 
+                    technology=tech_name,
+                    db_username=db_username,
+                    db_password=db_password
+                )
                 db.add(database)
                 await db.commit()
-                return {"success": True, "message": "Database added successfully"}
+                
+                # Refresh db_provider db_info dynamically
+                db_info = await self.app_db.get_db_info()
+                self.db_provider.set_db_info(db_info)
+                
+                logger.info(f"Database '{database_name}' on server '{servername}' successfully added by admin with generated credentials")
+                return {
+                    "success": True, 
+                    "message": "Database added successfully",
+                    "db_username": db_username,
+                    "db_password": db_password
+                }
+            except BaseServiceException:
+                raise
             except Exception as e:
                 await db.rollback()
-                print(f"Error adding database: {e}")
-                return {"success": False, "error": str(e)}
+                logger.error(f"Error adding database: {e}")
+                raise BaseServiceException(f"Error adding database: {str(e)}", original_exception=e)
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (services.py)</summary>

```python
"""
Admin Service Layer
Admin approval and management operations for risky queries
"""
from sqlalchemy.sql import select, text
from typing import Any
from app_database.models import QueryData, Workspace, User, Databases, MaskingRule
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from .schemas import AdminApprovals
from query_execution import config

import logging
from common.exceptions import BaseServiceException
from workspaces.exceptions import WorkspaceNotFoundError
from .exceptions import DatabaseAlreadyExistsError

logger = logging.getLogger(__name__)

class BaseAdminService:
    """
    Base class for all admin services.
    Manages database connections for subclasses.
    """
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        self.app_db = app_db
        self.db_provider = db_provider

class AdminService(BaseAdminService):
    """
    Main Admin Service.
    
    Combines sub-services (Approval, DB Addition) to provide a unified interface.
    """
    
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        # Establish connections by calling the Base class's __init__
        super().__init__(app_db, db_provider)
        
        # Initialize sub-services
        self.approval_service = AdminApprovalService(app_db, db_provider)
        self.db_addition_service = AdminDBAdditionService(app_db, db_provider)
        
        # Other services to be added in the future can go here
        # self.report_service = AdminReportService(app_db, db_provider)

    # --- Approval Service Delegations ---
    # We define the methods used in the router as wrappers here
    # So we don't have to change the router code.

    async def get_workspaces_for_approval(self):
        return await self.approval_service.get_workspaces_for_approval()

    async def execute_for_preview(self, workspace_id: int, admin_user: User):
        return await self.approval_service.execute_for_preview(workspace_id, admin_user)

    async def reject_query_by_workspace_id(self, workspace_id: int):
        return await self.approval_service.reject_query_by_workspace_id(workspace_id)
            
    async def approve(self, workspace_id: int, show_results: bool):
        return await self.approval_service.approve(workspace_id, show_results)

    async def list_databases(self) -> list[Databases]:
        async with self.app_db.get_app_db() as db:
            result = await db.execute(select(Databases))
            return list(result.scalars().all())

    async def discover_schema(self, database_id: int, admin_user: User) -> dict[str, list[str]]:
        async with self.app_db.get_app_db() as db:
            db_entry = await db.get(Databases, database_id)
            if not db_entry:
                return {}
            servername = db_entry.servername
            database_name = db_entry.database_name
            
        db_info = await self.app_db.get_db_info()
        self.db_provider.set_db_info(db_info)
        
        from sqlalchemy import inspect
        try:
            async with self.db_provider.get_session(admin_user, servername, database_name) as session:
                def get_schema(connection):
                    inspector = inspect(connection)
                    schema = {}
                    
                    # Retrieve all schemas in the database
                    schemas = inspector.get_schema_names()
                    system_schemas = {
                        'sys', 'information_schema', 'guest', 'db_owner', 'db_accessadmin',
                        'db_securityadmin', 'db_ddladmin', 'db_backupoperator',
                        'db_datareader', 'db_datawriter', 'db_denydatareader', 'db_denydatawriter'
                    }
                    
                    for schema_name in schemas:
                        # Skip database role and system schemas
                        if schema_name.lower() in system_schemas or schema_name.lower().startswith('db_'):
                            continue
                        
                        try:
                            # Retrieve all tables in this schema
                            tables = inspector.get_table_names(schema=schema_name)
                            for table_name in tables:
                                # Format table names as "schema_name.table_name" for clear identification
                                full_table_name = f"{schema_name}.{table_name}"
                                schema[full_table_name] = [
                                    col["name"] for col in inspector.get_columns(table_name, schema=schema_name)
                                ]
                        except Exception as e:
                            logger.warning(f"Failed to inspect schema '{schema_name}' for database {database_id}: {e}")
                            continue
                            
                    return schema

                connection = await session.connection()
                schema = await connection.run_sync(get_schema)
                return schema
        except Exception as e:
            logger.error(f"Failed to discover schema for database {database_id}: {e}")
            return {}

    async def get_all_masking_rules(self, database_id: int) -> list[MaskingRule]:
        async with self.app_db.get_app_db() as db:
            result = await db.execute(
                select(MaskingRule).where(MaskingRule.database_id == database_id)
            )
            return list(result.scalars().all())

    async def save_masking_rules(self, database_id: int, rules_data: list) -> bool:
        async with self.app_db.get_app_db() as db:
            try:
                from sqlalchemy import delete
                await db.execute(delete(MaskingRule).where(MaskingRule.database_id == database_id))
                for rule in rules_data:
                    new_rule = MaskingRule(
                        database_id=database_id,
                        table_name=rule.table_name,
                        column_name=rule.column_name,
                        masking_type=rule.masking_type,
                        is_active=rule.is_active
                    )
                    db.add(new_rule)
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to save masking rules for database {database_id}: {e}")
                return False

class AdminApprovalService(BaseAdminService):
    """
    Sub-service handling admin approval operations.
    """

    async def get_workspaces_for_approval(self):
        """
        Retrieves workspaces waiting for admin approval.
        """
        result_list = []
        try:
            async with self.app_db.get_app_db() as db:
                results = await db.execute(select(QueryData).where(QueryData.status == "waiting_for_approval"))
                queries = results.scalars().all()
                if queries:
                    for query in queries:
                       
                        workspace_result = await db.execute(
                            select(Workspace).where(Workspace.query_id == query.id)
                        )
                        workspace = workspace_result.scalars().first()

                        user_result = await db.execute(select(User).where(User.id == query.user_id))
                        user = user_result.scalars().first()
                        
                        if workspace and user:
                            data = AdminApprovals(
                                user_id=query.user_id,
                                workspace_id=workspace.id,
                                username = user.username,
                                query= query.query,
                                database=query.database_name,
                                status= query.status,
                                risk_type=query.risk_type,
                                servername=query.servername
                            )

                            result_list.append(data)
            return result_list
        except  Exception as e:
            print(f"Error: {str(e)}")
            return []
        
    async def execute_for_preview(self, workspace_id: int, admin_user: User):
        """
        Executes and previews the query for the admin.
        """
        log_id = None
        
        async with self.app_db.get_app_db() as db:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                return {"success": False, "error": "Workspace not found"}
                    
            query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
            query_data = query_result.scalars().first()
            if not query_data:
                return {"success": False, "error": "Query data not found"}
                    
            user_result = await db.execute(select(User).where(User.id == admin_user.id))
            user = user_result.scalars().first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            query_text = query_data.query
            servername = query_data.servername
            database_name = query_data.database_name
        
        try:
            log_id = await self.app_db.create_log(
                user=admin_user, 
                query=query_text, 
                machine_name=servername
            )
            
            async with self.db_provider.get_session(user, servername, database_name) as session:
                sql_query = text(query_text)
                result = await session.execute(sql_query)
                
                row_count: int = 0
                message: str | None = None
                result_data: list[dict[str, Any]] = []
                columns: list[str] = []
                
                if result.returns_rows:
                    rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
                    row_count = len(rows)
                    result_data = [dict(row._mapping) for row in rows]
                    columns = list(result_data[0].keys()) if result_data else []
                    if row_count >= config.MAX_ROW_COUNT_LIMIT:
                        message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"
                    else:
                        message = f"{row_count} rows returned"
                else:
                    row_count = result.rowcount if result.rowcount is not None else 0
                    message = f"{row_count} rows affected"
                    result_data = []
                    columns = []
            
            await self.app_db.update_log(
                log_id=log_id,
                successfull=True,
                row_count=row_count
            )

            return {
                "response_type": "data",
                "data": result_data,
                "columns": columns,
                "row_count": row_count,
                "message": message,
                "error": None
            }
        except Exception as e:
            if log_id:
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=False,
                    error=str(e)
                )

            print(f"Query preview failed: {e}")
            return {
                "response_type": "error",
                "data": [],
                "columns": [],
                "row_count": 0,
                "message": None,
                "error": str(e)
            }

    async def reject_query_by_workspace_id(self, workspace_id: int):
        """
        Rejects the query.
        """
        async with self.app_db.get_app_db() as db:
            try:
                workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
                workspace = workspace_result.scalars().first()
                if not workspace:
                    return {"success": False, "error": "Workspace not found"}
                    
                query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
                query_data = query_result.scalars().first()
                if not query_data:
                    return {"success": False, "error": "Query data not found"}
                
                query_data.status = "rejected"
                workspace.description = "Rejected by admin"
                
                await db.commit()
                return {"success": True}
                
            except Exception as e:
                await db.rollback()
                print(f"Error rejecting query: {e}")
                return {"success": False, "error": str(e)}
            
    async def approve(self, workspace_id: int, show_results: bool) -> dict[str, Any]:
        """
        Approves a query, enabling execution for the user.
        
        Args:
            workspace_id: The ID of the workspace containing the query.
            show_results: If True, the user can see execution results; otherwise, they cannot.
            
        Returns:
            dict[str, any]: A dictionary indicating success and the new query status.
        """
        async with self.app_db.get_app_db() as db:
            try:
                # 1. Fetch workspace by ID
                workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
                workspace: Workspace | None = workspace_result.scalars().first()
                if not workspace:
                    raise WorkspaceNotFoundError("Workspace not found")
                
                # 2. Fetch related QueryData
                query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
                query_data: QueryData | None = query_result.scalars().first()
                if not query_data:
                    raise WorkspaceNotFoundError("Query data not found for this workspace")
                
                # 3. Update status and description
                new_status: str = ""
                new_desc: str = ""
                if show_results:
                    new_status = "approved_with_results"
                    new_desc = "Approved by admin - User can execute"
                    workspace.show_results = True
                else:
                    new_status = "approved"
                    new_desc = "Approved by admin - User cannot execute"
                    workspace.show_results = False
                
                query_data.status = new_status
                workspace.description = new_desc
                
                await db.commit()
                
                logger.info(f"Query in workspace {workspace_id} approved by admin (Executable: {show_results})")
                return {
                    "success": True,
                    "status": new_status,
                    "message": f"Query approved successfully ({'executable' if show_results else 'not executable'})"
                }
            except BaseServiceException:
                raise
            except Exception as e:
                await db.rollback()
                logger.error(f"Approval failed for workspace {workspace_id}: {e}")
                raise BaseServiceException(f"Approval failed: {str(e)}", original_exception=e)

class AdminDBAdditionService(BaseAdminService):
    """
    Service for adding new databases to the platform configuration.
    """
    async def add_database(self, servername: str, database_name: str, tech_name: str) -> dict[str, Any]:
        """
        Adds a new database server and database configuration to the application databases.
        
        Args:
            servername: The host/instance name of the SQL server.
            database_name: The name of the database.
            tech_name: The database technology/type (e.g., mssql, postgresql, mysql).
            
        Returns:
            dict[str, any]: A dictionary containing execution status and a message or error.
        """
        async with self.app_db.get_app_db() as db:
            try:
                # Check if it already exists
                existing = await db.execute(select(Databases).where(
                    Databases.servername == servername, 
                    Databases.database_name == database_name
                ))
                existing_db: Databases | None = existing.scalars().first()
                if existing_db:
                    raise DatabaseAlreadyExistsError("Database already exists")

                from common.security import generate_secure_credentials
                db_username, db_password = generate_secure_credentials()

                database: Databases = Databases(
                    servername=servername, 
                    database_name=database_name, 
                    technology=tech_name,
                    db_username=db_username,
                    db_password=db_password
                )
                db.add(database)
                await db.commit()
                
                # Refresh db_provider db_info dynamically
                db_info = await self.app_db.get_db_info()
                self.db_provider.set_db_info(db_info)
                
                logger.info(f"Database '{database_name}' on server '{servername}' successfully added by admin with generated credentials")
                return {
                    "success": True, 
                    "message": "Database added successfully",
                    "db_username": db_username,
                    "db_password": db_password
                }
            except BaseServiceException:
                raise
            except Exception as e:
                await db.rollback()
                logger.error(f"Error adding database: {e}")
                raise BaseServiceException(f"Error adding database: {str(e)}", original_exception=e)

```
</details>



#### <a name="web_apiadminschemaspy"></a> `web_api/admin/schemas.py`
**Açıklama:** Admin onay ve veritabanı ekleme işlemleri için doğrulama kurallarını içeren Pydantic şemaları.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/admin/schemas.py b/web_api/admin/schemas.py
index cc6e358..f7b748a 100644
--- a/web_api/admin/schemas.py
+++ b/web_api/admin/schemas.py
@@ -75,3 +75,26 @@ class DatabaseAddRequest(BaseModel):
     servername: str
     database_name: str
     tech_name: str
+
+
+class MaskingRuleSchema(BaseModel):
+    table_name: str
+    column_name: str
+    masking_type: str = "default"
+    is_active: bool = True
+
+
+class MaskingRulesSaveRequest(BaseModel):
+    rules: List[MaskingRuleSchema]
+
+
+class DatabaseResponseSchema(BaseModel):
+    id: int
+    servername: str
+    database_name: str
+    technology: str
+    db_username: Optional[str] = None
+
+
+class DatabaseListResponse(BaseModel):
+    databases: List[DatabaseResponseSchema]
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (schemas.py)</summary>

```python
"""
Admin Schemas
Pydantic models for admin approval endpoints
"""
from pydantic import BaseModel
from typing import Optional, List
from typing import Dict, Any

class AdminApprovals(BaseModel):
    """
    Query information waiting for admin approval
    
    Attributes:
        user_id: ID of the user sending the query
        workspace_id: Related workspace ID
        username: Username
        query: SQL query waiting for approval
        database: Target database
        status: Query status ("waiting_for_approval", etc.)
        risk_type: Risk type (optional, from analyzer)
        servername: Target SQL Server (optional)
    """
    user_id: int
    workspace_id: int
    username: str
    query: str
    database: str
    status: str
    risk_type: Optional[str] = None
    servername: Optional[str] = None

class AdminApprovalsList(BaseModel):
    """Admin approval list response schema"""
    waiting_approvals: List[AdminApprovals]


class AdminPreviewResponse(BaseModel):
    """
    Preview result by admin

    Attributes:
        response_type: "data" or "error"
        data: List of rows (each row is a dict)
        columns: Optional, list of column names
        row_count: Returned row count
        message: Optional message (e.g. "truncated to MAX_ROW_COUNT")
        error: Error message (if any)
    """
    response_type: str  # "data" or "error"
    data: List[Dict[str, Any]]
    columns: Optional[List[str]] = None
    row_count: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None


class ApprovalRequest(BaseModel):
    """
    Admin approval request schema.

    Attributes:
        show_results: bool - if true, workspace becomes executable
    """
    show_results: bool

class DatabaseAddRequest(BaseModel):
    """
    Schema for adding a new database.
    
    Attributes:
        servername: Server instance name
        database_name: Database name
        tech_name: Technology name (e.g., mssql)
    """
    servername: str
    database_name: str
    tech_name: str


class MaskingRuleSchema(BaseModel):
    table_name: str
    column_name: str
    masking_type: str = "default"
    is_active: bool = True


class MaskingRulesSaveRequest(BaseModel):
    rules: List[MaskingRuleSchema]


class DatabaseResponseSchema(BaseModel):
    id: int
    servername: str
    database_name: str
    technology: str
    db_username: Optional[str] = None


class DatabaseListResponse(BaseModel):
    databases: List[DatabaseResponseSchema]

```
</details>



#### <a name="web_apiadmin__init__py"></a> `web_api/admin/__init__.py`
**Açıklama:** Admin paketi başlatma dosyası.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/admin/__init__.py b/web_api/admin/__init__.py
index 3e19d92..cce9d93 100644
--- a/web_api/admin/__init__.py
+++ b/web_api/admin/__init__.py
@@ -1,4 +1,7 @@
 """
 Admin Module
-Riskli query'lerin admin onayı ve yönetimi
+Handles query approvals and database registrations by administrators.
 """
+from .exceptions import DatabaseAlreadyExistsError
+
+__all__ = ["DatabaseAlreadyExistsError"]
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (__init__.py)</summary>

```python
"""
Admin Module
Handles query approvals and database registrations by administrators.
"""
from .exceptions import DatabaseAlreadyExistsError

__all__ = ["DatabaseAlreadyExistsError"]

```
</details>




### 📂 Kategori 7: Ön Yüz (React/TypeScript Frontend) Ekranları
---

#### <a name="frontendpageslogintsx"></a> `frontend/pages/Login.tsx`
**Açıklama:** Kullanıcı giriş ekranını, yeni cookie tabanlı stateless auth yapısına uygun olarak credentials çerezlerini HttpOnly olarak alacak ve hata durumlarında Trace ID gösterecek şekilde güncellenen sayfa.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/frontend/pages/Login.tsx b/frontend/pages/Login.tsx
index 3888257..06e4152 100644
--- a/frontend/pages/Login.tsx
+++ b/frontend/pages/Login.tsx
@@ -24,7 +24,7 @@ const Login: React.FC = () => {
         navigate('/');
       } else {
         const data = await response?.json();
-        setError(data?.error || "Connection refused. Ensure the backend is running.");
+        setError(data?.detail || data?.error || "Connection refused. Ensure the backend is running.");
       }
     } catch (err) {
       setError("Network error occurred while attempting to establish connection.");
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (Login.tsx)</summary>

```tsx

import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authenticatedFetch } from '../services/api';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const response = await authenticatedFetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      if (response && response.ok) {
        navigate('/');
      } else {
        const data = await response?.json();
        setError(data?.detail || data?.error || "Connection refused. Ensure the backend is running.");
      }
    } catch (err) {
      setError("Network error occurred while attempting to establish connection.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 p-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-full opacity-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-indigo-600 rounded-full blur-[120px]"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-emerald-600 rounded-full blur-[120px]"></div>
      </div>

      <div className="w-full max-w-md bg-gray-900/50 backdrop-blur-xl rounded-3xl shadow-2xl p-10 border border-gray-800 relative z-10">
        <div className="flex flex-col items-center mb-8">
          <h2 className="text-4xl font-black text-white tracking-tighter uppercase">WebQuery</h2>
          <p className="text-gray-500 text-[10px] font-bold mt-1 tracking-[0.3em] uppercase">Data Infrastructure</p>
        </div>
        
        {error && (
          <div className="mb-4 p-3 bg-red-900/20 border border-red-900/50 text-red-400 text-[10px] font-bold uppercase rounded-lg text-center tracking-widest">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Identity (Email)</label>
            <input 
              type="email" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@webquery.io"
              required
            />
          </div>
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Secure Code (Password)</label>
            <input 
              type="password" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>
          
          <div className="pt-4 flex flex-col gap-4">
            <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-black py-4 px-4 rounded-xl transition-all shadow-xl shadow-indigo-600/20 active:scale-95 uppercase tracking-widest text-xs">
              Establish Connection
            </button>
            
            <div className="flex flex-col gap-2 items-center">
              <Link to="/register" className="text-[10px] text-gray-400 hover:text-indigo-400 font-black uppercase tracking-widest transition-colors">
                Create New Identity
              </Link>
              <div className="text-center text-[9px] text-gray-700 font-bold uppercase tracking-tighter mt-2">
                Authorized personnel only beyond this point.
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;

```
</details>



#### <a name="frontendpagesregistertsx"></a> `frontend/pages/Register.tsx`
**Açıklama:** Kullanıcı kayıt ekranını, yeni merkezi hata formatını yakalayacak ve hata durumlarında detaylı enterprise hata kodlarını ve Trace ID'yi kullanıcıya sunacak şekilde güncelleyen sayfa.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/frontend/pages/Register.tsx b/frontend/pages/Register.tsx
index 4087fff..d792e57 100644
--- a/frontend/pages/Register.tsx
+++ b/frontend/pages/Register.tsx
@@ -26,7 +26,7 @@ const Register: React.FC = () => {
         setTimeout(() => navigate('/login'), 2000);
       } else {
         const data = await response?.json();
-        setMessage({ type: 'error', text: data?.error || 'Registration failed.' });
+        setMessage({ type: 'error', text: data?.detail || data?.error || 'Registration failed.' });
       }
     } catch (err) {
       setMessage({ type: 'error', text: 'A network error occurred.' });
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (Register.tsx)</summary>

```tsx

import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authenticatedFetch } from '../services/api';

const Register: React.FC = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);

    try {
      const response = await authenticatedFetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password })
      });

      if (response && response.ok) {
        setMessage({ type: 'success', text: 'Registration successful! Redirecting...' });
        setTimeout(() => navigate('/login'), 2000);
      } else {
        const data = await response?.json();
        setMessage({ type: 'error', text: data?.detail || data?.error || 'Registration failed.' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'A network error occurred.' });
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 p-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-full opacity-10 pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-600 rounded-full blur-[120px]"></div>
        <div className="absolute bottom-[-10%] left-[-10%] w-[40%] h-[40%] bg-emerald-600 rounded-full blur-[120px]"></div>
      </div>

      <div className="w-full max-w-md bg-gray-900/50 backdrop-blur-xl rounded-3xl shadow-2xl p-10 border border-gray-800 relative z-10">
        <div className="flex flex-col items-center mb-8">
          <h2 className="text-4xl font-black text-white tracking-tighter uppercase">Register</h2>
          <p className="text-gray-500 text-[10px] font-bold mt-1 tracking-[0.3em] uppercase">Initialize Profile</p>
        </div>
        
        {message && (
          <div className={`mb-4 p-3 border rounded text-[10px] font-bold uppercase text-center tracking-widest ${message.type === 'success' ? 'bg-green-900/20 border-green-700/50 text-green-400' : 'bg-red-900/20 border-red-900/50 text-red-400'}`}>
            {message.text}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Username</label>
            <input 
              type="text" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium" 
              value={username} 
              onChange={(e) => setUsername(e.target.value)} 
              placeholder="operator_01"
              required 
            />
          </div>
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Email</label>
            <input 
              type="email" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium" 
              value={email} 
              onChange={(e) => setEmail(e.target.value)} 
              placeholder="email@webquery.io"
              required 
            />
          </div>
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Password</label>
            <input 
              type="password" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              placeholder="••••••••"
              required 
            />
          </div>
          
          <div className="pt-4 flex flex-col gap-3">
            <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-black py-4 px-4 rounded-xl transition-all shadow-xl shadow-indigo-600/20 active:scale-95 uppercase tracking-widest text-xs">
              Create Account
            </button>
            <Link to="/login" className="w-full bg-gray-800/50 hover:bg-gray-800 text-gray-400 hover:text-white font-black py-4 px-4 rounded-xl transition-all border border-gray-800 text-center uppercase tracking-widest text-xs">
              Back to Connection
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Register;

```
</details>



#### <a name="frontendpagessqleditortsx"></a> `frontend/pages/SqlEditor.tsx`
**Açıklama:** Sorgu editörünü, hedef sunucu ve veritabanı seçim parametreleriyle (`servername`, `database_name`) sorguları yürütecek, hata durumunda Trace ID göstererek hata bildirmeyi kolaylaştıracak şekilde güncelleyen sayfa.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/frontend/pages/SqlEditor.tsx b/frontend/pages/SqlEditor.tsx
index c0b2c42..326a9ba 100644
--- a/frontend/pages/SqlEditor.tsx
+++ b/frontend/pages/SqlEditor.tsx
@@ -21,6 +21,12 @@ const SqlEditor: React.FC = () => {
   const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
   const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(null);
 
+  // --- Ad-hoc Masking State ---
+  const [persistentMaskedCols, setPersistentMaskedCols] = useState<string[]>([]);
+  const [adHocMaskCols, setAdHocMaskCols] = useState<string[]>([]);
+  const [newAdHocCol, setNewAdHocCol] = useState('');
+  const [showMaskingModal, setShowMaskingModal] = useState(false);
+
   const [showSaveModal, setShowSaveModal] = useState(false);
   const [saveName, setSaveName] = useState('');
   const [saveDesc, setSaveDesc] = useState('');
@@ -37,6 +43,28 @@ const SqlEditor: React.FC = () => {
     }
   }, [workspaceId]);
 
+  // Fetch persistently masked columns for the active server/database
+  useEffect(() => {
+    if (selectedServer && selectedDatabase) {
+      fetchPersistentMaskingRules();
+    } else {
+      setPersistentMaskedCols([]);
+    }
+    setAdHocMaskCols([]); // Clear ad-hoc columns when changing server or database
+  }, [selectedServer, selectedDatabase]);
+
+  const fetchPersistentMaskingRules = async () => {
+    try {
+      const res = await authenticatedFetch(`/api/masking_rules?servername=${selectedServer}&database_name=${selectedDatabase}`);
+      if (res?.ok) {
+        const data = await res.json();
+        setPersistentMaskedCols(data || []);
+      }
+    } catch (e) {
+      console.error("Failed to fetch persistent masking rules:", e);
+    }
+  };
+
   useEffect(() => {
     if (selectedServer && servers[selectedServer]) {
       const dbs = servers[selectedServer].databases;
@@ -104,7 +132,12 @@ const SqlEditor: React.FC = () => {
       const res = await authenticatedFetch('/api/execute_query', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
-        body: JSON.stringify({ query, servername: selectedServer, database_name: selectedDatabase })
+        body: JSON.stringify({ 
+          query, 
+          servername: selectedServer, 
+          database_name: selectedDatabase,
+          ad_hoc_mask_columns: adHocMaskCols
+        })
       });
       if (res) {
         const data = await res.json();
@@ -281,6 +314,22 @@ const SqlEditor: React.FC = () => {
           >
             {loading ? '...' : (currentWorkspace ? 'UPDATE' : 'SAVE')}
           </button>
+          <button
+            onClick={() => setShowMaskingModal(true)}
+            disabled={!selectedServer || !selectedDatabase || loading}
+            className="bg-amber-600/10 hover:bg-amber-600 text-amber-400 hover:text-white px-4 py-2 rounded-lg border border-amber-600/30 transition shadow-lg text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"
+            title="Maskeleme Ayarları"
+          >
+            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
+            </svg>
+            MASKELEME
+            {(persistentMaskedCols.length > 0 || adHocMaskCols.length > 0) && (
+              <span className="bg-amber-500 text-gray-950 text-[10px] font-extrabold px-1.5 py-0.2 rounded-full leading-none">
+                {persistentMaskedCols.length + adHocMaskCols.length}
+              </span>
+            )}
+          </button>
           <button onClick={executeQuery} disabled={loading} className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-2 rounded-lg text-sm font-black shadow-xl transition-all flex items-center gap-2 tracking-widest active:scale-95 disabled:opacity-50">
             {loading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> : 'RUN'}
           </button>
@@ -393,6 +442,107 @@ const SqlEditor: React.FC = () => {
           </button>
         </div>
       </Modal>
+
+      <Modal isOpen={showMaskingModal} onClose={() => setShowMaskingModal(false)} title="Veri Maskeleme Ayarları">
+        <div className="space-y-4">
+          <div className="text-xs text-gray-400 leading-relaxed">
+            Bu sorgu çalıştırılırken maskelenecek kolonları yönetin. Admin tarafından tanımlanmış kalıcı kurallar otomatik olarak uygulanır ve devre dışı bırakılamaz. Ek olarak geçici ad-hoc kurallar tanımlayabilirsiniz.
+          </div>
+
+          {/* Persistent Admin Masking Rules (Read-only) */}
+          <div>
+            <label className="block text-[10px] text-gray-500 font-black uppercase mb-2 tracking-wider">Yönetici Maskeleme Kuralları (Kalıcı)</label>
+            {persistentMaskedCols.length === 0 ? (
+              <div className="bg-gray-950 border border-gray-850 p-3 rounded-lg text-xs text-gray-500 italic">
+                Bu veritabanı için yönetici tarafından tanımlanmış kalıcı maskeleme kuralı bulunmuyor.
+              </div>
+            ) : (
+              <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
+                {persistentMaskedCols.map(col => (
+                  <div key={col} className="flex items-center justify-between bg-gray-950 border border-gray-850/60 px-3 py-2 rounded-lg text-xs">
+                    <span className="font-mono text-gray-300">{col}</span>
+                    <span className="text-[9px] font-bold uppercase bg-red-950/45 text-red-400 border border-red-900/30 px-2 py-0.5 rounded-full select-none">
+                      Kalıcı Maskeli
+                    </span>
+                  </div>
+                ))}
+              </div>
+            )}
+          </div>
+
+          {/* User Ad-Hoc Masking Rules */}
+          <div>
+            <label className="block text-[10px] text-gray-500 font-black uppercase mb-2 tracking-wider">Geçici Maskeleme Kuralları (Ad-Hoc)</label>
+            
+            {/* Input field to add custom columns */}
+            <div className="flex gap-2 mb-3">
+              <input
+                type="text"
+                value={newAdHocCol}
+                onChange={e => setNewAdHocCol(e.target.value)}
+                placeholder="örn. email, salary, phone_number"
+                className="flex-1 bg-gray-950 border border-gray-850 focus:border-indigo-500 rounded-lg px-3 py-2 text-white outline-none text-xs font-mono"
+                onKeyDown={e => {
+                  if (e.key === 'Enter') {
+                    e.preventDefault();
+                    if (newAdHocCol.trim()) {
+                      const trimmed = newAdHocCol.trim().toLowerCase();
+                      if (!persistentMaskedCols.includes(trimmed) && !adHocMaskCols.includes(trimmed)) {
+                        setAdHocMaskCols([...adHocMaskCols, trimmed]);
+                      }
+                      setNewAdHocCol('');
+                    }
+                  }
+                }}
+              />
+              <button
+                type="button"
+                onClick={() => {
+                  if (newAdHocCol.trim()) {
+                    const trimmed = newAdHocCol.trim().toLowerCase();
+                    if (!persistentMaskedCols.includes(trimmed) && !adHocMaskCols.includes(trimmed)) {
+                      setAdHocMaskCols([...adHocMaskCols, trimmed]);
+                    }
+                    setNewAdHocCol('');
+                  }
+                }}
+                className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 rounded-lg text-xs font-bold transition"
+              >
+                Ekle
+              </button>
+            </div>
+
+            {adHocMaskCols.length === 0 ? (
+              <div className="bg-gray-950 border border-gray-850 p-3 rounded-lg text-xs text-gray-500 italic">
+                Sadece bu işlem için geçerli olmak üzere ek maskelenecek kolon adı girin.
+              </div>
+            ) : (
+              <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
+                {adHocMaskCols.map(col => (
+                  <div key={col} className="flex items-center justify-between bg-gray-950 border border-gray-850/60 px-3 py-2 rounded-lg text-xs">
+                    <span className="font-mono text-indigo-300">{col}</span>
+                    <button
+                      type="button"
+                      onClick={() => setAdHocMaskCols(adHocMaskCols.filter(c => c !== col))}
+                      className="text-gray-500 hover:text-red-400 transition-all font-bold text-xs"
+                      title="Kuralı kaldır"
+                    >
+                      Kaldır
+                    </button>
+                  </div>
+                ))}
+              </div>
+            )}
+          </div>
+
+          <button
+            onClick={() => setShowMaskingModal(false)}
+            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white p-2.5 rounded-lg font-bold text-xs transition tracking-widest uppercase mt-2 shadow-lg"
+          >
+            Tamam
+          </button>
+        </div>
+      </Modal>
     </div>
   );
 };
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (SqlEditor.tsx)</summary>

```tsx

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AceEditor from '../components/AceEditor';
import Modal from '../components/Modal';
import { authenticatedFetch } from '../services/api';
import { DatabaseInfo, Workspace, QueryResult } from '../types';
import * as XLSX from 'xlsx';

const SqlEditor: React.FC = () => {
  const { workspaceId } = useParams();
  const navigate = useNavigate();

  const [query, setQuery] = useState('-- WebQuery SQL Studio\nSELECT * FROM table_name LIMIT 10;');
  const [servers, setServers] = useState<DatabaseInfo>({});
  const [selectedServer, setSelectedServer] = useState('');
  const [selectedDatabase, setSelectedDatabase] = useState('');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(null);

  // --- Ad-hoc Masking State ---
  const [persistentMaskedCols, setPersistentMaskedCols] = useState<string[]>([]);
  const [adHocMaskCols, setAdHocMaskCols] = useState<string[]>([]);
  const [newAdHocCol, setNewAdHocCol] = useState('');
  const [showMaskingModal, setShowMaskingModal] = useState(false);

  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveDesc, setSaveDesc] = useState('');

  const [wsOpen, setWsOpen] = useState(false);
  const [srvOpen, setSrvOpen] = useState(false);
  const [dbOpen, setDbOpen] = useState(false);

  useEffect(() => {
    fetchServers();
    fetchWorkspaces();
    if (workspaceId) {
      loadWorkspace(parseInt(workspaceId));
    }
  }, [workspaceId]);

  // Fetch persistently masked columns for the active server/database
  useEffect(() => {
    if (selectedServer && selectedDatabase) {
      fetchPersistentMaskingRules();
    } else {
      setPersistentMaskedCols([]);
    }
    setAdHocMaskCols([]); // Clear ad-hoc columns when changing server or database
  }, [selectedServer, selectedDatabase]);

  const fetchPersistentMaskingRules = async () => {
    try {
      const res = await authenticatedFetch(`/api/masking_rules?servername=${selectedServer}&database_name=${selectedDatabase}`);
      if (res?.ok) {
        const data = await res.json();
        setPersistentMaskedCols(data || []);
      }
    } catch (e) {
      console.error("Failed to fetch persistent masking rules:", e);
    }
  };

  useEffect(() => {
    if (selectedServer && servers[selectedServer]) {
      const dbs = servers[selectedServer].databases;
      if (dbs.length > 0 && (!selectedDatabase || !dbs.includes(selectedDatabase))) {
        setSelectedDatabase(dbs[0]);
      }
    } else {
      setSelectedDatabase('');
    }
  }, [selectedServer, servers]);

  const fetchServers = async () => {
    try {
      const res = await authenticatedFetch('/api/database_information');
      if (res?.ok) {
        const data = await res.json();
        if (data.db_info) {
          setServers(data.db_info);
          const firstSrv = Object.keys(data.db_info)[0];
          if (firstSrv && !selectedServer) setSelectedServer(firstSrv);
        }
      }
    } catch (e) {
      console.error("Failed to fetch server info:", e);
    }
  };

  const fetchWorkspaces = async () => {
    try {
      const res = await authenticatedFetch('/api/workspaces');
      if (res?.ok) {
        const data = await res.json();
        setWorkspaces(data.workspaces || []);
      }
    } catch (e) {
      console.error("Failed to fetch workspaces:", e);
    }
  };

  const loadWorkspace = async (id: number) => {
    setLoading(true);
    try {
      const res = await authenticatedFetch(`/api/get_workspace_by_id/${id}`);
      if (res?.ok) {
        const data = await res.json();
        setCurrentWorkspace(data);
        setQuery(data.query);
        setSelectedServer(data.servername);
        setSelectedDatabase(data.database_name);
      }
    } catch (e) {
      console.error("Failed to load workspace:", e);
    }
    setLoading(false);
  };

  const executeQuery = async () => {
    if (!selectedServer || !selectedDatabase) {
      alert("Please select a server and database.");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await authenticatedFetch('/api/execute_query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          servername: selectedServer, 
          database_name: selectedDatabase,
          ad_hoc_mask_columns: adHocMaskCols
        })
      });
      if (res) {
        const data = await res.json();
        if (res.ok) {
          setResult(data);
        } else {
          setResult({ error: data.error || data.detail || 'Execution failed' });
        }
      }
    } catch (e: any) {
      setResult({ error: "Failed to connect to the execution server." });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveWorkspace = async () => {
    if (!saveName) return;
    setLoading(true);
    try {
      const res = await authenticatedFetch('/api/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: saveName,
          description: saveDesc,
          query: query,
          servername: selectedServer,
          database_name: selectedDatabase
        })
      });
      if (res?.ok) {
        const newItem = await res.json();
        setShowSaveModal(false);
        fetchWorkspaces();
        if (newItem.id) navigate(`/editor/${newItem.id}`);
      }
    } catch (e) {
      console.error("Save failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateWorkspace = async () => {
    if (!currentWorkspace) return;
    setLoading(true);
    try {
      const res = await authenticatedFetch(`/api/workspaces/${currentWorkspace.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: currentWorkspace.name,
          description: currentWorkspace.description,
          query: query,
          servername: selectedServer,
          database_name: selectedDatabase
        })
      });
      if (res?.ok) {
        alert('Workspace updated successfully.');
        fetchWorkspaces();
      }
    } catch (e) {
      console.error("Update failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const getTechColor = (tech?: string) => {
    if (!tech) return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    switch (tech.toLowerCase()) {
      case 'mssql': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'postgres': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'oracle': return 'bg-red-500/20 text-red-400 border-red-500/30';
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-100px)] gap-4 animate-in slide-in-from-bottom-4 duration-500">
      {/* Header with Custom Dropdowns */}
      <div className="bg-gray-900 p-4 rounded-xl shadow-2xl border border-gray-800 flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap gap-2 flex-1">
          {/* Workspace Switcher */}
          <div className="relative">
            <label className="block text-[10px] text-gray-500 font-bold uppercase mb-1 ml-1">Workspace</label>
            <button
              onClick={() => setWsOpen(!wsOpen)}
              className="flex items-center justify-between bg-gray-850 border border-gray-700 hover:border-indigo-500 rounded-lg px-4 py-2 text-sm w-[220px] transition-all text-white shadow-inner"
            >
              <span className="truncate">{currentWorkspace?.name || 'New Workspace'}</span>
              <svg className={`w-4 h-4 transition-transform ${wsOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
            </button>
            {wsOpen && (
              <div className="absolute top-full left-0 mt-2 w-64 bg-gray-850 border border-gray-700 rounded-xl shadow-2xl z-[150] overflow-hidden py-1">
                <button onClick={() => { setCurrentWorkspace(null); setQuery(''); setWsOpen(false); navigate('/editor'); }} className="w-full text-left px-4 py-2 text-xs text-indigo-400 hover:bg-indigo-500/10 font-bold border-b border-gray-700">+ CREATE NEW</button>
                {workspaces.length === 0 ? (
                  <div className="px-4 py-3 text-xs text-gray-600">No workspaces found</div>
                ) : (
                  workspaces.map(w => (
                    <button key={w.id} onClick={() => { loadWorkspace(w.id); setWsOpen(false); navigate(`/editor/${w.id}`); }} className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-800 flex flex-col gap-0.5 ${currentWorkspace?.id === w.id ? 'bg-indigo-500/10 border-l-2 border-indigo-500' : ''}`}>
                      <span className="font-medium text-gray-100">{w.name}</span>
                      <span className="text-[10px] text-gray-500 italic truncate">{w.description}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Server Selector */}
          <div className="relative">
            <label className="block text-[10px] text-gray-500 font-bold uppercase mb-1 ml-1">Server</label>
            <button
              onClick={() => setSrvOpen(!srvOpen)}
              className="flex items-center justify-between bg-gray-850 border border-gray-700 hover:border-indigo-500 rounded-lg px-4 py-2 text-sm w-[240px] transition-all text-white shadow-inner"
            >
              <div className="flex items-center gap-2 truncate">
                <span className={`w-1.5 h-1.5 rounded-full ${selectedServer ? 'bg-indigo-500' : 'bg-gray-600'}`}></span>
                {selectedServer || 'Select Server'}
              </div>
              <svg className={`w-4 h-4 transition-transform ${srvOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
            </button>
            {srvOpen && (
              <div className="absolute top-full left-0 mt-2 w-[280px] bg-gray-850 border border-gray-700 rounded-xl shadow-2xl z-[150] overflow-hidden py-1">
                {Object.keys(servers).length === 0 ? (
                  <div className="px-4 py-3 text-xs text-gray-600">No servers available</div>
                ) : (
                  Object.keys(servers).map(s => (
                    <button key={s} onClick={() => { setSelectedServer(s); setSrvOpen(false); }} className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-800 flex items-center justify-between ${selectedServer === s ? 'bg-indigo-500/10 border-l-2 border-indigo-500' : ''}`}>
                      <span className="font-medium text-gray-100">{s}</span>
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${getTechColor(servers[s].technology)}`}>{servers[s].technology || 'Unknown'}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Database Selector */}
          <div className="relative">
            <label className="block text-[10px] text-gray-500 font-bold uppercase mb-1 ml-1">Database</label>
            <button
              onClick={() => setDbOpen(!dbOpen)}
              disabled={!selectedServer}
              className={`flex items-center justify-between bg-gray-850 border border-gray-700 hover:border-indigo-500 rounded-lg px-4 py-2 text-sm w-[200px] transition-all text-white shadow-inner ${!selectedServer ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <span className="truncate">{selectedDatabase || 'Select DB'}</span>
              <svg className={`w-4 h-4 transition-transform ${dbOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
            </button>
            {dbOpen && (
              <div className="absolute top-full left-0 mt-2 w-56 bg-gray-850 border border-gray-700 rounded-xl shadow-2xl z-[150] max-h-64 overflow-y-auto py-1">
                {selectedServer && servers[selectedServer]?.databases.length > 0 ? (
                  servers[selectedServer].databases.map(db => (
                    <button key={db} onClick={() => { setSelectedDatabase(db); setDbOpen(false); }} className={`w-full text-left px-4 py-2.5 text-sm hover:bg-gray-800 text-gray-300 ${selectedDatabase === db ? 'bg-indigo-500/10 text-white font-bold' : ''}`}>
                      {db}
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-xs text-gray-600">No databases found</div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => currentWorkspace ? handleUpdateWorkspace() : setShowSaveModal(true)}
            disabled={loading}
            className="bg-emerald-600/10 hover:bg-emerald-600 text-emerald-400 hover:text-white px-5 py-2 rounded-lg border border-emerald-600/30 transition shadow-lg text-sm font-bold disabled:opacity-50"
          >
            {loading ? '...' : (currentWorkspace ? 'UPDATE' : 'SAVE')}
          </button>
          <button
            onClick={() => setShowMaskingModal(true)}
            disabled={!selectedServer || !selectedDatabase || loading}
            className="bg-amber-600/10 hover:bg-amber-600 text-amber-400 hover:text-white px-4 py-2 rounded-lg border border-amber-600/30 transition shadow-lg text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"
            title="Maskeleme Ayarları"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            MASKELEME
            {(persistentMaskedCols.length > 0 || adHocMaskCols.length > 0) && (
              <span className="bg-amber-500 text-gray-950 text-[10px] font-extrabold px-1.5 py-0.2 rounded-full leading-none">
                {persistentMaskedCols.length + adHocMaskCols.length}
              </span>
            )}
          </button>
          <button onClick={executeQuery} disabled={loading} className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-2 rounded-lg text-sm font-black shadow-xl transition-all flex items-center gap-2 tracking-widest active:scale-95 disabled:opacity-50">
            {loading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> : 'RUN'}
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* Editor Area */}
        <div className="flex-1 bg-gray-900 rounded-xl border border-gray-800 p-2 flex flex-col shadow-2xl overflow-hidden">
          <div className="flex justify-between items-center mb-2 px-2">
            <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest flex items-center gap-2">
              <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse"></span> Query Studio
            </div>
            <button onClick={() => setQuery('')} className="text-[10px] text-red-500/50 hover:text-red-500 transition">CLEAR ALL</button>
          </div>
          <div className="flex-1 rounded-lg overflow-hidden bg-gray-950">
            <AceEditor value={query} onChange={setQuery} height="100%" />
          </div>
        </div>

        {/* Results Area */}
        <div className="flex-1 bg-gray-900 rounded-xl border border-gray-800 p-2 flex flex-col min-w-0 shadow-2xl overflow-hidden">
          <div className="flex justify-between items-center mb-2 px-2">
            <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Live Execution Result</div>
            {result?.data && result.data.length > 0 && (
              <button onClick={() => {
                const ws = XLSX.utils.json_to_sheet(result.data!);
                const wb = XLSX.utils.book_new();
                XLSX.utils.book_append_sheet(wb, ws, 'Results');
                XLSX.writeFile(wb, 'query_export.xlsx');
              }} className="text-[10px] text-emerald-400 hover:text-emerald-300 font-bold flex items-center gap-1">
                EXPORT EXCEL
              </button>
            )}
          </div>

          <div className="flex-1 bg-gray-950 rounded-lg border border-gray-800 overflow-auto relative custom-scrollbar">
            {loading && (
              <div className="absolute inset-0 bg-gray-950/80 backdrop-blur-sm flex items-center justify-center z-20">
                <div className="flex flex-col items-center gap-3">
                  <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-sm font-bold text-indigo-400 tracking-tighter uppercase">Remote Execution in Progress...</span>
                </div>
              </div>
            )}

            {result?.error && (
              <div className="p-4 bg-red-950/20 text-red-400 border border-red-500/20 m-4 rounded-lg font-mono text-xs shadow-lg">
                <div className="font-black mb-1 opacity-50 underline uppercase">Query Exception:</div>
                {result.error}
              </div>
            )}

            {result?.message && !result.error && (
              <div className="p-4 text-emerald-400 text-center font-bold text-sm bg-emerald-950/10 rounded m-4 border border-emerald-500/10">
                {result.message}
              </div>
            )}

            {result?.data && result.data.length > 0 ? (
              <table className="w-full text-left border-separate border-spacing-0 text-xs">
                <thead className="bg-gray-900 sticky top-0 z-10">
                  <tr>
                    {Object.keys(result.data[0]).map(k => (
                      <th key={k} className="p-3 border-b border-gray-800 font-black text-gray-500 uppercase tracking-tighter bg-gray-900">{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/30">
                  {result.data.map((row, i) => (
                    <tr key={i} className="hover:bg-indigo-500/5 group transition-colors">
                      {Object.values(row).map((v: any, j) => (
                        <td key={j} className="p-3 text-gray-400 group-hover:text-gray-100 whitespace-nowrap font-medium">
                          {v === null ? <span className="text-gray-700 italic opacity-50">NULL</span> : String(v)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : !loading && !result?.error && !result?.message && (
              <div className="h-full flex flex-col items-center justify-center text-gray-800 gap-4">
                <svg className="w-20 h-20 opacity-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path></svg>
                <p className="text-xs font-bold opacity-30 tracking-[0.2em] uppercase">Ready for Execution</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <Modal isOpen={showSaveModal} onClose={() => setShowSaveModal(false)} title="New Workspace Configuration">
        <div className="space-y-4">
          <div>
            <label className="block text-[10px] text-gray-500 font-black uppercase mb-1 ml-1 tracking-widest">Workspace Name</label>
            <input value={saveName} onChange={e => setSaveName(e.target.value)} placeholder="e.g. Sales Report Q1" className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-white outline-none focus:ring-1 focus:ring-indigo-500 text-sm font-medium" />
          </div>
          <div>
            <label className="block text-[10px] text-gray-500 font-black uppercase mb-1 ml-1 tracking-widest">Description</label>
            <textarea value={saveDesc} onChange={e => setSaveDesc(e.target.value)} placeholder="Briefly describe the purpose of this query." className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-white h-24 outline-none focus:ring-1 focus:ring-indigo-500 resize-none text-sm" />
          </div>
          <div className="bg-indigo-500/5 p-4 rounded-lg border border-indigo-500/20 text-xs text-indigo-300">
            New workspaces are saved and accessible from the explorer dashboard.
          </div>
          <button
            onClick={handleSaveWorkspace}
            disabled={!saveName || loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white p-3 rounded-lg font-black shadow-xl transition-all disabled:opacity-30 tracking-widest"
          >
            {loading ? 'SAVING...' : 'SAVE WORKSPACE'}
          </button>
        </div>
      </Modal>

      <Modal isOpen={showMaskingModal} onClose={() => setShowMaskingModal(false)} title="Veri Maskeleme Ayarları">
        <div className="space-y-4">
          <div className="text-xs text-gray-400 leading-relaxed">
            Bu sorgu çalıştırılırken maskelenecek kolonları yönetin. Admin tarafından tanımlanmış kalıcı kurallar otomatik olarak uygulanır ve devre dışı bırakılamaz. Ek olarak geçici ad-hoc kurallar tanımlayabilirsiniz.
          </div>

          {/* Persistent Admin Masking Rules (Read-only) */}
          <div>
            <label className="block text-[10px] text-gray-500 font-black uppercase mb-2 tracking-wider">Yönetici Maskeleme Kuralları (Kalıcı)</label>
            {persistentMaskedCols.length === 0 ? (
              <div className="bg-gray-950 border border-gray-850 p-3 rounded-lg text-xs text-gray-500 italic">
                Bu veritabanı için yönetici tarafından tanımlanmış kalıcı maskeleme kuralı bulunmuyor.
              </div>
            ) : (
              <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                {persistentMaskedCols.map(col => (
                  <div key={col} className="flex items-center justify-between bg-gray-950 border border-gray-850/60 px-3 py-2 rounded-lg text-xs">
                    <span className="font-mono text-gray-300">{col}</span>
                    <span className="text-[9px] font-bold uppercase bg-red-950/45 text-red-400 border border-red-900/30 px-2 py-0.5 rounded-full select-none">
                      Kalıcı Maskeli
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* User Ad-Hoc Masking Rules */}
          <div>
            <label className="block text-[10px] text-gray-500 font-black uppercase mb-2 tracking-wider">Geçici Maskeleme Kuralları (Ad-Hoc)</label>
            
            {/* Input field to add custom columns */}
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                value={newAdHocCol}
                onChange={e => setNewAdHocCol(e.target.value)}
                placeholder="örn. email, salary, phone_number"
                className="flex-1 bg-gray-950 border border-gray-850 focus:border-indigo-500 rounded-lg px-3 py-2 text-white outline-none text-xs font-mono"
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (newAdHocCol.trim()) {
                      const trimmed = newAdHocCol.trim().toLowerCase();
                      if (!persistentMaskedCols.includes(trimmed) && !adHocMaskCols.includes(trimmed)) {
                        setAdHocMaskCols([...adHocMaskCols, trimmed]);
                      }
                      setNewAdHocCol('');
                    }
                  }
                }}
              />
              <button
                type="button"
                onClick={() => {
                  if (newAdHocCol.trim()) {
                    const trimmed = newAdHocCol.trim().toLowerCase();
                    if (!persistentMaskedCols.includes(trimmed) && !adHocMaskCols.includes(trimmed)) {
                      setAdHocMaskCols([...adHocMaskCols, trimmed]);
                    }
                    setNewAdHocCol('');
                  }
                }}
                className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 rounded-lg text-xs font-bold transition"
              >
                Ekle
              </button>
            </div>

            {adHocMaskCols.length === 0 ? (
              <div className="bg-gray-950 border border-gray-850 p-3 rounded-lg text-xs text-gray-500 italic">
                Sadece bu işlem için geçerli olmak üzere ek maskelenecek kolon adı girin.
              </div>
            ) : (
              <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                {adHocMaskCols.map(col => (
                  <div key={col} className="flex items-center justify-between bg-gray-950 border border-gray-850/60 px-3 py-2 rounded-lg text-xs">
                    <span className="font-mono text-indigo-300">{col}</span>
                    <button
                      type="button"
                      onClick={() => setAdHocMaskCols(adHocMaskCols.filter(c => c !== col))}
                      className="text-gray-500 hover:text-red-400 transition-all font-bold text-xs"
                      title="Kuralı kaldır"
                    >
                      Kaldır
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={() => setShowMaskingModal(false)}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white p-2.5 rounded-lg font-bold text-xs transition tracking-widest uppercase mt-2 shadow-lg"
          >
            Tamam
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default SqlEditor;

```
</details>



#### <a name="frontendpagesadmintsx"></a> `frontend/pages/Admin.tsx`
**Açıklama:** Admin yönetim panelini, onay bekleyen sorguları listeleme, detaylı SQL AST analizi risk durumunu görme, sorguları onaylama/reddetme ve yeni hedef veritabanı tanımlama özelliklerini içerecek şekilde yenileyen sayfa.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/frontend/pages/Admin.tsx b/frontend/pages/Admin.tsx
index 9d0fba0..0a0f5ec 100644
--- a/frontend/pages/Admin.tsx
+++ b/frontend/pages/Admin.tsx
@@ -1,25 +1,66 @@
-
 import React, { useEffect, useState } from 'react';
 import { authenticatedFetch } from '../services/api';
 import { PendingQuery } from '../types';
 import Modal from '../components/Modal';
 import AceEditor from '../components/AceEditor';
 
+interface Database {
+  id: number;
+  servername: string;
+  database_name: string;
+  technology: string;
+  db_username?: string;
+}
+
+interface MaskingRule {
+  table_name: string;
+  column_name: string;
+  masking_type: string;
+  is_active: boolean;
+}
+
 const Admin: React.FC = () => {
+  // Navigation & Tab state
+  const [activeTab, setActiveTab] = useState<'approvals' | 'masking'>('approvals');
+
+  // --- Query Approvals State ---
   const [queries, setQueries] = useState<PendingQuery[]>([]);
   const [selectedQuery, setSelectedQuery] = useState<PendingQuery | null>(null);
   const [previewData, setPreviewData] = useState<any[]>([]);
-  const [loading, setLoading] = useState(false);
+  const [loadingPreview, setLoadingPreview] = useState(false);
+
+  // --- Databases & Masking State ---
+  const [databases, setDatabases] = useState<Database[]>([]);
+  const [selectedDb, setSelectedDb] = useState<Database | null>(null);
+  const [loadingDbs, setLoadingDbs] = useState(false);
+  const [savingRules, setSavingRules] = useState(false);
+  const [loadingSchema, setLoadingSchema] = useState(false);
+
+  // Add Database Form State
+  const [dbForm, setDbForm] = useState({
+    servername: '',
+    database_name: '',
+    technology: 'mssql'
+  });
+  const [addingDb, setAddingDb] = useState(false);
+  const [generatedCreds, setGeneratedCreds] = useState<{ username: string; password: string } | null>(null);
+
+  // Schema Discovery & Masking Rules State
+  const [schema, setSchema] = useState<Record<string, string[]>>({});
+  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
+  const [maskedColumns, setMaskedColumns] = useState<Set<string>>(new Set()); // Formatted as "table_name.column_name"
 
   useEffect(() => {
-    // Fixed: Casting window to any to access globally loaded ace library to avoid TS error
+    // Initialize AceEditor config
     const ace = (window as any).ace;
     if (ace) {
       ace.config.set('basePath', 'https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.12/');
     }
     fetchPending();
+    fetchDatabases();
   }, []);
 
+  // Fetch pending queries for approvals
   const fetchPending = async () => {
     const res = await authenticatedFetch('/api/admin/queries_to_approve');
     if (res?.ok) {
@@ -28,9 +69,21 @@ const Admin: React.FC = () => {
     }
   };
 
+  // Fetch registered databases
+  const fetchDatabases = async () => {
+    setLoadingDbs(true);
+    const res = await authenticatedFetch('/api/admin/databases');
+    if (res?.ok) {
+      const data = await res.json();
+      setDatabases(data.databases || []);
+    }
+    setLoadingDbs(false);
+  };
+
+  // Run preview execution for a selected query
   const runPreview = async () => {
     if (!selectedQuery) return;
-    setLoading(true);
+    setLoadingPreview(true);
     try {
       const res = await authenticatedFetch(`/api/admin/execute_for_preview/${selectedQuery.workspace_id}`, { method: 'POST' });
       if (res?.ok) {
@@ -40,10 +93,11 @@ const Admin: React.FC = () => {
     } catch (e) {
       console.error(e);
     } finally {
-      setLoading(false);
+      setLoadingPreview(false);
     }
   };
 
+  // Handle query approval or rejection
   const handleDecision = async (approved: boolean, executable: boolean = false) => {
     if (!selectedQuery) return;
     const url = approved 
@@ -65,90 +119,685 @@ const Admin: React.FC = () => {
     }
   };
 
+  // Add a new database to the system and generate secure access credentials
+  const handleAddDatabase = async (e: React.FormEvent) => {
+    e.preventDefault();
+    if (!dbForm.servername || !dbForm.database_name) return;
+    setAddingDb(true);
+    try {
+      const res = await authenticatedFetch('/api/admin/add_database', {
+        method: 'POST',
+        headers: { 'Content-Type': 'application/json' },
+        body: JSON.stringify({
+          servername: dbForm.servername,
+          database_name: dbForm.database_name,
+          tech_name: dbForm.technology
+        })
+      });
+      if (res?.ok) {
+        const data = await res.json();
+        // Set the generated credentials to show in the success modal
+        setGeneratedCreds({
+          username: data.db_username,
+          password: data.db_password
+        });
+        setDbForm({ servername: '', database_name: '', technology: 'mssql' });
+        fetchDatabases();
+      } else {
+        const errData = await res?.json();
+        alert(errData?.detail || "Failed to add database.");
+      }
+    } catch (e) {
+      console.error(e);
+    } finally {
+      setAddingDb(false);
+    }
+  };
+
+  // Select a database to load its schema and masking rules
+  const handleSelectDatabase = async (db: Database) => {
+    setSelectedDb(db);
+    setSchema({});
+    setMaskedColumns(new Set());
+    setExpandedTables({});
+    
+    // Load schema & masking rules in parallel
+    await Promise.all([
+      discoverSchema(db.id),
+      loadMaskingRules(db.id)
+    ]);
+  };
+
+  // Discover tables & columns for a database
+  const discoverSchema = async (dbId: number) => {
+    setLoadingSchema(true);
+    try {
+      const res = await authenticatedFetch(`/api/admin/databases/${dbId}/discover_schema`);
+      if (res?.ok) {
+        const data = await res.json();
+        setSchema(data || {});
+      }
+    } catch (e) {
+      console.error(e);
+    } finally {
+      setLoadingSchema(false);
+    }
+  };
+
+  // Load persistent masking rules for a database
+  const loadMaskingRules = async (dbId: number) => {
+    try {
+      const res = await authenticatedFetch(`/api/admin/databases/${dbId}/masking_rules`);
+      if (res?.ok) {
+        const rules: MaskingRule[] = await res.json();
+        const masked = new Set<string>();
+        rules.forEach(r => {
+          if (r.is_active) {
+            masked.add(`${r.table_name.toLowerCase()}.${r.column_name.toLowerCase()}`);
+          }
+        });
+        setMaskedColumns(masked);
+      }
+    } catch (e) {
+      console.error(e);
+    }
+  };
+
+  // Toggle active masking rule on a specific table/column
+  const handleToggleMasking = (tableName: string, columnName: string) => {
+    const key = `${tableName.toLowerCase()}.` + `${columnName.toLowerCase()}`;
+    const newMasked = new Set(maskedColumns);
+    if (newMasked.has(key)) {
+      newMasked.delete(key);
+    } else {
+      newMasked.add(key);
+    }
+    setMaskedColumns(newMasked);
+  };
+
+  // Save masking rules to backend
+  const handleSaveMaskingRules = async () => {
+    if (!selectedDb) return;
+    setSavingRules(true);
+    
+    const rulesList: MaskingRule[] = [];
+    Object.keys(schema).forEach(tableName => {
+      schema[tableName].forEach(columnName => {
+        const key = `${tableName.toLowerCase()}.${columnName.toLowerCase()}`;
+        if (maskedColumns.has(key)) {
+          rulesList.push({
+            table_name: tableName,
+            column_name: columnName,
+            masking_type: 'default',
+            is_active: true
+          });
+        }
+      });
+    });
+
+    try {
+      const res = await authenticatedFetch(`/api/admin/databases/${selectedDb.id}/masking_rules`, {
+        method: 'POST',
+        headers: { 'Content-Type': 'application/json' },
+        body: JSON.stringify({ rules: rulesList })
+      });
+      if (res?.ok) {
+        alert("Masking rules updated successfully.");
+      } else {
+        alert("Failed to save masking rules.");
+      }
+    } catch (e) {
+      console.error(e);
+    } finally {
+      setSavingRules(false);
+    }
+  };
+
+  const toggleTableExpand = (tableName: string) => {
+    setExpandedTables(prev => ({
+      ...prev,
+      [tableName]: !prev[tableName]
+    }));
+  };
+
+  // Custom helper to safety lowercase
+  const safetyLower = (val: string) => val ? val.toLowerCase() : '';
+
   return (
-    <div className="max-w-6xl mx-auto">
-      <h1 className="text-3xl font-bold mb-6 text-white border-b border-gray-700 pb-4">Admin Approval Panel</h1>
-      
-      {queries.length === 0 ? (
-         <div className="bg-gray-800 p-8 rounded-xl text-center text-gray-400">No pending queries found.</div>
-      ) : (
-        <div className="grid gap-4">
-          {queries.map(q => (
-            <div key={q.workspace_id} className="bg-gray-800 border border-gray-700 rounded-xl p-4 flex justify-between items-start">
-               <div>
-                  <div className="flex items-center gap-3 mb-2">
-                     <span className="font-bold text-white text-lg">{q.username}</span>
-                     <span className="text-xs bg-yellow-900/50 text-yellow-200 border border-yellow-700 px-2 py-0.5 rounded">{q.status}</span>
-                     {q.risk_type && <span className="text-xs bg-red-900/50 text-red-200 border border-red-700 px-2 py-0.5 rounded">{q.risk_type}</span>}
+    <div className="max-w-7xl mx-auto px-4 py-6">
+      {/* Premium Dashboard Header with Sub-header Navigation */}
+      <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-800 pb-5 mb-8">
+        <div>
+          <h1 className="text-3xl font-bold text-white tracking-tight">Yönetim Paneli</h1>
+          <p className="text-sm text-gray-400 mt-1">Sorgu onayları, veritabanı bağlantıları ve veri maskeleme konfigürasyonları.</p>
+        </div>
+        
+        {/* Modern Switcher Tabs */}
+        <div className="flex bg-gray-900/80 border border-gray-800 p-1 rounded-xl mt-4 md:mt-0 shadow-inner">
+          <button 
+            onClick={() => setActiveTab('approvals')}
+            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
+              activeTab === 'approvals' 
+                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
+                : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
+            }`}
+          >
+            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
+            </svg>
+            Sorgu Onayları
+            {queries.length > 0 && (
+              <span className="ml-1 px-1.5 py-0.5 text-xs font-bold bg-red-500 text-white rounded-full leading-none animate-pulse">
+                {queries.length}
+              </span>
+            )}
+          </button>
+          <button 
+            onClick={() => setActiveTab('masking')}
+            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
+              activeTab === 'masking' 
+                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
+                : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
+            }`}
+          >
+            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
+            </svg>
+            Veritabanı & Maskeleme
+          </button>
+        </div>
+      </div>
+
+      {/* ==================== TAB: QUERY APPROVALS ==================== */}
+      {activeTab === 'approvals' && (
+        <div>
+          {queries.length === 0 ? (
+            <div className="bg-gray-850 border border-gray-800 p-16 rounded-2xl text-center shadow-xl">
+              <div className="inline-flex p-4 rounded-full bg-gray-800 text-indigo-400 mb-4">
+                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
+                </svg>
+              </div>
+              <h3 className="text-lg font-bold text-white">Bekleyen Sorgu Bulunmuyor</h3>
+              <p className="text-gray-400 text-sm mt-1 max-w-sm mx-auto">Tüm riskli sorgu analiz talepleri karara bağlanmış durumda.</p>
+            </div>
+          ) : (
+            <div className="grid gap-4">
+              {queries.map(q => (
+                <div key={q.workspace_id} className="bg-gray-850 border border-gray-800 hover:border-gray-700 rounded-xl p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 transition duration-200 shadow-md">
+                  <div className="flex-1 min-w-0">
+                    <div className="flex flex-wrap items-center gap-2 mb-2.5">
+                      <span className="font-semibold text-white text-lg">{q.username}</span>
+                      <span className="text-xs font-medium bg-amber-900/40 text-amber-300 border border-amber-800/60 px-2.5 py-0.5 rounded-full">
+                        {q.status === 'waiting_for_approval' ? 'Onay Bekliyor' : q.status}
+                      </span>
+                      {q.risk_type && (
+                        <span className="text-xs font-medium bg-red-950/55 text-red-300 border border-red-850 px-2.5 py-0.5 rounded-full">
+                          {q.risk_type} Riski
+                        </span>
+                      )}
+                    </div>
+                    <div className="text-xs text-gray-400 flex items-center gap-2 mb-3">
+                      <span className="font-medium text-gray-300">{q.servername}</span>
+                      <span className="text-gray-600">&bull;</span>
+                      <span className="font-medium text-gray-300">{q.database}</span>
+                    </div>
+                    <div className="bg-gray-900/90 border border-gray-800/80 p-3.5 rounded-lg font-mono text-xs text-gray-300 max-w-4xl overflow-hidden text-ellipsis whitespace-nowrap">
+                      {q.query}
+                    </div>
                   </div>
-                  <div className="text-sm text-gray-400 mb-2">
-                    {q.servername} &bull; {q.database}
+                  <button 
+                    onClick={() => {
+                      setSelectedQuery(q);
+                      setPreviewData([]);
+                    }}
+                    className="w-full md:w-auto bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-indigo-600/10 flex items-center justify-center gap-2"
+                  >
+                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
+                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
+                    </svg>
+                    İncele
+                  </button>
+                </div>
+              ))}
+            </div>
+          )}
+        </div>
+      )}
+
+      {/* ==================== TAB: DATABASE & MASKING ==================== */}
+      {activeTab === 'masking' && (
+        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
+          
+          {/* Left Column: DB Registration & DB List */}
+          <div className="lg:col-span-5 flex flex-col gap-6">
+            
+            {/* Database Registration Form */}
+            <div className="bg-gray-850 border border-gray-800 rounded-2xl p-6 shadow-md">
+              <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-4 border-b border-gray-800 pb-3">
+                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
+                </svg>
+                Yeni Veritabanı Ekle
+              </h2>
+              
+              <form onSubmit={handleAddDatabase} className="space-y-4">
+                <div>
+                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Sunucu Adresi (Host)</label>
+                  <input 
+                    type="text"
+                    required
+                    placeholder="örn. localhost veya 10.0.0.5"
+                    value={dbForm.servername}
+                    onChange={e => setDbForm({ ...dbForm, servername: e.target.value })}
+                    className="w-full bg-gray-900 border border-gray-800 hover:border-gray-700 focus:border-indigo-600 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition"
+                  />
+                </div>
+
+                <div className="grid grid-cols-2 gap-4">
+                  <div>
+                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Veritabanı Adı</label>
+                    <input 
+                      type="text"
+                      required
+                      placeholder="örn. Northwind"
+                      value={dbForm.database_name}
+                      onChange={e => setDbForm({ ...dbForm, database_name: e.target.value })}
+                      className="w-full bg-gray-900 border border-gray-800 hover:border-gray-700 focus:border-indigo-600 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition"
+                    />
                   </div>
-                  <div className="bg-gray-900 p-3 rounded font-mono text-sm text-gray-300 max-w-3xl overflow-hidden text-ellipsis whitespace-nowrap">
-                    {q.query}
+                  <div>
+                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Teknoloji</label>
+                    <select
+                      value={dbForm.technology}
+                      onChange={e => setDbForm({ ...dbForm, technology: e.target.value })}
+                      className="w-full bg-gray-900 border border-gray-800 hover:border-gray-700 focus:border-indigo-600 rounded-lg px-3 py-2.5 text-sm text-white outline-none transition"
+                    >
+                      <option value="mssql">MS SQL Server</option>
+                      <option value="postgresql">PostgreSQL</option>
+                      <option value="mysql">MySQL</option>
+                    </select>
                   </div>
-               </div>
-               <button 
-                 onClick={() => setSelectedQuery(q)}
-                 className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded text-sm font-medium transition"
-               >
-                 Review
-               </button>
+                </div>
+
+                <button 
+                  type="submit"
+                  disabled={addingDb}
+                  className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-800 text-white font-semibold py-2.5 rounded-lg text-sm transition shadow-md shadow-indigo-600/10 mt-2"
+                >
+                  {addingDb ? 'Veritabanı Ekleniyor...' : 'Ekle & Güvenli Kullanıcı Üret'}
+                </button>
+              </form>
+            </div>
+
+            {/* Database List */}
+            <div className="bg-gray-850 border border-gray-800 rounded-2xl p-6 shadow-md flex-1">
+              <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-4 border-b border-gray-800 pb-3">
+                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.58 4 8 4s8-1.79 8-4M4 7c0-2.21 3.58-4 8-4s8 1.79 8 4m0 5c0 2.21-3.58 4-8 4s-8-1.79-8-4" />
+                </svg>
+                Kayıtlı Veritabanları
+              </h2>
+
+              {loadingDbs ? (
+                <div className="text-center py-8 text-gray-500 text-sm">Veritabanları yükleniyor...</div>
+              ) : databases.length === 0 ? (
+                <div className="text-center py-8 text-gray-500 text-sm">Henüz kayıtlı veritabanı bulunmuyor.</div>
+              ) : (
+                <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
+                  {databases.map(db => (
+                    <button
+                      key={db.id}
+                      onClick={() => handleSelectDatabase(db)}
+                      className={`w-full text-left p-3 rounded-xl border transition duration-150 flex justify-between items-center ${
+                        selectedDb?.id === db.id 
+                          ? 'bg-indigo-900/30 border-indigo-700 text-white' 
+                          : 'bg-gray-900/60 border-gray-800 hover:border-gray-700 text-gray-300 hover:text-white'
+                      }`}
+                    >
+                      <div>
+                        <div className="font-semibold text-sm">{db.database_name}</div>
+                        <div className="text-xs text-gray-400 mt-0.5">{db.servername} &bull; {db.technology.toUpperCase()}</div>
+                      </div>
+                      <svg className={`w-4.5 h-4.5 transition-transform duration-200 ${selectedDb?.id === db.id ? 'text-indigo-400 transform translate-x-0.5' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
+                      </svg>
+                    </button>
+                  ))}
+                </div>
+              )}
             </div>
-          ))}
+
+          </div>
+
+          {/* Right Column: Schema TreeView & Masking Rules */}
+          <div className="lg:col-span-7">
+            {selectedDb ? (
+              <div className="bg-gray-850 border border-gray-800 rounded-2xl p-6 shadow-md h-full flex flex-col">
+                
+                {/* Panel Header */}
+                <div className="flex flex-wrap justify-between items-center border-b border-gray-800 pb-4 mb-4 gap-4">
+                  <div>
+                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
+                      <span className="text-indigo-400">#</span>
+                      {selectedDb.database_name} Maskeleme Kuralları
+                    </h2>
+                    <p className="text-xs text-gray-400 mt-0.5">{selectedDb.servername} sunucusundaki aktif şema kolonları.</p>
+                  </div>
+                  
+                  <button 
+                    onClick={() => discoverSchema(selectedDb.id)}
+                    disabled={loadingSchema}
+                    className="bg-gray-800 hover:bg-gray-700 disabled:bg-gray-850 text-xs font-semibold text-gray-300 hover:text-white px-3 py-2 rounded-lg border border-gray-700 transition flex items-center gap-1.5"
+                  >
+                    <svg className={`w-3.5 h-3.5 ${loadingSchema ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
+                    </svg>
+                    Şemayı Yenile
+                  </button>
+                </div>
+
+                {/* Schema TreeView Container */}
+                <div className="flex-1 min-h-[380px] max-h-[480px] overflow-y-auto bg-gray-900/65 border border-gray-800/80 rounded-xl p-4">
+                  {loadingSchema ? (
+                    <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-2">
+                      <svg className="w-8 h-8 text-indigo-500 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
+                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
+                      </svg>
+                      <span className="text-sm font-medium">Veritabanı şeması taranıyor...</span>
+                    </div>
+                  ) : Object.keys(schema).length === 0 ? (
+                    <div className="h-full flex flex-col items-center justify-center text-gray-500 text-sm text-center px-6">
+                      <svg className="w-10 h-10 text-gray-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
+                      </svg>
+                      Bu veritabanına ait tablo bilgisi bulunamadı veya bağlantı kurulamadı. Lütfen sunucu ayarlarını ve ağ erişimini kontrol edin.
+                    </div>
+                  ) : (
+                    <div className="space-y-2.5">
+                      {Object.keys(schema).map(tableName => {
+                        const isExpanded = !!expandedTables[tableName];
+                        const columns = schema[tableName];
+                        return (
+                          <div key={tableName} className="border border-gray-800/60 rounded-lg overflow-hidden bg-gray-950/40">
+                            {/* Table Node */}
+                            <button
+                              onClick={() => toggleTableExpand(tableName)}
+                              className="w-full flex items-center justify-between p-3 hover:bg-gray-800/25 transition text-left"
+                            >
+                              <div className="flex items-center gap-2">
+                                <svg className={`w-4 h-4 text-gray-400 transition-transform duration-150 ${isExpanded ? 'transform rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
+                                </svg>
+                                <svg className="w-4 h-4 text-indigo-400/80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
+                                </svg>
+                                <span className="font-semibold text-sm text-gray-200">{tableName}</span>
+                              </div>
+                              <span className="text-xs text-indigo-400/85 font-semibold bg-indigo-950/40 px-2 py-0.5 rounded-full">
+                                {columns.length} Kolon
+                              </span>
+                            </button>
+
+                            {/* Column Leaf Nodes (Expanded) */}
+                            {isExpanded && (
+                              <div className="border-t border-gray-900 bg-gray-950/80 px-4 py-2 space-y-1.5 pl-9">
+                                {columns.map(col => {
+                                  const isMasked = maskedColumns.has(`${tableName.toLowerCase()}.${col.toLowerCase()}`);
+                                  return (
+                                    <div 
+                                      key={col} 
+                                      onClick={() => handleToggleMasking(tableName, col)}
+                                      className="flex items-center justify-between py-1.5 hover:bg-gray-900/40 rounded px-2 cursor-pointer select-none"
+                                    >
+                                      <span className="text-xs text-gray-300 font-mono">{col}</span>
+                                      <div className="flex items-center gap-2">
+                                        {isMasked && (
+                                          <span className="text-[10px] uppercase font-bold bg-amber-950/50 text-amber-400 border border-amber-800/40 px-1.5 py-0.2 rounded">
+                                            Maskeli
+                                          </span>
+                                        )}
+                                        <input 
+                                          type="checkbox" 
+                                          checked={isMasked}
+                                          onChange={() => {}} // Handled by div onClick
+                                          className="w-4 h-4 rounded text-indigo-600 bg-gray-900 border-gray-700 focus:ring-indigo-600 focus:ring-offset-gray-900"
+                                        />
+                                      </div>
+                                    </div>
+                                  );
+                                })}
+                              </div>
+                            )}
+                          </div>
+                        );
+                      })}
+                    </div>
+                  )}
+                </div>
+
+                {/* Save Rules Button */}
+                <div className="mt-5 border-t border-gray-800 pt-4 flex justify-between items-center">
+                  <span className="text-xs text-gray-400 font-medium">
+                    Toplam <span className="text-amber-400 font-bold">{maskedColumns.size}</span> kolon maskelenmek üzere seçildi.
+                  </span>
+                  <button 
+                    onClick={handleSaveMaskingRules}
+                    disabled={savingRules || loadingSchema}
+                    className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-800 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition shadow-md shadow-indigo-600/10 flex items-center gap-2"
+                  >
+                    {savingRules ? (
+                      <>
+                        <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
+                        </svg>
+                        Kaydediliyor...
+                      </>
+                    ) : (
+                      <>
+                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
+                        </svg>
+                        Kuralları Kaydet
+                      </>
+                    )}
+                  </button>
+                </div>
+
+              </div>
+            ) : (
+              <div className="bg-gray-850 border border-gray-800 p-16 rounded-2xl text-center shadow-xl h-full flex flex-col items-center justify-center">
+                <div className="p-4 rounded-full bg-gray-800 text-indigo-400 mb-4">
+                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
+                  </svg>
+                </div>
+                <h3 className="text-lg font-bold text-white">Maskeleme Yönetimi</h3>
+                <p className="text-gray-400 text-sm mt-1 max-w-xs mx-auto">Sol paneldeki kayıtlı veritabanlarından birini seçerek aktif şema kolonları üzerinde maskeleme kuralları tanımlayabilirsiniz.</p>
+              </div>
+            )}
+          </div>
+
         </div>
       )}
 
+      {/* ==================== MODAL: GENERATED CREDENTIALS ==================== */}
+      {generatedCreds && (
+        <Modal 
+          isOpen={true} 
+          onClose={() => setGeneratedCreds(null)} 
+          title="Veritabanı Erişim Bilgileri" 
+          size="md"
+        >
+          <div className="space-y-4">
+            <div className="bg-amber-950/40 border border-amber-900/50 p-4 rounded-xl flex gap-3">
+              <svg className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
+              </svg>
+              <div>
+                <h4 className="text-xs font-bold text-amber-300 uppercase">Önemli Güvenlik Uyarısı</h4>
+                <p className="text-xs text-amber-400/90 mt-1 leading-relaxed">
+                  WebQuery, bu veritabanına erişmek için aşağıdaki benzersiz servis hesabı kimlik bilgilerini üretmiştir. Şifre sadece <strong>bir kez</strong> gösterilecektir. Lütfen bilgileri güvenli bir yere kaydedin.
+                </p>
+              </div>
+            </div>
+
+            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3 font-mono text-xs">
+              <div className="flex justify-between items-center">
+                <span className="text-gray-400 uppercase font-bold text-[10px]">Üretilen Kullanıcı Adı:</span>
+                <span className="text-indigo-300 font-semibold select-all">{generatedCreds.username}</span>
+              </div>
+              <div className="border-t border-gray-800/50 pt-2.5 flex justify-between items-center">
+                <span className="text-gray-400 uppercase font-bold text-[10px]">Üretilen Şifre:</span>
+                <span className="text-indigo-300 font-semibold select-all">{generatedCreds.password}</span>
+              </div>
+            </div>
+
+            <div className="flex justify-end pt-2">
+              <button 
+                onClick={() => {
+                  navigator.clipboard.writeText(`Username: ${generatedCreds.username}\nPassword: ${generatedCreds.password}`);
+                  alert("Credentials copied to clipboard.");
+                  setGeneratedCreds(null);
+                }}
+                className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition flex items-center gap-1.5"
+              >
+                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
+                </svg>
+                Kopyala & Kapat
+              </button>
+            </div>
+          </div>
+        </Modal>
+      )}
+
+      {/* ==================== MODAL: REVIEW QUERY ==================== */}
       {selectedQuery && (
-        <Modal isOpen={true} onClose={() => setSelectedQuery(null)} title="Review Query" size="xl">
-          <div className="flex flex-col gap-4">
-             <div className="grid grid-cols-2 gap-4 text-sm text-gray-300 bg-gray-900 p-3 rounded">
-                <div>User: <span className="text-white">{selectedQuery.username}</span></div>
-                <div>Server: <span className="text-white">{selectedQuery.servername}</span></div>
-                <div>Database: <span className="text-white">{selectedQuery.database}</span></div>
-                <div>Risk: <span className="text-red-300">{selectedQuery.risk_type || 'None'}</span></div>
-             </div>
-
-             <div>
-               <label className="text-xs text-gray-400 font-bold uppercase mb-1 block">Full Query</label>
-               <AceEditor value={selectedQuery.query} readOnly={true} height="200px" />
-             </div>
-
-             <div className="border-t border-gray-700 pt-4">
-                <div className="flex justify-between items-center mb-2">
-                   <h4 className="text-sm font-bold uppercase text-gray-400">Result Preview</h4>
-                   <button onClick={runPreview} disabled={loading} className="text-xs bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded">
-                     {loading ? 'Running...' : 'Run Preview'}
-                   </button>
-                </div>
-                <div className="bg-gray-900 rounded border border-gray-700 h-48 overflow-auto">
-                   {previewData.length > 0 ? (
-                     <table className="w-full text-xs text-left">
-                       <thead className="bg-gray-800 text-gray-300 sticky top-0">
-                         <tr>{Object.keys(previewData[0]).map(k => <th key={k} className="p-2">{k}</th>)}</tr>
-                       </thead>
-                       <tbody>
-                         {previewData.map((r, i) => (
-                           <tr key={i} className="border-b border-gray-800 text-gray-400">
-                              {Object.values(r).map((v:any, j) => <td key={j} className="p-2 whitespace-nowrap">{String(v)}</td>)}
-                           </tr>
-                         ))}
-                       </tbody>
-                     </table>
-                   ) : (
-                     <div className="h-full flex items-center justify-center text-gray-500 text-sm">Click 'Run Preview' to see results</div>
-                   )}
-                </div>
-             </div>
+        <Modal 
+          isOpen={true} 
+          onClose={() => setSelectedQuery(null)} 
+          title="Sorgu Talebi İncelemesi" 
+          size="xl"
+        >
+          <div className="flex flex-col gap-5">
+            
+            {/* Metadata Summary Grid */}
+            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-gray-900 border border-gray-800 p-4 rounded-xl text-xs font-medium">
+              <div>
+                <span className="text-gray-400 block mb-0.5">Kullanıcı:</span>
+                <span className="text-white text-sm font-bold">{selectedQuery.username}</span>
+              </div>
+              <div>
+                <span className="text-gray-400 block mb-0.5">Sunucu:</span>
+                <span className="text-white text-sm font-semibold">{selectedQuery.servername}</span>
+              </div>
+              <div>
+                <span className="text-gray-400 block mb-0.5">Veritabanı:</span>
+                <span className="text-white text-sm font-semibold">{selectedQuery.database}</span>
+              </div>
+              <div>
+                <span className="text-gray-400 block mb-0.5">Risk Seviyesi:</span>
+                <span className={`text-sm font-bold ${selectedQuery.risk_type ? 'text-red-400' : 'text-emerald-400'}`}>
+                  {selectedQuery.risk_type || 'Yok'}
+                </span>
+              </div>
+            </div>
+
+            {/* SQL Query Editor Preview */}
+            <div>
+              <label className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5 block">SQL Sorgusu</label>
+              <div className="border border-gray-800 rounded-xl overflow-hidden">
+                <AceEditor value={selectedQuery.query} readOnly={true} height="220px" />
+              </div>
+            </div>
+
+            {/* Result Preview Panel */}
+            <div className="border-t border-gray-800 pt-5">
+              <div className="flex justify-between items-center mb-3">
+                <h4 className="text-xs font-bold uppercase text-gray-400 tracking-wider">Sonuç Önizleme</h4>
+                <button 
+                  onClick={runPreview} 
+                  disabled={loadingPreview} 
+                  className="bg-gray-850 hover:bg-gray-800 border border-gray-700 disabled:bg-gray-900 text-xs font-semibold text-white px-3.5 py-1.5 rounded-lg transition flex items-center gap-1"
+                >
+                  {loadingPreview ? (
+                    <>
+                      <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
+                      </svg>
+                      Çalıştırılıyor...
+                    </>
+                  ) : (
+                    <>
+                      <svg className="w-3 h-3 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
+                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
+                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
+                      </svg>
+                      Önizleme Çalıştır
+                    </>
+                  )}
+                </button>
+              </div>
+
+              <div className="bg-gray-900 border border-gray-800 rounded-xl h-48 overflow-auto">
+                {previewData.length > 0 ? (
+                  <table className="w-full text-xs text-left border-collapse">
+                    <thead className="bg-gray-850 text-gray-300 border-b border-gray-800 sticky top-0">
+                      <tr>
+                        {Object.keys(previewData[0]).map(k => (
+                          <th key={k} className="p-3 font-semibold border-r border-gray-800 last:border-0">{k}</th>
+                        ))}
+                      </tr>
+                    </thead>
+                    <tbody className="divide-y divide-gray-800/60">
+                      {previewData.map((r, i) => (
+                        <tr key={i} className="hover:bg-gray-850/30 text-gray-300 transition duration-100">
+                          {Object.values(r).map((v: any, j) => (
+                            <td key={j} className="p-3 border-r border-gray-800/40 last:border-0 font-mono whitespace-nowrap overflow-hidden text-ellipsis max-w-[200px]">
+                              {String(v)}
+                            </td>
+                          ))}
+                        </tr>
+                      ))}
+                    </tbody>
+                  </table>
+                ) : (
+                  <div className="h-full flex items-center justify-center text-gray-500 text-xs">
+                    Önizleme verilerini görüntülemek için yukarıdaki 'Önizleme Çalıştır' butonuna basın.
+                  </div>
+                )}
+              </div>
+            </div>
+
+            {/* Action Decision Buttons */}
+            <div className="flex flex-wrap justify-end gap-3 pt-3 border-t border-gray-800 mt-2">
+              <button 
+                onClick={() => handleDecision(false)} 
+                className="bg-red-650 hover:bg-red-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-red-900/10"
+              >
+                Reddet
+              </button>
+              <button 
+                onClick={() => handleDecision(true, false)} 
+                className="bg-amber-600 hover:bg-amber-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-amber-700/10"
+              >
+                Onayla (Gözlem Modu)
+              </button>
+              <button 
+                onClick={() => handleDecision(true, true)} 
+                className="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-emerald-700/10"
+              >
+                Onayla & Çalıştırılabilir Yap
+              </button>
+            </div>
 
-             <div className="flex justify-end gap-2 pt-2">
-                <button onClick={() => handleDecision(false)} className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded shadow">Reject</button>
-                <button onClick={() => handleDecision(true, false)} className="bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-2 rounded shadow">Approve (No Exec)</button>
-                <button onClick={() => handleDecision(true, true)} className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded shadow">Approve & Executable</button>
-             </div>
           </div>
         </Modal>
       )}
+
     </div>
   );
 };
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (Admin.tsx)</summary>

```tsx
import React, { useEffect, useState } from 'react';
import { authenticatedFetch } from '../services/api';
import { PendingQuery } from '../types';
import Modal from '../components/Modal';
import AceEditor from '../components/AceEditor';

interface Database {
  id: number;
  servername: string;
  database_name: string;
  technology: string;
  db_username?: string;
}

interface MaskingRule {
  table_name: string;
  column_name: string;
  masking_type: string;
  is_active: boolean;
}

const Admin: React.FC = () => {
  // Navigation & Tab state
  const [activeTab, setActiveTab] = useState<'approvals' | 'masking'>('approvals');

  // --- Query Approvals State ---
  const [queries, setQueries] = useState<PendingQuery[]>([]);
  const [selectedQuery, setSelectedQuery] = useState<PendingQuery | null>(null);
  const [previewData, setPreviewData] = useState<any[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // --- Databases & Masking State ---
  const [databases, setDatabases] = useState<Database[]>([]);
  const [selectedDb, setSelectedDb] = useState<Database | null>(null);
  const [loadingDbs, setLoadingDbs] = useState(false);
  const [savingRules, setSavingRules] = useState(false);
  const [loadingSchema, setLoadingSchema] = useState(false);

  // Add Database Form State
  const [dbForm, setDbForm] = useState({
    servername: '',
    database_name: '',
    technology: 'mssql'
  });
  const [addingDb, setAddingDb] = useState(false);
  const [generatedCreds, setGeneratedCreds] = useState<{ username: string; password: string } | null>(null);

  // Schema Discovery & Masking Rules State
  const [schema, setSchema] = useState<Record<string, string[]>>({});
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
  const [maskedColumns, setMaskedColumns] = useState<Set<string>>(new Set()); // Formatted as "table_name.column_name"

  useEffect(() => {
    // Initialize AceEditor config
    const ace = (window as any).ace;
    if (ace) {
      ace.config.set('basePath', 'https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.12/');
    }
    fetchPending();
    fetchDatabases();
  }, []);

  // Fetch pending queries for approvals
  const fetchPending = async () => {
    const res = await authenticatedFetch('/api/admin/queries_to_approve');
    if (res?.ok) {
      const data = await res.json();
      setQueries(data.waiting_approvals || []);
    }
  };

  // Fetch registered databases
  const fetchDatabases = async () => {
    setLoadingDbs(true);
    const res = await authenticatedFetch('/api/admin/databases');
    if (res?.ok) {
      const data = await res.json();
      setDatabases(data.databases || []);
    }
    setLoadingDbs(false);
  };

  // Run preview execution for a selected query
  const runPreview = async () => {
    if (!selectedQuery) return;
    setLoadingPreview(true);
    try {
      const res = await authenticatedFetch(`/api/admin/execute_for_preview/${selectedQuery.workspace_id}`, { method: 'POST' });
      if (res?.ok) {
        const data = await res.json();
        setPreviewData(data.data || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingPreview(false);
    }
  };

  // Handle query approval or rejection
  const handleDecision = async (approved: boolean, executable: boolean = false) => {
    if (!selectedQuery) return;
    const url = approved 
      ? `/api/admin/approve_query/${selectedQuery.workspace_id}`
      : `/api/admin/reject_query/${selectedQuery.workspace_id}`;
    
    const body = approved ? JSON.stringify({ show_results: executable }) : undefined;
    
    const res = await authenticatedFetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body
    });

    if (res?.ok) {
      setSelectedQuery(null);
      setPreviewData([]);
      fetchPending();
    }
  };

  // Add a new database to the system and generate secure access credentials
  const handleAddDatabase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dbForm.servername || !dbForm.database_name) return;
    setAddingDb(true);
    try {
      const res = await authenticatedFetch('/api/admin/add_database', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          servername: dbForm.servername,
          database_name: dbForm.database_name,
          tech_name: dbForm.technology
        })
      });
      if (res?.ok) {
        const data = await res.json();
        // Set the generated credentials to show in the success modal
        setGeneratedCreds({
          username: data.db_username,
          password: data.db_password
        });
        setDbForm({ servername: '', database_name: '', technology: 'mssql' });
        fetchDatabases();
      } else {
        const errData = await res?.json();
        alert(errData?.detail || "Failed to add database.");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setAddingDb(false);
    }
  };

  // Select a database to load its schema and masking rules
  const handleSelectDatabase = async (db: Database) => {
    setSelectedDb(db);
    setSchema({});
    setMaskedColumns(new Set());
    setExpandedTables({});
    
    // Load schema & masking rules in parallel
    await Promise.all([
      discoverSchema(db.id),
      loadMaskingRules(db.id)
    ]);
  };

  // Discover tables & columns for a database
  const discoverSchema = async (dbId: number) => {
    setLoadingSchema(true);
    try {
      const res = await authenticatedFetch(`/api/admin/databases/${dbId}/discover_schema`);
      if (res?.ok) {
        const data = await res.json();
        setSchema(data || {});
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSchema(false);
    }
  };

  // Load persistent masking rules for a database
  const loadMaskingRules = async (dbId: number) => {
    try {
      const res = await authenticatedFetch(`/api/admin/databases/${dbId}/masking_rules`);
      if (res?.ok) {
        const rules: MaskingRule[] = await res.json();
        const masked = new Set<string>();
        rules.forEach(r => {
          if (r.is_active) {
            masked.add(`${r.table_name.toLowerCase()}.${r.column_name.toLowerCase()}`);
          }
        });
        setMaskedColumns(masked);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Toggle active masking rule on a specific table/column
  const handleToggleMasking = (tableName: string, columnName: string) => {
    const key = `${tableName.toLowerCase()}.` + `${columnName.toLowerCase()}`;
    const newMasked = new Set(maskedColumns);
    if (newMasked.has(key)) {
      newMasked.delete(key);
    } else {
      newMasked.add(key);
    }
    setMaskedColumns(newMasked);
  };

  // Save masking rules to backend
  const handleSaveMaskingRules = async () => {
    if (!selectedDb) return;
    setSavingRules(true);
    
    const rulesList: MaskingRule[] = [];
    Object.keys(schema).forEach(tableName => {
      schema[tableName].forEach(columnName => {
        const key = `${tableName.toLowerCase()}.${columnName.toLowerCase()}`;
        if (maskedColumns.has(key)) {
          rulesList.push({
            table_name: tableName,
            column_name: columnName,
            masking_type: 'default',
            is_active: true
          });
        }
      });
    });

    try {
      const res = await authenticatedFetch(`/api/admin/databases/${selectedDb.id}/masking_rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules: rulesList })
      });
      if (res?.ok) {
        alert("Masking rules updated successfully.");
      } else {
        alert("Failed to save masking rules.");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSavingRules(false);
    }
  };

  const toggleTableExpand = (tableName: string) => {
    setExpandedTables(prev => ({
      ...prev,
      [tableName]: !prev[tableName]
    }));
  };

  // Custom helper to safety lowercase
  const safetyLower = (val: string) => val ? val.toLowerCase() : '';

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Premium Dashboard Header with Sub-header Navigation */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-800 pb-5 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Yönetim Paneli</h1>
          <p className="text-sm text-gray-400 mt-1">Sorgu onayları, veritabanı bağlantıları ve veri maskeleme konfigürasyonları.</p>
        </div>
        
        {/* Modern Switcher Tabs */}
        <div className="flex bg-gray-900/80 border border-gray-800 p-1 rounded-xl mt-4 md:mt-0 shadow-inner">
          <button 
            onClick={() => setActiveTab('approvals')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
              activeTab === 'approvals' 
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Sorgu Onayları
            {queries.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs font-bold bg-red-500 text-white rounded-full leading-none animate-pulse">
                {queries.length}
              </span>
            )}
          </button>
          <button 
            onClick={() => setActiveTab('masking')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
              activeTab === 'masking' 
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            Veritabanı & Maskeleme
          </button>
        </div>
      </div>

      {/* ==================== TAB: QUERY APPROVALS ==================== */}
      {activeTab === 'approvals' && (
        <div>
          {queries.length === 0 ? (
            <div className="bg-gray-850 border border-gray-800 p-16 rounded-2xl text-center shadow-xl">
              <div className="inline-flex p-4 rounded-full bg-gray-800 text-indigo-400 mb-4">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white">Bekleyen Sorgu Bulunmuyor</h3>
              <p className="text-gray-400 text-sm mt-1 max-w-sm mx-auto">Tüm riskli sorgu analiz talepleri karara bağlanmış durumda.</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {queries.map(q => (
                <div key={q.workspace_id} className="bg-gray-850 border border-gray-800 hover:border-gray-700 rounded-xl p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 transition duration-200 shadow-md">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2.5">
                      <span className="font-semibold text-white text-lg">{q.username}</span>
                      <span className="text-xs font-medium bg-amber-900/40 text-amber-300 border border-amber-800/60 px-2.5 py-0.5 rounded-full">
                        {q.status === 'waiting_for_approval' ? 'Onay Bekliyor' : q.status}
                      </span>
                      {q.risk_type && (
                        <span className="text-xs font-medium bg-red-950/55 text-red-300 border border-red-850 px-2.5 py-0.5 rounded-full">
                          {q.risk_type} Riski
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-400 flex items-center gap-2 mb-3">
                      <span className="font-medium text-gray-300">{q.servername}</span>
                      <span className="text-gray-600">&bull;</span>
                      <span className="font-medium text-gray-300">{q.database}</span>
                    </div>
                    <div className="bg-gray-900/90 border border-gray-800/80 p-3.5 rounded-lg font-mono text-xs text-gray-300 max-w-4xl overflow-hidden text-ellipsis whitespace-nowrap">
                      {q.query}
                    </div>
                  </div>
                  <button 
                    onClick={() => {
                      setSelectedQuery(q);
                      setPreviewData([]);
                    }}
                    className="w-full md:w-auto bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-indigo-600/10 flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                    İncele
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ==================== TAB: DATABASE & MASKING ==================== */}
      {activeTab === 'masking' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column: DB Registration & DB List */}
          <div className="lg:col-span-5 flex flex-col gap-6">
            
            {/* Database Registration Form */}
            <div className="bg-gray-850 border border-gray-800 rounded-2xl p-6 shadow-md">
              <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-4 border-b border-gray-800 pb-3">
                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Yeni Veritabanı Ekle
              </h2>
              
              <form onSubmit={handleAddDatabase} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Sunucu Adresi (Host)</label>
                  <input 
                    type="text"
                    required
                    placeholder="örn. localhost veya 10.0.0.5"
                    value={dbForm.servername}
                    onChange={e => setDbForm({ ...dbForm, servername: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-800 hover:border-gray-700 focus:border-indigo-600 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Veritabanı Adı</label>
                    <input 
                      type="text"
                      required
                      placeholder="örn. Northwind"
                      value={dbForm.database_name}
                      onChange={e => setDbForm({ ...dbForm, database_name: e.target.value })}
                      className="w-full bg-gray-900 border border-gray-800 hover:border-gray-700 focus:border-indigo-600 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Teknoloji</label>
                    <select
                      value={dbForm.technology}
                      onChange={e => setDbForm({ ...dbForm, technology: e.target.value })}
                      className="w-full bg-gray-900 border border-gray-800 hover:border-gray-700 focus:border-indigo-600 rounded-lg px-3 py-2.5 text-sm text-white outline-none transition"
                    >
                      <option value="mssql">MS SQL Server</option>
                      <option value="postgresql">PostgreSQL</option>
                      <option value="mysql">MySQL</option>
                    </select>
                  </div>
                </div>

                <button 
                  type="submit"
                  disabled={addingDb}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-800 text-white font-semibold py-2.5 rounded-lg text-sm transition shadow-md shadow-indigo-600/10 mt-2"
                >
                  {addingDb ? 'Veritabanı Ekleniyor...' : 'Ekle & Güvenli Kullanıcı Üret'}
                </button>
              </form>
            </div>

            {/* Database List */}
            <div className="bg-gray-850 border border-gray-800 rounded-2xl p-6 shadow-md flex-1">
              <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-4 border-b border-gray-800 pb-3">
                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.58 4 8 4s8-1.79 8-4M4 7c0-2.21 3.58-4 8-4s8 1.79 8 4m0 5c0 2.21-3.58 4-8 4s-8-1.79-8-4" />
                </svg>
                Kayıtlı Veritabanları
              </h2>

              {loadingDbs ? (
                <div className="text-center py-8 text-gray-500 text-sm">Veritabanları yükleniyor...</div>
              ) : databases.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-sm">Henüz kayıtlı veritabanı bulunmuyor.</div>
              ) : (
                <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
                  {databases.map(db => (
                    <button
                      key={db.id}
                      onClick={() => handleSelectDatabase(db)}
                      className={`w-full text-left p-3 rounded-xl border transition duration-150 flex justify-between items-center ${
                        selectedDb?.id === db.id 
                          ? 'bg-indigo-900/30 border-indigo-700 text-white' 
                          : 'bg-gray-900/60 border-gray-800 hover:border-gray-700 text-gray-300 hover:text-white'
                      }`}
                    >
                      <div>
                        <div className="font-semibold text-sm">{db.database_name}</div>
                        <div className="text-xs text-gray-400 mt-0.5">{db.servername} &bull; {db.technology.toUpperCase()}</div>
                      </div>
                      <svg className={`w-4.5 h-4.5 transition-transform duration-200 ${selectedDb?.id === db.id ? 'text-indigo-400 transform translate-x-0.5' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                  ))}
                </div>
              )}
            </div>

          </div>

          {/* Right Column: Schema TreeView & Masking Rules */}
          <div className="lg:col-span-7">
            {selectedDb ? (
              <div className="bg-gray-850 border border-gray-800 rounded-2xl p-6 shadow-md h-full flex flex-col">
                
                {/* Panel Header */}
                <div className="flex flex-wrap justify-between items-center border-b border-gray-800 pb-4 mb-4 gap-4">
                  <div>
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                      <span className="text-indigo-400">#</span>
                      {selectedDb.database_name} Maskeleme Kuralları
                    </h2>
                    <p className="text-xs text-gray-400 mt-0.5">{selectedDb.servername} sunucusundaki aktif şema kolonları.</p>
                  </div>
                  
                  <button 
                    onClick={() => discoverSchema(selectedDb.id)}
                    disabled={loadingSchema}
                    className="bg-gray-800 hover:bg-gray-700 disabled:bg-gray-850 text-xs font-semibold text-gray-300 hover:text-white px-3 py-2 rounded-lg border border-gray-700 transition flex items-center gap-1.5"
                  >
                    <svg className={`w-3.5 h-3.5 ${loadingSchema ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
                    </svg>
                    Şemayı Yenile
                  </button>
                </div>

                {/* Schema TreeView Container */}
                <div className="flex-1 min-h-[380px] max-h-[480px] overflow-y-auto bg-gray-900/65 border border-gray-800/80 rounded-xl p-4">
                  {loadingSchema ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-2">
                      <svg className="w-8 h-8 text-indigo-500 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span className="text-sm font-medium">Veritabanı şeması taranıyor...</span>
                    </div>
                  ) : Object.keys(schema).length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-500 text-sm text-center px-6">
                      <svg className="w-10 h-10 text-gray-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      Bu veritabanına ait tablo bilgisi bulunamadı veya bağlantı kurulamadı. Lütfen sunucu ayarlarını ve ağ erişimini kontrol edin.
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {Object.keys(schema).map(tableName => {
                        const isExpanded = !!expandedTables[tableName];
                        const columns = schema[tableName];
                        return (
                          <div key={tableName} className="border border-gray-800/60 rounded-lg overflow-hidden bg-gray-950/40">
                            {/* Table Node */}
                            <button
                              onClick={() => toggleTableExpand(tableName)}
                              className="w-full flex items-center justify-between p-3 hover:bg-gray-800/25 transition text-left"
                            >
                              <div className="flex items-center gap-2">
                                <svg className={`w-4 h-4 text-gray-400 transition-transform duration-150 ${isExpanded ? 'transform rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                                </svg>
                                <svg className="w-4 h-4 text-indigo-400/80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                                <span className="font-semibold text-sm text-gray-200">{tableName}</span>
                              </div>
                              <span className="text-xs text-indigo-400/85 font-semibold bg-indigo-950/40 px-2 py-0.5 rounded-full">
                                {columns.length} Kolon
                              </span>
                            </button>

                            {/* Column Leaf Nodes (Expanded) */}
                            {isExpanded && (
                              <div className="border-t border-gray-900 bg-gray-950/80 px-4 py-2 space-y-1.5 pl-9">
                                {columns.map(col => {
                                  const isMasked = maskedColumns.has(`${tableName.toLowerCase()}.${col.toLowerCase()}`);
                                  return (
                                    <div 
                                      key={col} 
                                      onClick={() => handleToggleMasking(tableName, col)}
                                      className="flex items-center justify-between py-1.5 hover:bg-gray-900/40 rounded px-2 cursor-pointer select-none"
                                    >
                                      <span className="text-xs text-gray-300 font-mono">{col}</span>
                                      <div className="flex items-center gap-2">
                                        {isMasked && (
                                          <span className="text-[10px] uppercase font-bold bg-amber-950/50 text-amber-400 border border-amber-800/40 px-1.5 py-0.2 rounded">
                                            Maskeli
                                          </span>
                                        )}
                                        <input 
                                          type="checkbox" 
                                          checked={isMasked}
                                          onChange={() => {}} // Handled by div onClick
                                          className="w-4 h-4 rounded text-indigo-600 bg-gray-900 border-gray-700 focus:ring-indigo-600 focus:ring-offset-gray-900"
                                        />
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Save Rules Button */}
                <div className="mt-5 border-t border-gray-800 pt-4 flex justify-between items-center">
                  <span className="text-xs text-gray-400 font-medium">
                    Toplam <span className="text-amber-400 font-bold">{maskedColumns.size}</span> kolon maskelenmek üzere seçildi.
                  </span>
                  <button 
                    onClick={handleSaveMaskingRules}
                    disabled={savingRules || loadingSchema}
                    className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-800 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition shadow-md shadow-indigo-600/10 flex items-center gap-2"
                  >
                    {savingRules ? (
                      <>
                        <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
                        </svg>
                        Kaydediliyor...
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                        </svg>
                        Kuralları Kaydet
                      </>
                    )}
                  </button>
                </div>

              </div>
            ) : (
              <div className="bg-gray-850 border border-gray-800 p-16 rounded-2xl text-center shadow-xl h-full flex flex-col items-center justify-center">
                <div className="p-4 rounded-full bg-gray-800 text-indigo-400 mb-4">
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold text-white">Maskeleme Yönetimi</h3>
                <p className="text-gray-400 text-sm mt-1 max-w-xs mx-auto">Sol paneldeki kayıtlı veritabanlarından birini seçerek aktif şema kolonları üzerinde maskeleme kuralları tanımlayabilirsiniz.</p>
              </div>
            )}
          </div>

        </div>
      )}

      {/* ==================== MODAL: GENERATED CREDENTIALS ==================== */}
      {generatedCreds && (
        <Modal 
          isOpen={true} 
          onClose={() => setGeneratedCreds(null)} 
          title="Veritabanı Erişim Bilgileri" 
          size="md"
        >
          <div className="space-y-4">
            <div className="bg-amber-950/40 border border-amber-900/50 p-4 rounded-xl flex gap-3">
              <svg className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <h4 className="text-xs font-bold text-amber-300 uppercase">Önemli Güvenlik Uyarısı</h4>
                <p className="text-xs text-amber-400/90 mt-1 leading-relaxed">
                  WebQuery, bu veritabanına erişmek için aşağıdaki benzersiz servis hesabı kimlik bilgilerini üretmiştir. Şifre sadece <strong>bir kez</strong> gösterilecektir. Lütfen bilgileri güvenli bir yere kaydedin.
                </p>
              </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3 font-mono text-xs">
              <div className="flex justify-between items-center">
                <span className="text-gray-400 uppercase font-bold text-[10px]">Üretilen Kullanıcı Adı:</span>
                <span className="text-indigo-300 font-semibold select-all">{generatedCreds.username}</span>
              </div>
              <div className="border-t border-gray-800/50 pt-2.5 flex justify-between items-center">
                <span className="text-gray-400 uppercase font-bold text-[10px]">Üretilen Şifre:</span>
                <span className="text-indigo-300 font-semibold select-all">{generatedCreds.password}</span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button 
                onClick={() => {
                  navigator.clipboard.writeText(`Username: ${generatedCreds.username}\nPassword: ${generatedCreds.password}`);
                  alert("Credentials copied to clipboard.");
                  setGeneratedCreds(null);
                }}
                className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition flex items-center gap-1.5"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                </svg>
                Kopyala & Kapat
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ==================== MODAL: REVIEW QUERY ==================== */}
      {selectedQuery && (
        <Modal 
          isOpen={true} 
          onClose={() => setSelectedQuery(null)} 
          title="Sorgu Talebi İncelemesi" 
          size="xl"
        >
          <div className="flex flex-col gap-5">
            
            {/* Metadata Summary Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-gray-900 border border-gray-800 p-4 rounded-xl text-xs font-medium">
              <div>
                <span className="text-gray-400 block mb-0.5">Kullanıcı:</span>
                <span className="text-white text-sm font-bold">{selectedQuery.username}</span>
              </div>
              <div>
                <span className="text-gray-400 block mb-0.5">Sunucu:</span>
                <span className="text-white text-sm font-semibold">{selectedQuery.servername}</span>
              </div>
              <div>
                <span className="text-gray-400 block mb-0.5">Veritabanı:</span>
                <span className="text-white text-sm font-semibold">{selectedQuery.database}</span>
              </div>
              <div>
                <span className="text-gray-400 block mb-0.5">Risk Seviyesi:</span>
                <span className={`text-sm font-bold ${selectedQuery.risk_type ? 'text-red-400' : 'text-emerald-400'}`}>
                  {selectedQuery.risk_type || 'Yok'}
                </span>
              </div>
            </div>

            {/* SQL Query Editor Preview */}
            <div>
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5 block">SQL Sorgusu</label>
              <div className="border border-gray-800 rounded-xl overflow-hidden">
                <AceEditor value={selectedQuery.query} readOnly={true} height="220px" />
              </div>
            </div>

            {/* Result Preview Panel */}
            <div className="border-t border-gray-800 pt-5">
              <div className="flex justify-between items-center mb-3">
                <h4 className="text-xs font-bold uppercase text-gray-400 tracking-wider">Sonuç Önizleme</h4>
                <button 
                  onClick={runPreview} 
                  disabled={loadingPreview} 
                  className="bg-gray-850 hover:bg-gray-800 border border-gray-700 disabled:bg-gray-900 text-xs font-semibold text-white px-3.5 py-1.5 rounded-lg transition flex items-center gap-1"
                >
                  {loadingPreview ? (
                    <>
                      <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
                      </svg>
                      Çalıştırılıyor...
                    </>
                  ) : (
                    <>
                      <svg className="w-3 h-3 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Önizleme Çalıştır
                    </>
                  )}
                </button>
              </div>

              <div className="bg-gray-900 border border-gray-800 rounded-xl h-48 overflow-auto">
                {previewData.length > 0 ? (
                  <table className="w-full text-xs text-left border-collapse">
                    <thead className="bg-gray-850 text-gray-300 border-b border-gray-800 sticky top-0">
                      <tr>
                        {Object.keys(previewData[0]).map(k => (
                          <th key={k} className="p-3 font-semibold border-r border-gray-800 last:border-0">{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800/60">
                      {previewData.map((r, i) => (
                        <tr key={i} className="hover:bg-gray-850/30 text-gray-300 transition duration-100">
                          {Object.values(r).map((v: any, j) => (
                            <td key={j} className="p-3 border-r border-gray-800/40 last:border-0 font-mono whitespace-nowrap overflow-hidden text-ellipsis max-w-[200px]">
                              {String(v)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-500 text-xs">
                    Önizleme verilerini görüntülemek için yukarıdaki 'Önizleme Çalıştır' butonuna basın.
                  </div>
                )}
              </div>
            </div>

            {/* Action Decision Buttons */}
            <div className="flex flex-wrap justify-end gap-3 pt-3 border-t border-gray-800 mt-2">
              <button 
                onClick={() => handleDecision(false)} 
                className="bg-red-650 hover:bg-red-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-red-900/10"
              >
                Reddet
              </button>
              <button 
                onClick={() => handleDecision(true, false)} 
                className="bg-amber-600 hover:bg-amber-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-amber-700/10"
              >
                Onayla (Gözlem Modu)
              </button>
              <button 
                onClick={() => handleDecision(true, true)} 
                className="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-emerald-700/10"
              >
                Onayla & Çalıştırılabilir Yap
              </button>
            </div>

          </div>
        </Modal>
      )}

    </div>
  );
};

export default Admin;

```
</details>




### 📂 Kategori 8: Kapsamlı Entegrasyon ve Güvenlik Testleri (Testing Infrastructure)
---

#### <a name="web_apitestsconftestpy"></a> `web_api/tests/conftest.py`
**Açıklama:** Testler için asenkron SQLite in-memory veritabanı (`sqlite+aiosqlite:///:memory:`) kuran, mock veri sağlayıcılarını başlatan ve asenkron HTTP istemcisi sunan pytest yapılandırma modülü.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/tests/conftest.py b/web_api/tests/conftest.py
index bd2ebc7..9ec068d 100644
--- a/web_api/tests/conftest.py
+++ b/web_api/tests/conftest.py
@@ -15,8 +15,6 @@ pytestmark = pytest.mark.asyncio
 
 import pytest_asyncio
 from app_database import AppDatabase
-from cryptography.fernet import Fernet
-from session import SessionCache
 from database_provider import DatabaseProvider
 
 @pytest_asyncio.fixture
@@ -30,13 +28,11 @@ async def async_client():
     await app.state.app_db.create_tables()
     
     app.state.db_provider = DatabaseProvider()
-    app.state.fernet = Fernet(Fernet.generate_key())
-    import fakeredis
-    fake_redis = fakeredis.FakeRedis()
+    await app.state.db_provider.start_cache_loop()
     
-    # We monkeypatch the session cache's redis client
-    app.state.session_cache = SessionCache(fernet=app.state.fernet)
-    app.state.session_cache.client = fake_redis
+    # Disable rate limiter for testing to prevent 429 Too Many Requests
+    if hasattr(app.state, "limiter"):
+        app.state.limiter.enabled = False
     
     transport = ASGITransport(app=app)
     async with AsyncClient(transport=transport, base_url="http://test") as client:
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (conftest.py)</summary>

```python
import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os
# Mock APP_DATABASE_URL before any app modules are imported
os.environ["APP_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Add the web_api directory to sys.path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app

# Mark all async tests to use asyncio automatically
pytestmark = pytest.mark.asyncio

import pytest_asyncio
from app_database import AppDatabase
from database_provider import DatabaseProvider

@pytest_asyncio.fixture
async def async_client():
    """
    Fixture for providing an asynchronous HTTP client that bypasses the actual network
    and directly calls the ASGI application.
    """
    # Manually setup state for testing
    app.state.app_db = AppDatabase()
    await app.state.app_db.create_tables()
    
    app.state.db_provider = DatabaseProvider()
    await app.state.db_provider.start_cache_loop()
    
    # Disable rate limiter for testing to prevent 429 Too Many Requests
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

```
</details>



#### <a name="web_apitestsintegrationtest_auth_apipy"></a> `web_api/tests/integration/test_auth_api.py`
**Açıklama:** Yeni durumsuz cookie tabanlı kimlik doğrulama akışını, kayıt, giriş ve çıkış işlemlerini entegrasyon testleriyle doğrulayan test modülü.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/tests/integration/test_auth_api.py b/web_api/tests/integration/test_auth_api.py
index f919eab..7405530 100644
--- a/web_api/tests/integration/test_auth_api.py
+++ b/web_api/tests/integration/test_auth_api.py
@@ -1,11 +1,17 @@
+"""
+Integration tests for User Authentication, Registration, and Session management.
+Includes rate limiting bypass, password policy validations, JWT cookie handling,
+and clean engine shutdowns upon logout.
+"""
 import pytest
-import httpx
+from unittest.mock import AsyncMock, patch
 from httpx import AsyncClient
+from app import app
 
 @pytest.mark.asyncio
 async def test_register_and_login(async_client: AsyncClient):
     """
-    Test user registration and subsequent login.
+    Test successful user registration and subsequent login setting cookies.
     """
     # 1. Register a new user
     register_data = {
@@ -32,12 +38,182 @@ async def test_register_and_login(async_client: AsyncClient):
     data = response.json()
     assert "access_token" in data
     assert data["token_type"] == "bearer"
+    
+    # Verify cookie is set in response headers
+    assert "access_token" in response.cookies
+    cookie = response.cookies["access_token"]
+    assert cookie is not None
+
+
+@pytest.mark.asyncio
+async def test_login_invalid_credentials(async_client: AsyncClient):
+    """
+    Test login failures with non-existent user and incorrect password.
+    """
+    # 1. Login with unregistered user
+    login_data = {
+        "email": "nonexistent@example.com",
+        "password": "StrongPassword123!"
+    }
+    response = await async_client.post("/api/login", json=login_data)
+    assert response.status_code == 400
+    assert "Invalid email or password" in response.text
+
+    # 2. Register a user
+    register_data = {
+        "username": "auth_user",
+        "email": "auth_user@example.com",
+        "password": "StrongPassword123!"
+    }
+    response = await async_client.post("/api/register", json=register_data)
+    assert response.status_code == 200
+
+    # 3. Login with incorrect password
+    bad_login_data = {
+        "email": "auth_user@example.com",
+        "password": "WrongPassword999!"
+    }
+    response = await async_client.post("/api/login", json=bad_login_data)
+    assert response.status_code == 400
+    assert "Invalid email or password" in response.text
+
+
+@pytest.mark.asyncio
+async def test_register_duplicate_email(async_client: AsyncClient):
+    """
+    Test that registering an email already in use yields a 400 bad request.
+    """
+    register_data = {
+        "username": "dup_user1",
+        "email": "duplicate@example.com",
+        "password": "StrongPassword123!"
+    }
+    
+    response = await async_client.post("/api/register", json=register_data)
+    assert response.status_code == 200
+
+    # Attempt second registration with same email
+    register_data_2 = {
+        "username": "dup_user2",
+        "email": "duplicate@example.com",
+        "password": "DifferentPassword123!"
+    }
+    response = await async_client.post("/api/register", json=register_data_2)
+    assert response.status_code == 400
+    data = response.json()
+    assert data["error_code"] == "USER_ALREADY_EXISTS"
+    assert "Email already registered" in data["message"]
+
+
+@pytest.mark.asyncio
+async def test_register_invalid_password(async_client: AsyncClient):
+    """
+    Test that registration rejects passwords violating the security policy.
+    """
+    # 1. Short password
+    register_data = {
+        "username": "weak_user1",
+        "email": "weak1@example.com",
+        "password": "Short1!"
+    }
+    response = await async_client.post("/api/register", json=register_data)
+    assert response.status_code == 400
+    assert "Şifre en az 12 karakter olmalıdır" in response.json()["detail"]
+
+    # 2. No uppercase or numbers
+    register_data_2 = {
+        "username": "weak_user2",
+        "email": "weak2@example.com",
+        "password": "lowercaseonly!"
+    }
+    response = await async_client.post("/api/register", json=register_data_2)
+    assert response.status_code == 400
+    assert "Şifre en az bir büyük harf ve bir rakam içermelidir" in response.json()["detail"]
+
 
 @pytest.mark.asyncio
 async def test_access_protected_route_without_token(async_client: AsyncClient):
     """
-    Test that accessing a protected API route without a token returns 401.
+    Test that accessing protected endpoints without access_token cookie returns 401.
     """
     response = await async_client.get("/api/workspaces")
-    # Our middleware returns 401 for /api/ routes when no token is present
     assert response.status_code == 401
+    assert "Token required" in response.text
+
+
+@pytest.mark.asyncio
+async def test_access_me_protected_route(async_client: AsyncClient):
+    """
+    Test that logged in user can successfully retrieve their profile via /api/me.
+    """
+    # 1. Register and login
+    register_data = {
+        "username": "profile_user",
+        "email": "profile@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/register", json=register_data)
+    
+    login_data = {
+        "email": "profile@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/login", json=login_data)
+
+    # 2. Retrieve user details
+    response = await async_client.get("/api/me")
+    assert response.status_code == 200
+    data = response.json()
+    assert data["username"] == "profile_user"
+    assert data["is_admin"] is False
+
+
+@pytest.mark.asyncio
+async def test_access_me_invalid_token(async_client: AsyncClient):
+    """
+    Test that profile retrieval returns 401 when access_token cookie is corrupted/invalid.
+    """
+    async_client.cookies.set("access_token", "invalid_jwt_token_format_xxxx")
+    response = await async_client.get("/api/me")
+    assert response.status_code == 401
+    assert "Invalid token" in response.json()["detail"]
+
+
+@pytest.mark.asyncio
+async def test_logout_flow(async_client: AsyncClient):
+    """
+    Test complete logout flow: clears cookie, logs session update, and closes user DB engines.
+    """
+    # 1. Register and login
+    register_data = {
+        "username": "logout_user",
+        "email": "logout@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/register", json=register_data)
+    
+    login_data = {
+        "email": "logout@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/login", json=login_data)
+
+    # Verify cookies contain token
+    assert "access_token" in async_client.cookies
+
+    # 2. Mock db_provider.close_user_engines
+    db_provider = app.state.db_provider
+    with patch.object(db_provider, "close_user_engines", new_callable=AsyncMock) as mock_close:
+        # 3. Perform logout
+        response = await async_client.post("/api/logout")
+        assert response.status_code == 200
+        assert "Successfully logged out" in response.json()["message"]
+
+        # 4. Verify cookie was deleted
+        # Note: In HTTP clients, deleting a cookie sets it to empty or expires it immediately
+        assert "access_token" not in async_client.cookies or async_client.cookies.get("access_token") == ""
+
+        # 5. Verify close_user_engines was called
+        mock_close.assert_called_once()
+        called_user_id = mock_close.call_args[0][0]
+        assert isinstance(called_user_id, int)
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (test_auth_api.py)</summary>

```python
"""
Integration tests for User Authentication, Registration, and Session management.
Includes rate limiting bypass, password policy validations, JWT cookie handling,
and clean engine shutdowns upon logout.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from app import app

@pytest.mark.asyncio
async def test_register_and_login(async_client: AsyncClient):
    """
    Test successful user registration and subsequent login setting cookies.
    """
    # 1. Register a new user
    register_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "StrongPassword123!"
    }
    
    response = await async_client.post("/api/register", json=register_data)
    assert response.status_code == 200, f"Registration failed: {response.text}"
    
    data = response.json()
    assert data["success"] is True
    
    # 2. Login with the created user
    login_data = {
        "email": "test@example.com",
        "password": "StrongPassword123!"
    }
    
    response = await async_client.post("/api/login", json=login_data)
    assert response.status_code == 200, f"Login failed: {response.text}"
    
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    # Verify cookie is set in response headers
    assert "access_token" in response.cookies
    cookie = response.cookies["access_token"]
    assert cookie is not None


@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client: AsyncClient):
    """
    Test login failures with non-existent user and incorrect password.
    """
    # 1. Login with unregistered user
    login_data = {
        "email": "nonexistent@example.com",
        "password": "StrongPassword123!"
    }
    response = await async_client.post("/api/login", json=login_data)
    assert response.status_code == 400
    assert "Invalid email or password" in response.text

    # 2. Register a user
    register_data = {
        "username": "auth_user",
        "email": "auth_user@example.com",
        "password": "StrongPassword123!"
    }
    response = await async_client.post("/api/register", json=register_data)
    assert response.status_code == 200

    # 3. Login with incorrect password
    bad_login_data = {
        "email": "auth_user@example.com",
        "password": "WrongPassword999!"
    }
    response = await async_client.post("/api/login", json=bad_login_data)
    assert response.status_code == 400
    assert "Invalid email or password" in response.text


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    """
    Test that registering an email already in use yields a 400 bad request.
    """
    register_data = {
        "username": "dup_user1",
        "email": "duplicate@example.com",
        "password": "StrongPassword123!"
    }
    
    response = await async_client.post("/api/register", json=register_data)
    assert response.status_code == 200

    # Attempt second registration with same email
    register_data_2 = {
        "username": "dup_user2",
        "email": "duplicate@example.com",
        "password": "DifferentPassword123!"
    }
    response = await async_client.post("/api/register", json=register_data_2)
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "USER_ALREADY_EXISTS"
    assert "Email already registered" in data["message"]


@pytest.mark.asyncio
async def test_register_invalid_password(async_client: AsyncClient):
    """
    Test that registration rejects passwords violating the security policy.
    """
    # 1. Short password
    register_data = {
        "username": "weak_user1",
        "email": "weak1@example.com",
        "password": "Short1!"
    }
    response = await async_client.post("/api/register", json=register_data)
    assert response.status_code == 400
    assert "Şifre en az 12 karakter olmalıdır" in response.json()["detail"]

    # 2. No uppercase or numbers
    register_data_2 = {
        "username": "weak_user2",
        "email": "weak2@example.com",
        "password": "lowercaseonly!"
    }
    response = await async_client.post("/api/register", json=register_data_2)
    assert response.status_code == 400
    assert "Şifre en az bir büyük harf ve bir rakam içermelidir" in response.json()["detail"]


@pytest.mark.asyncio
async def test_access_protected_route_without_token(async_client: AsyncClient):
    """
    Test that accessing protected endpoints without access_token cookie returns 401.
    """
    response = await async_client.get("/api/workspaces")
    assert response.status_code == 401
    assert "Token required" in response.text


@pytest.mark.asyncio
async def test_access_me_protected_route(async_client: AsyncClient):
    """
    Test that logged in user can successfully retrieve their profile via /api/me.
    """
    # 1. Register and login
    register_data = {
        "username": "profile_user",
        "email": "profile@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "profile@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)

    # 2. Retrieve user details
    response = await async_client.get("/api/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "profile_user"
    assert data["is_admin"] is False


@pytest.mark.asyncio
async def test_access_me_invalid_token(async_client: AsyncClient):
    """
    Test that profile retrieval returns 401 when access_token cookie is corrupted/invalid.
    """
    async_client.cookies.set("access_token", "invalid_jwt_token_format_xxxx")
    response = await async_client.get("/api/me")
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_logout_flow(async_client: AsyncClient):
    """
    Test complete logout flow: clears cookie, logs session update, and closes user DB engines.
    """
    # 1. Register and login
    register_data = {
        "username": "logout_user",
        "email": "logout@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "logout@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)

    # Verify cookies contain token
    assert "access_token" in async_client.cookies

    # 2. Mock db_provider.close_user_engines
    db_provider = app.state.db_provider
    with patch.object(db_provider, "close_user_engines", new_callable=AsyncMock) as mock_close:
        # 3. Perform logout
        response = await async_client.post("/api/logout")
        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]

        # 4. Verify cookie was deleted
        # Note: In HTTP clients, deleting a cookie sets it to empty or expires it immediately
        assert "access_token" not in async_client.cookies or async_client.cookies.get("access_token") == ""

        # 5. Verify close_user_engines was called
        mock_close.assert_called_once()
        called_user_id = mock_close.call_args[0][0]
        assert isinstance(called_user_id, int)

```
</details>



#### <a name="web_apitestsintegrationtest_admin_apipy"></a> `web_api/tests/integration/test_admin_api.py`
**Açıklama:** Admin yetkilendirmelerini, veritabanı ekleme süreçlerini, riskli sorgu onaylama ve reddetme akışlarını test eden entegrasyon testleri.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/tests/integration/test_admin_api.py b/web_api/tests/integration/test_admin_api.py
new file mode 100644
index 0000000..8d6ec1a
--- /dev/null
+++ b/web_api/tests/integration/test_admin_api.py
@@ -0,0 +1,245 @@
+"""
+Integration tests for admin router and service layer.
+Verifies Role-Based Access Control (RBAC), database registration, and query approval workflows.
+"""
+import pytest
+from httpx import AsyncClient
+from unittest.mock import MagicMock, AsyncMock, patch
+from contextlib import asynccontextmanager
+from sqlalchemy.future import select
+
+from app import app
+from app_database.models import User, Workspace, QueryData, Databases
+
+@pytest.fixture
+def mock_db_session():
+    """
+    Fixture that patches DatabaseProvider.get_session to return a mock session.
+    """
+    mock_session = AsyncMock()
+    mock_result = MagicMock()
+    mock_session.execute.return_value = mock_result
+    
+    @asynccontextmanager
+    async def fake_get_session(user, servername, database_name):
+        yield mock_session
+        
+    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
+        yield mock_session, mock_result
+
+
+async def create_user_and_login(async_client: AsyncClient, email: str, username: str, make_admin: bool = False) -> int:
+    """
+    Helper function to register, login, and optionally promote a user to admin.
+    """
+    register_data = {
+        "username": username,
+        "email": email,
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/register", json=register_data)
+    
+    app_db = app.state.app_db
+    user_id = 0
+    if make_admin:
+        async with app_db.get_app_db() as db:
+            result = await db.execute(select(User).where(User.email == email))
+            user = result.scalars().first()
+            user.is_admin = True
+            user_id = user.id
+            await db.commit()
+            
+    login_data = {
+        "email": email,
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/login", json=login_data)
+    
+    if not make_admin:
+        async with app_db.get_app_db() as db:
+            result = await db.execute(select(User).where(User.email == email))
+            user = result.scalars().first()
+            user_id = user.id
+            
+    return user_id
+
+
+@pytest.mark.asyncio
+async def test_admin_rbac_restrictions(async_client: AsyncClient):
+    """
+    Tests that non-admin users are blocked from accessing administrative routes.
+    """
+    # 1. Login as regular user
+    await create_user_and_login(async_client, "regular@example.com", "regular")
+    
+    # 2. Attempt to list queries waiting for approval -> should fail with 403 Forbidden
+    resp_list = await async_client.get("/api/admin/queries_to_approve")
+    assert resp_list.status_code == 403
+    assert "Admin access required" in resp_list.json()["detail"]
+    
+    # 3. Attempt to approve a query -> should fail with 403 Forbidden
+    resp_approve = await async_client.post("/api/admin/approve_query/1", json={"show_results": True})
+    assert resp_approve.status_code == 403
+    assert "Admin access required" in resp_approve.json()["detail"]
+    
+    # 4. Attempt to add a database -> should fail with 403 Forbidden
+    db_payload = {
+        "servername": "new-server",
+        "database_name": "new-db",
+        "tech_name": "mssql"
+    }
+    resp_add = await async_client.post("/api/admin/add_database", json=db_payload)
+    assert resp_add.status_code == 403
+    assert "Admin access required" in resp_add.json()["detail"]
+
+
+@pytest.mark.asyncio
+async def test_admin_database_registration(async_client: AsyncClient):
+    """
+    Tests registering databases by an admin, including duplicate checks.
+    """
+    # 1. Login as admin
+    await create_user_and_login(async_client, "admin1@example.com", "admin1", make_admin=True)
+    
+    # 2. Add database
+    db_payload = {
+        "servername": "prod-server",
+        "database_name": "orders_db",
+        "tech_name": "postgresql"
+    }
+    response = await async_client.post("/api/admin/add_database", json=db_payload)
+    assert response.status_code == 200
+    assert "added successfully" in response.json()["message"]
+    
+    # Verify database entry in metadata DB
+    app_db = app.state.app_db
+    async with app_db.get_app_db() as db:
+        result = await db.execute(select(Databases).where(Databases.database_name == "orders_db"))
+        db_entry = result.scalars().first()
+        assert db_entry is not None
+        assert db_entry.servername == "prod-server"
+        assert db_entry.technology == "postgresql"
+        
+    # 3. Attempt to add duplicate database -> should fail with 400 Bad Request
+    response_dup = await async_client.post("/api/admin/add_database", json=db_payload)
+    assert response_dup.status_code == 400
+    assert response_dup.json()["error_code"] == "DATABASE_ALREADY_EXISTS"
+    assert "already exists" in response_dup.json()["message"]
+
+
+@pytest.mark.asyncio
+async def test_admin_query_approval_workflow(async_client: AsyncClient, mock_db_session):
+    """
+    Tests query approval and rejection flows, ensuring execution permissions update correctly.
+    """
+    mock_session, mock_result = mock_db_session
+    
+    # 1. Register a regular user and create a workspace
+    regular_client = AsyncClient(transport=async_client._transport, base_url="http://test")
+    await create_user_and_login(regular_client, "user_req@example.com", "user_req")
+    
+    create_payload = {
+        "name": "Audit Workspace",
+        "query": "UPDATE items SET price = 10",
+        "servername": "prod-server",
+        "database_name": "orders_db"
+    }
+    create_response = await regular_client.post("/api/workspaces", json=create_payload)
+    workspace_id = create_response.json()["workspace_id"]
+    
+    # Simulate the query is flagged and waiting for approval in DB
+    app_db = app.state.app_db
+    async with app_db.get_app_db() as db:
+        ws = await db.get(Workspace, workspace_id)
+        qdata = await db.get(QueryData, ws.query_id)
+        qdata.status = "waiting_for_approval"
+        await db.commit()
+        
+    # 2. Login as admin
+    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
+    await create_user_and_login(admin_client, "admin2@example.com", "admin2", make_admin=True)
+    
+    # 3. Get list of queries to approve -> should show the workspace
+    list_response = await admin_client.get("/api/admin/queries_to_approve")
+    assert list_response.status_code == 200
+    approvals = list_response.json()["waiting_approvals"]
+    assert len(approvals) == 1
+    assert approvals[0]["workspace_id"] == workspace_id
+    assert approvals[0]["query"] == "UPDATE items SET price = 10"
+    
+    # 4. Preview execution by admin (executes without changing status)
+    mock_result.returns_rows = False
+    mock_result.rowcount = 5
+    
+    preview_response = await admin_client.post(f"/api/admin/execute_for_preview/{workspace_id}")
+    assert preview_response.status_code == 200
+    assert preview_response.json()["response_type"] == "data"
+    assert "5 rows affected" in preview_response.json()["message"]
+    
+    # Verify status remains "waiting_for_approval"
+    async with app_db.get_app_db() as db:
+        ws = await db.get(Workspace, workspace_id)
+        qdata = await db.get(QueryData, ws.query_id)
+        assert qdata.status == "waiting_for_approval"
+        
+    # 5. Approve query
+    approve_payload = {"show_results": True}
+    approve_response = await admin_client.post(f"/api/admin/approve_query/{workspace_id}", json=approve_payload)
+    assert approve_response.status_code == 200
+    assert approve_response.json()["success"] is True
+    assert approve_response.json()["status"] == "approved_with_results"
+    
+    # Verify regular user can now execute it
+    mock_result.returns_rows = False
+    mock_result.rowcount = 5
+    
+    exec_response = await regular_client.post(f"/api/execute_workspace/{workspace_id}")
+    assert exec_response.status_code == 200
+    assert exec_response.json()["response_type"] == "data"
+    assert "5 rows affected" in exec_response.json()["message"]
+
+
+@pytest.mark.asyncio
+async def test_admin_query_rejection(async_client: AsyncClient):
+    """
+    Tests query rejection flow by an admin.
+    """
+    # 1. Create user and workspace
+    regular_client = AsyncClient(transport=async_client._transport, base_url="http://test")
+    await create_user_and_login(regular_client, "user_rej@example.com", "user_rej")
+    create_payload = {
+        "name": "Rejected Workspace",
+        "query": "DROP TABLE critical_table",
+        "servername": "prod-server",
+        "database_name": "orders_db"
+    }
+    create_response = await regular_client.post("/api/workspaces", json=create_payload)
+    workspace_id = create_response.json()["workspace_id"]
+    
+    # Simulate query is waiting for approval
+    app_db = app.state.app_db
+    async with app_db.get_app_db() as db:
+        ws = await db.get(Workspace, workspace_id)
+        qdata = await db.get(QueryData, ws.query_id)
+        qdata.status = "waiting_for_approval"
+        await db.commit()
+        
+    # 2. Login as admin
+    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
+    await create_user_and_login(admin_client, "admin3@example.com", "admin3", make_admin=True)
+    
+    # 3. Reject query
+    reject_response = await admin_client.post(f"/api/admin/reject_query/{workspace_id}")
+    assert reject_response.status_code == 200
+    
+    # Verify status changed to "rejected"
+    async with app_db.get_app_db() as db:
+        ws = await db.get(Workspace, workspace_id)
+        qdata = await db.get(QueryData, ws.query_id)
+        assert qdata.status == "rejected"
+        assert ws.description == "Rejected by admin"
+        
+    # Verify regular user execution remains blocked (returns 400 Bad Request / QUERY_REJECTED_BY_ANALYZER)
+    exec_response = await regular_client.post(f"/api/execute_workspace/{workspace_id}")
+    assert exec_response.status_code == 400
+    assert exec_response.json()["error_code"] == "QUERY_REJECTED_BY_ANALYZER"
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (test_admin_api.py)</summary>

```python
"""
Integration tests for admin router and service layer.
Verifies Role-Based Access Control (RBAC), database registration, and query approval workflows.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager
from sqlalchemy.future import select

from app import app
from app_database.models import User, Workspace, QueryData, Databases

@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, servername, database_name):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result


async def create_user_and_login(async_client: AsyncClient, email: str, username: str, make_admin: bool = False) -> int:
    """
    Helper function to register, login, and optionally promote a user to admin.
    """
    register_data = {
        "username": username,
        "email": email,
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    app_db = app.state.app_db
    user_id = 0
    if make_admin:
        async with app_db.get_app_db() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            user.is_admin = True
            user_id = user.id
            await db.commit()
            
    login_data = {
        "email": email,
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    if not make_admin:
        async with app_db.get_app_db() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            user_id = user.id
            
    return user_id


@pytest.mark.asyncio
async def test_admin_rbac_restrictions(async_client: AsyncClient):
    """
    Tests that non-admin users are blocked from accessing administrative routes.
    """
    # 1. Login as regular user
    await create_user_and_login(async_client, "regular@example.com", "regular")
    
    # 2. Attempt to list queries waiting for approval -> should fail with 403 Forbidden
    resp_list = await async_client.get("/api/admin/queries_to_approve")
    assert resp_list.status_code == 403
    assert "Admin access required" in resp_list.json()["detail"]
    
    # 3. Attempt to approve a query -> should fail with 403 Forbidden
    resp_approve = await async_client.post("/api/admin/approve_query/1", json={"show_results": True})
    assert resp_approve.status_code == 403
    assert "Admin access required" in resp_approve.json()["detail"]
    
    # 4. Attempt to add a database -> should fail with 403 Forbidden
    db_payload = {
        "servername": "new-server",
        "database_name": "new-db",
        "tech_name": "mssql"
    }
    resp_add = await async_client.post("/api/admin/add_database", json=db_payload)
    assert resp_add.status_code == 403
    assert "Admin access required" in resp_add.json()["detail"]


@pytest.mark.asyncio
async def test_admin_database_registration(async_client: AsyncClient):
    """
    Tests registering databases by an admin, including duplicate checks.
    """
    # 1. Login as admin
    await create_user_and_login(async_client, "admin1@example.com", "admin1", make_admin=True)
    
    # 2. Add database
    db_payload = {
        "servername": "prod-server",
        "database_name": "orders_db",
        "tech_name": "postgresql"
    }
    response = await async_client.post("/api/admin/add_database", json=db_payload)
    assert response.status_code == 200
    assert "added successfully" in response.json()["message"]
    
    # Verify database entry in metadata DB
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        result = await db.execute(select(Databases).where(Databases.database_name == "orders_db"))
        db_entry = result.scalars().first()
        assert db_entry is not None
        assert db_entry.servername == "prod-server"
        assert db_entry.technology == "postgresql"
        
    # 3. Attempt to add duplicate database -> should fail with 400 Bad Request
    response_dup = await async_client.post("/api/admin/add_database", json=db_payload)
    assert response_dup.status_code == 400
    assert response_dup.json()["error_code"] == "DATABASE_ALREADY_EXISTS"
    assert "already exists" in response_dup.json()["message"]


@pytest.mark.asyncio
async def test_admin_query_approval_workflow(async_client: AsyncClient, mock_db_session):
    """
    Tests query approval and rejection flows, ensuring execution permissions update correctly.
    """
    mock_session, mock_result = mock_db_session
    
    # 1. Register a regular user and create a workspace
    regular_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(regular_client, "user_req@example.com", "user_req")
    
    create_payload = {
        "name": "Audit Workspace",
        "query": "UPDATE items SET price = 10",
        "servername": "prod-server",
        "database_name": "orders_db"
    }
    create_response = await regular_client.post("/api/workspaces", json=create_payload)
    workspace_id = create_response.json()["workspace_id"]
    
    # Simulate the query is flagged and waiting for approval in DB
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        qdata = await db.get(QueryData, ws.query_id)
        qdata.status = "waiting_for_approval"
        await db.commit()
        
    # 2. Login as admin
    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(admin_client, "admin2@example.com", "admin2", make_admin=True)
    
    # 3. Get list of queries to approve -> should show the workspace
    list_response = await admin_client.get("/api/admin/queries_to_approve")
    assert list_response.status_code == 200
    approvals = list_response.json()["waiting_approvals"]
    assert len(approvals) == 1
    assert approvals[0]["workspace_id"] == workspace_id
    assert approvals[0]["query"] == "UPDATE items SET price = 10"
    
    # 4. Preview execution by admin (executes without changing status)
    mock_result.returns_rows = False
    mock_result.rowcount = 5
    
    preview_response = await admin_client.post(f"/api/admin/execute_for_preview/{workspace_id}")
    assert preview_response.status_code == 200
    assert preview_response.json()["response_type"] == "data"
    assert "5 rows affected" in preview_response.json()["message"]
    
    # Verify status remains "waiting_for_approval"
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        qdata = await db.get(QueryData, ws.query_id)
        assert qdata.status == "waiting_for_approval"
        
    # 5. Approve query
    approve_payload = {"show_results": True}
    approve_response = await admin_client.post(f"/api/admin/approve_query/{workspace_id}", json=approve_payload)
    assert approve_response.status_code == 200
    assert approve_response.json()["success"] is True
    assert approve_response.json()["status"] == "approved_with_results"
    
    # Verify regular user can now execute it
    mock_result.returns_rows = False
    mock_result.rowcount = 5
    
    exec_response = await regular_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response.status_code == 200
    assert exec_response.json()["response_type"] == "data"
    assert "5 rows affected" in exec_response.json()["message"]


@pytest.mark.asyncio
async def test_admin_query_rejection(async_client: AsyncClient):
    """
    Tests query rejection flow by an admin.
    """
    # 1. Create user and workspace
    regular_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(regular_client, "user_rej@example.com", "user_rej")
    create_payload = {
        "name": "Rejected Workspace",
        "query": "DROP TABLE critical_table",
        "servername": "prod-server",
        "database_name": "orders_db"
    }
    create_response = await regular_client.post("/api/workspaces", json=create_payload)
    workspace_id = create_response.json()["workspace_id"]
    
    # Simulate query is waiting for approval
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        qdata = await db.get(QueryData, ws.query_id)
        qdata.status = "waiting_for_approval"
        await db.commit()
        
    # 2. Login as admin
    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(admin_client, "admin3@example.com", "admin3", make_admin=True)
    
    # 3. Reject query
    reject_response = await admin_client.post(f"/api/admin/reject_query/{workspace_id}")
    assert reject_response.status_code == 200
    
    # Verify status changed to "rejected"
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        qdata = await db.get(QueryData, ws.query_id)
        assert qdata.status == "rejected"
        assert ws.description == "Rejected by admin"
        
    # Verify regular user execution remains blocked (returns 400 Bad Request / QUERY_REJECTED_BY_ANALYZER)
    exec_response = await regular_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response.status_code == 400
    assert exec_response.json()["error_code"] == "QUERY_REJECTED_BY_ANALYZER"

```
</details>



#### <a name="web_apitestsintegrationtest_error_handling_and_tracepy"></a> `web_api/tests/integration/test_error_handling_and_trace.py`
**Açıklama:** Trace ID üretimini, global hata yakalama ve dönüştürme sistemini, REST HTTP 400 ve 404 yanıtlarındaki trace_id varlığını doğrulayan uçtan uca entegrasyon testleri.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/tests/integration/test_error_handling_and_trace.py b/web_api/tests/integration/test_error_handling_and_trace.py
new file mode 100644
index 0000000..793d278
--- /dev/null
+++ b/web_api/tests/integration/test_error_handling_and_trace.py
@@ -0,0 +1,133 @@
+"""
+Integration tests for the centralized Exception Handling and Trace ID tracking system.
+Verifies Trace ID headers, global exception routing, and error translation.
+"""
+import pytest
+from httpx import AsyncClient
+from unittest.mock import MagicMock, AsyncMock, patch
+from contextlib import asynccontextmanager
+
+from app import app
+from app_database.models import Databases
+
+@pytest.fixture
+def mock_db_session():
+    """
+    Fixture that patches DatabaseProvider.get_session to return a mock session.
+    """
+    mock_session = AsyncMock()
+    mock_result = MagicMock()
+    mock_session.execute.return_value = mock_result
+    
+    @asynccontextmanager
+    async def fake_get_session(user, servername, database_name):
+        yield mock_session
+        
+    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
+        yield mock_session, mock_result
+
+@pytest.mark.asyncio
+async def test_trace_id_header_on_public_route(async_client: AsyncClient):
+    """
+    Test that even public endpoints (like /health) return the X-Request-ID trace header.
+    """
+    response = await async_client.get("/health")
+    assert response.status_code == 200
+    assert "X-Request-ID" in response.headers
+    assert len(response.headers["X-Request-ID"]) > 0
+
+@pytest.mark.asyncio
+async def test_query_execution_error_translation(async_client: AsyncClient, mock_db_session):
+    """
+    Test that database execution exceptions are wrapped into QueryExecutionError,
+    caught by the global handler, and returned as a clean 400 Bad Request.
+    """
+    mock_session, mock_result = mock_db_session
+    
+    # 1. Inject mock database
+    app_db = app.state.app_db
+    async with app_db.get_app_db() as db:
+        test_db = Databases(
+            servername="trace-server",
+            database_name="trace-db",
+            technology="postgresql"
+        )
+        db.add(test_db)
+        await db.commit()
+    
+    # Reload db_info in provider
+    db_info = await app_db.get_db_info()
+    app.state.db_provider.set_db_info(db_info)
+    
+    # 2. Register and login
+    register_data = {
+        "username": "traceuser",
+        "email": "trace@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/register", json=register_data)
+    
+    login_data = {
+        "email": "trace@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/login", json=login_data)
+    
+    # 3. Configure mock session to raise a database execution exception (e.g. syntax error)
+    mock_session.execute.side_effect = Exception("column 'non_existent' does not exist")
+    
+    # 4. Execute query
+    query_payload = {
+        "query": "SELECT non_existent FROM users",
+        "servername": "trace-server",
+        "database_name": "trace-db"
+    }
+    response = await async_client.post("/api/execute_query", json=query_payload)
+    
+    # Assert REST status is 400 (Bad Request) instead of 500 or 200 with error
+    assert response.status_code == 400
+    
+    resp_data = response.json()
+    assert resp_data["success"] is False
+    assert resp_data["error_code"] == "QUERY_EXECUTION_FAILED"
+    assert "column 'non_existent' does not exist" in resp_data["message"]
+    assert "column 'non_existent' does not exist" in resp_data["error"]
+    
+    # Verify Trace ID matches the response header
+    assert "X-Request-ID" in response.headers
+    assert resp_data["trace_id"] == response.headers["X-Request-ID"]
+
+@pytest.mark.asyncio
+async def test_workspace_not_found_error_translation(async_client: AsyncClient):
+    """
+    Test that attempting to access a non-existent workspace raises WorkspaceNotFoundError
+    which is translated by the global handler into a clean 404 Not Found.
+    """
+    # 1. Register and login
+    register_data = {
+        "username": "traceuser2",
+        "email": "trace2@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/register", json=register_data)
+    
+    login_data = {
+        "email": "trace2@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/login", json=login_data)
+    
+    # 2. Get non-existent workspace (ID: 99999)
+    response = await async_client.get("/api/get_workspace_by_id/99999")
+    
+    # Assert REST status is 404 (Not Found) instead of 400 or 500
+    assert response.status_code == 404
+    
+    resp_data = response.json()
+    assert resp_data["success"] is False
+    assert resp_data["error_code"] == "WORKSPACE_NOT_FOUND"
+    assert "Workspace not found" in resp_data["message"]
+    
+    # Verify Trace ID matches header
+    assert "X-Request-ID" in response.headers
+    assert resp_data["trace_id"] == response.headers["X-Request-ID"]
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (test_error_handling_and_trace.py)</summary>

```python
"""
Integration tests for the centralized Exception Handling and Trace ID tracking system.
Verifies Trace ID headers, global exception routing, and error translation.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from app import app
from app_database.models import Databases

@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, servername, database_name):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result

@pytest.mark.asyncio
async def test_trace_id_header_on_public_route(async_client: AsyncClient):
    """
    Test that even public endpoints (like /health) return the X-Request-ID trace header.
    """
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0

@pytest.mark.asyncio
async def test_query_execution_error_translation(async_client: AsyncClient, mock_db_session):
    """
    Test that database execution exceptions are wrapped into QueryExecutionError,
    caught by the global handler, and returned as a clean 400 Bad Request.
    """
    mock_session, mock_result = mock_db_session
    
    # 1. Inject mock database
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="trace-server",
            database_name="trace-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
    
    # Reload db_info in provider
    db_info = await app_db.get_db_info()
    app.state.db_provider.set_db_info(db_info)
    
    # 2. Register and login
    register_data = {
        "username": "traceuser",
        "email": "trace@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "trace@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # 3. Configure mock session to raise a database execution exception (e.g. syntax error)
    mock_session.execute.side_effect = Exception("column 'non_existent' does not exist")
    
    # 4. Execute query
    query_payload = {
        "query": "SELECT non_existent FROM users",
        "servername": "trace-server",
        "database_name": "trace-db"
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    
    # Assert REST status is 400 (Bad Request) instead of 500 or 200 with error
    assert response.status_code == 400
    
    resp_data = response.json()
    assert resp_data["success"] is False
    assert resp_data["error_code"] == "QUERY_EXECUTION_FAILED"
    assert "column 'non_existent' does not exist" in resp_data["message"]
    assert "column 'non_existent' does not exist" in resp_data["error"]
    
    # Verify Trace ID matches the response header
    assert "X-Request-ID" in response.headers
    assert resp_data["trace_id"] == response.headers["X-Request-ID"]

@pytest.mark.asyncio
async def test_workspace_not_found_error_translation(async_client: AsyncClient):
    """
    Test that attempting to access a non-existent workspace raises WorkspaceNotFoundError
    which is translated by the global handler into a clean 404 Not Found.
    """
    # 1. Register and login
    register_data = {
        "username": "traceuser2",
        "email": "trace2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "trace2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # 2. Get non-existent workspace (ID: 99999)
    response = await async_client.get("/api/get_workspace_by_id/99999")
    
    # Assert REST status is 404 (Not Found) instead of 400 or 500
    assert response.status_code == 404
    
    resp_data = response.json()
    assert resp_data["success"] is False
    assert resp_data["error_code"] == "WORKSPACE_NOT_FOUND"
    assert "Workspace not found" in resp_data["message"]
    
    # Verify Trace ID matches header
    assert "X-Request-ID" in response.headers
    assert resp_data["trace_id"] == response.headers["X-Request-ID"]

```
</details>



#### <a name="web_apitestsintegrationtest_notifications_and_slackpy"></a> `web_api/tests/integration/test_notifications_and_slack.py`
**Açıklama:** Riskli sorgularda Slack bildirimlerinin gönderilmesini ve Slack etkileşim mekanizmalarını mock objeler üzerinden doğrulayan entegrasyon testleri.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/tests/integration/test_notifications_and_slack.py b/web_api/tests/integration/test_notifications_and_slack.py
new file mode 100644
index 0000000..9451076
--- /dev/null
+++ b/web_api/tests/integration/test_notifications_and_slack.py
@@ -0,0 +1,202 @@
+"""
+Integration tests for Slack Interactive listener and Notification services.
+Mocks out-of-band network calls and verifies database state transitions.
+"""
+import pytest
+import httpx
+from unittest.mock import MagicMock, AsyncMock, patch
+from sqlalchemy.future import select
+from httpx import AsyncClient
+
+from app import app
+from app_database.models import User, Workspace, QueryData
+from slack_integration.listener import SlackListener
+from notification.services import NotificationService
+
+async def create_test_user_and_workspace(email: str, username: str) -> tuple[int, str]:
+    """
+    Helper function to create a test user and a workspace with its query data in metadata DB.
+    Uses a single transaction to prevent expired attributes lazy loading issues.
+    """
+    app_db = app.state.app_db
+    async with app_db.get_app_db() as db:
+        # 1. Create and flush user to get ID
+        user = User(username=username, email=email)
+        user.set_password("Password123!")
+        db.add(user)
+        await db.flush()
+        user_id = user.id
+        
+        # 2. Create and flush query data to get ID
+        qdata = QueryData(
+            query="SELECT * FROM confidential_data",
+            servername="prod-server",
+            database_name="finance_db",
+            status="waiting_for_approval",
+            uuid="test-uuid-12345",
+            user_id=user_id
+        )
+        db.add(qdata)
+        await db.flush()
+        qdata_id = qdata.id
+        qdata_uuid = qdata.uuid
+        
+        # 3. Create workspace
+        ws = Workspace(
+            name="Financials",
+            user_id=user_id,
+            query_id=qdata_id,
+            show_results=False,
+            description="Waiting for admin review"
+        )
+        db.add(ws)
+        await db.flush()
+        ws_id = ws.id
+        await db.commit()
+        
+        return ws_id, qdata_uuid
+
+
+@pytest.mark.asyncio
+async def test_slack_interactive_approval_flow(async_client: AsyncClient):
+    """
+    Tests the Slack Bolt app approval action handler.
+    Simulates a Slack admin clicking the 'Approve' button and verifies metadata DB updates.
+    """
+    # 1. Setup test workspace and query data
+    ws_id, q_uuid = await create_test_user_and_workspace("user_slack_appr@example.com", "slack_appr_user")
+    
+    # 2. Instantiate SlackListener with app_db
+    app_db = app.state.app_db
+    listener = SlackListener(app_db=app_db)
+    
+    # 3. Construct mock body and respond callbacks
+    mock_ack = AsyncMock()
+    mock_respond = AsyncMock()
+    mock_body = {
+        "user": {"id": "U_ADMIN_123"},
+        "actions": [{"value": q_uuid}]
+    }
+    
+    # 4. Trigger the handler directly
+    await listener.handle_approve_with_results(
+        ack=mock_ack,
+        body=mock_body,
+        respond=mock_respond
+    )
+    
+    # Verify ack was called
+    mock_ack.assert_called_once()
+    
+    # Verify Slack response was sent
+    mock_respond.assert_called_once()
+    respond_args = mock_respond.call_args[1]
+    assert "Query approved" in respond_args["text"]
+    assert "U_ADMIN_123" in respond_args["text"]
+    
+    # Verify DB state was updated successfully
+    async with app_db.get_app_db() as db:
+        result_q = await db.execute(select(QueryData).where(QueryData.uuid == q_uuid))
+        qdata = result_q.scalars().first()
+        assert qdata.status == "approved_with_results"
+        
+        result_ws = await db.execute(select(Workspace).where(Workspace.query_id == qdata.id))
+        ws = result_ws.scalars().first()
+        assert ws.show_results is True
+        assert "Approved by admin via Slack" in ws.description
+
+
+@pytest.mark.asyncio
+async def test_slack_interactive_rejection_flow(async_client: AsyncClient):
+    """
+    Tests the Slack Bolt app rejection action handler.
+    Simulates a Slack admin clicking the 'Reject' button and verifies metadata DB updates.
+    """
+    # 1. Setup test workspace and query data
+    ws_id, q_uuid = await create_test_user_and_workspace("user_slack_rej@example.com", "slack_rej_user")
+    
+    # 2. Instantiate SlackListener
+    app_db = app.state.app_db
+    listener = SlackListener(app_db=app_db)
+    
+    # 3. Construct mock body and respond callbacks
+    mock_ack = AsyncMock()
+    mock_respond = AsyncMock()
+    mock_body = {
+        "user": {"id": "U_ADMIN_999"},
+        "actions": [{"value": q_uuid}]
+    }
+    
+    # 4. Trigger the handler directly
+    await listener.handle_reject_query(
+        ack=mock_ack,
+        body=mock_body,
+        respond=mock_respond
+    )
+    
+    # Verify ack was called
+    mock_ack.assert_called_once()
+    
+    # Verify Slack response was sent
+    mock_respond.assert_called_once()
+    respond_args = mock_respond.call_args[1]
+    assert "Query rejected" in respond_args["text"]
+    assert "U_ADMIN_999" in respond_args["text"]
+    
+    # Verify DB state was updated successfully
+    async with app_db.get_app_db() as db:
+        result_q = await db.execute(select(QueryData).where(QueryData.uuid == q_uuid))
+        qdata = result_q.scalars().first()
+        assert qdata.status == "rejected"
+        
+        result_ws = await db.execute(select(Workspace).where(Workspace.query_id == qdata.id))
+        ws = result_ws.scalars().first()
+        assert ws.show_results is False
+        assert "Rejected by admin via Slack" in ws.description
+
+
+@pytest.mark.asyncio
+async def test_notification_webhook_payload():
+    """
+    Tests the NotificationService to ensure it formats and sends webhook payloads correctly.
+    """
+    # 1. Instantiate NotificationService with a mock Slack Webhook URL
+    notifier = NotificationService()
+    notifier.slack_url = "https://hooks.slack.com/services/T_MOCK/B_MOCK/W_MOCK"
+    
+    # 2. Mock httpx.AsyncClient.post
+    mock_response = MagicMock(spec=httpx.Response)
+    mock_response.status_code = 200
+    
+    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
+        mock_post.return_value = mock_response
+        
+        # 3. Send notification
+        success = await notifier.send_approval_notification(
+            request_id="test-req-id-777",
+            username="analyst_bob",
+            request_time="2026-06-25 12:00:00",
+            database_name="customer_db",
+            servername="prod-db-1",
+            risk_type="risky_dml",
+            query="DELETE FROM customers"
+        )
+        
+        assert success is True
+        
+        # Verify post call
+        mock_post.assert_called_once()
+        post_args = mock_post.call_args
+        url = post_args[0][0]
+        json_payload = post_args[1]["json"]
+        
+        assert url == "https://hooks.slack.com/services/T_MOCK/B_MOCK/W_MOCK"
+        assert "blocks" in json_payload
+        
+        # Verify payload contains critical query metadata
+        blocks_str = str(json_payload["blocks"])
+        assert "test-req-id-777" in blocks_str
+        assert "analyst_bob" in blocks_str
+        assert "prod-db-1" in blocks_str
+        assert "customer_db" in blocks_str
+        assert "DELETE FROM customers" in blocks_str
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (test_notifications_and_slack.py)</summary>

```python
"""
Integration tests for Slack Interactive listener and Notification services.
Mocks out-of-band network calls and verifies database state transitions.
"""
import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.future import select
from httpx import AsyncClient

from app import app
from app_database.models import User, Workspace, QueryData
from slack_integration.listener import SlackListener
from notification.services import NotificationService

async def create_test_user_and_workspace(email: str, username: str) -> tuple[int, str]:
    """
    Helper function to create a test user and a workspace with its query data in metadata DB.
    Uses a single transaction to prevent expired attributes lazy loading issues.
    """
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        # 1. Create and flush user to get ID
        user = User(username=username, email=email)
        user.set_password("Password123!")
        db.add(user)
        await db.flush()
        user_id = user.id
        
        # 2. Create and flush query data to get ID
        qdata = QueryData(
            query="SELECT * FROM confidential_data",
            servername="prod-server",
            database_name="finance_db",
            status="waiting_for_approval",
            uuid="test-uuid-12345",
            user_id=user_id
        )
        db.add(qdata)
        await db.flush()
        qdata_id = qdata.id
        qdata_uuid = qdata.uuid
        
        # 3. Create workspace
        ws = Workspace(
            name="Financials",
            user_id=user_id,
            query_id=qdata_id,
            show_results=False,
            description="Waiting for admin review"
        )
        db.add(ws)
        await db.flush()
        ws_id = ws.id
        await db.commit()
        
        return ws_id, qdata_uuid


@pytest.mark.asyncio
async def test_slack_interactive_approval_flow(async_client: AsyncClient):
    """
    Tests the Slack Bolt app approval action handler.
    Simulates a Slack admin clicking the 'Approve' button and verifies metadata DB updates.
    """
    # 1. Setup test workspace and query data
    ws_id, q_uuid = await create_test_user_and_workspace("user_slack_appr@example.com", "slack_appr_user")
    
    # 2. Instantiate SlackListener with app_db
    app_db = app.state.app_db
    listener = SlackListener(app_db=app_db)
    
    # 3. Construct mock body and respond callbacks
    mock_ack = AsyncMock()
    mock_respond = AsyncMock()
    mock_body = {
        "user": {"id": "U_ADMIN_123"},
        "actions": [{"value": q_uuid}]
    }
    
    # 4. Trigger the handler directly
    await listener.handle_approve_with_results(
        ack=mock_ack,
        body=mock_body,
        respond=mock_respond
    )
    
    # Verify ack was called
    mock_ack.assert_called_once()
    
    # Verify Slack response was sent
    mock_respond.assert_called_once()
    respond_args = mock_respond.call_args[1]
    assert "Query approved" in respond_args["text"]
    assert "U_ADMIN_123" in respond_args["text"]
    
    # Verify DB state was updated successfully
    async with app_db.get_app_db() as db:
        result_q = await db.execute(select(QueryData).where(QueryData.uuid == q_uuid))
        qdata = result_q.scalars().first()
        assert qdata.status == "approved_with_results"
        
        result_ws = await db.execute(select(Workspace).where(Workspace.query_id == qdata.id))
        ws = result_ws.scalars().first()
        assert ws.show_results is True
        assert "Approved by admin via Slack" in ws.description


@pytest.mark.asyncio
async def test_slack_interactive_rejection_flow(async_client: AsyncClient):
    """
    Tests the Slack Bolt app rejection action handler.
    Simulates a Slack admin clicking the 'Reject' button and verifies metadata DB updates.
    """
    # 1. Setup test workspace and query data
    ws_id, q_uuid = await create_test_user_and_workspace("user_slack_rej@example.com", "slack_rej_user")
    
    # 2. Instantiate SlackListener
    app_db = app.state.app_db
    listener = SlackListener(app_db=app_db)
    
    # 3. Construct mock body and respond callbacks
    mock_ack = AsyncMock()
    mock_respond = AsyncMock()
    mock_body = {
        "user": {"id": "U_ADMIN_999"},
        "actions": [{"value": q_uuid}]
    }
    
    # 4. Trigger the handler directly
    await listener.handle_reject_query(
        ack=mock_ack,
        body=mock_body,
        respond=mock_respond
    )
    
    # Verify ack was called
    mock_ack.assert_called_once()
    
    # Verify Slack response was sent
    mock_respond.assert_called_once()
    respond_args = mock_respond.call_args[1]
    assert "Query rejected" in respond_args["text"]
    assert "U_ADMIN_999" in respond_args["text"]
    
    # Verify DB state was updated successfully
    async with app_db.get_app_db() as db:
        result_q = await db.execute(select(QueryData).where(QueryData.uuid == q_uuid))
        qdata = result_q.scalars().first()
        assert qdata.status == "rejected"
        
        result_ws = await db.execute(select(Workspace).where(Workspace.query_id == qdata.id))
        ws = result_ws.scalars().first()
        assert ws.show_results is False
        assert "Rejected by admin via Slack" in ws.description


@pytest.mark.asyncio
async def test_notification_webhook_payload():
    """
    Tests the NotificationService to ensure it formats and sends webhook payloads correctly.
    """
    # 1. Instantiate NotificationService with a mock Slack Webhook URL
    notifier = NotificationService()
    notifier.slack_url = "https://hooks.slack.com/services/T_MOCK/B_MOCK/W_MOCK"
    
    # 2. Mock httpx.AsyncClient.post
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        # 3. Send notification
        success = await notifier.send_approval_notification(
            request_id="test-req-id-777",
            username="analyst_bob",
            request_time="2026-06-25 12:00:00",
            database_name="customer_db",
            servername="prod-db-1",
            risk_type="risky_dml",
            query="DELETE FROM customers"
        )
        
        assert success is True
        
        # Verify post call
        mock_post.assert_called_once()
        post_args = mock_post.call_args
        url = post_args[0][0]
        json_payload = post_args[1]["json"]
        
        assert url == "https://hooks.slack.com/services/T_MOCK/B_MOCK/W_MOCK"
        assert "blocks" in json_payload
        
        # Verify payload contains critical query metadata
        blocks_str = str(json_payload["blocks"])
        assert "test-req-id-777" in blocks_str
        assert "analyst_bob" in blocks_str
        assert "prod-db-1" in blocks_str
        assert "customer_db" in blocks_str
        assert "DELETE FROM customers" in blocks_str

```
</details>



#### <a name="web_apitestsintegrationtest_query_executionpy"></a> `web_api/tests/integration/test_query_execution.py`
**Açıklama:** Güvenli sorgu çalıştırma, AST risk analiz limitleri ve dinamik sonuç maskeleme mekanizmalarının doğruluğunu denetleyen entegrasyon testleri.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/tests/integration/test_query_execution.py b/web_api/tests/integration/test_query_execution.py
new file mode 100644
index 0000000..4f13664
--- /dev/null
+++ b/web_api/tests/integration/test_query_execution.py
@@ -0,0 +1,128 @@
+"""
+Integration tests for query execution endpoints.
+Verifies SELECT and DML/non-SELECT query execution paths and safety.
+"""
+import pytest
+from httpx import AsyncClient
+from unittest.mock import MagicMock, AsyncMock, patch
+from contextlib import asynccontextmanager
+
+from app import app
+from app_database.models import Databases
+
+@pytest.fixture
+def mock_db_session():
+    """
+    Fixture that patches DatabaseProvider.get_session to return a mock session.
+    """
+    mock_session = AsyncMock()
+    mock_result = MagicMock()
+    
+    # We will configure the mock_result inside each test case
+    mock_session.execute.return_value = mock_result
+    
+    @asynccontextmanager
+    async def fake_get_session(user, servername, database_name):
+        yield mock_session
+        
+    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
+        yield mock_session, mock_result
+
+@pytest.mark.asyncio
+async def test_select_query_execution(async_client: AsyncClient, mock_db_session):
+    """
+    Test that a SELECT query returns data successfully.
+    """
+    mock_session, mock_result = mock_db_session
+    
+    # 1. Setup mock database in metadata DB
+    app_db = app.state.app_db
+    async with app_db.get_app_db() as db:
+        # Add a test database entry to Databases table
+        test_db = Databases(
+            servername="test-server",
+            database_name="test-db",
+            technology="postgresql"
+        )
+        db.add(test_db)
+        await db.commit()
+        
+    # Reload db_info in db_provider to pick up the new database
+    db_info = await app_db.get_db_info()
+    app.state.db_provider.set_db_info(db_info)
+    
+    # 2. Register and login
+    register_data = {
+        "username": "queryuser",
+        "email": "query@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/register", json=register_data)
+    
+    login_data = {
+        "email": "query@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/login", json=login_data)
+    
+    # 3. Configure mock result for SELECT (returns rows)
+    mock_result.returns_rows = True
+    
+    # Create a mock row with a _mapping dictionary
+    mock_row = MagicMock()
+    mock_row._mapping = {"id": 1, "name": "John Doe"}
+    mock_result.fetchmany.return_value = [mock_row]
+    
+    # 4. Execute the query via API
+    query_payload = {
+        "query": "SELECT * FROM users",
+        "servername": "test-server",
+        "database_name": "test-db"
+    }
+    response = await async_client.post("/api/execute_query", json=query_payload)
+    assert response.status_code == 200, f"Query execution failed: {response.text}"
+    
+    resp_data = response.json()
+    assert resp_data["response_type"] == "data"
+    assert resp_data["data"] == [{"id": 1, "name": "John Doe"}]
+    assert "1 rows returned" in resp_data["message"]
+
+@pytest.mark.asyncio
+async def test_dml_query_execution(async_client: AsyncClient, mock_db_session):
+    """
+    Test that a DML/non-SELECT query (like UPDATE) returns affected rows count successfully
+    and does not crash with ResourceClosedError.
+    """
+    mock_session, mock_result = mock_db_session
+    
+    # Register and login
+    register_data = {
+        "username": "queryuser2",
+        "email": "query2@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/register", json=register_data)
+    
+    login_data = {
+        "email": "query2@example.com",
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/login", json=login_data)
+    
+    # Configure mock result for UPDATE (does NOT return rows)
+    mock_result.returns_rows = False
+    mock_result.rowcount = 3
+    
+    # Execute the query via API
+    query_payload = {
+        "query": "UPDATE users SET active = 1 WHERE age > 30",
+        "servername": "test-server",
+        "database_name": "test-db"
+    }
+    response = await async_client.post("/api/execute_query", json=query_payload)
+    assert response.status_code == 200, f"Query execution failed: {response.text}"
+    
+    resp_data = response.json()
+    assert resp_data["response_type"] == "data"
+    assert resp_data["data"] == []
+    assert resp_data["message"] == "3 rows affected"
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (test_query_execution.py)</summary>

```python
"""
Integration tests for query execution endpoints.
Verifies SELECT and DML/non-SELECT query execution paths and safety.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from app import app
from app_database.models import Databases

@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    
    # We will configure the mock_result inside each test case
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, servername, database_name):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result

@pytest.mark.asyncio
async def test_select_query_execution(async_client: AsyncClient, mock_db_session):
    """
    Test that a SELECT query returns data successfully.
    """
    mock_session, mock_result = mock_db_session
    
    # 1. Setup mock database in metadata DB
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        # Add a test database entry to Databases table
        test_db = Databases(
            servername="test-server",
            database_name="test-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        
    # Reload db_info in db_provider to pick up the new database
    db_info = await app_db.get_db_info()
    app.state.db_provider.set_db_info(db_info)
    
    # 2. Register and login
    register_data = {
        "username": "queryuser",
        "email": "query@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "query@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # 3. Configure mock result for SELECT (returns rows)
    mock_result.returns_rows = True
    
    # Create a mock row with a _mapping dictionary
    mock_row = MagicMock()
    mock_row._mapping = {"id": 1, "name": "John Doe"}
    mock_result.fetchmany.return_value = [mock_row]
    
    # 4. Execute the query via API
    query_payload = {
        "query": "SELECT * FROM users",
        "servername": "test-server",
        "database_name": "test-db"
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    assert response.status_code == 200, f"Query execution failed: {response.text}"
    
    resp_data = response.json()
    assert resp_data["response_type"] == "data"
    assert resp_data["data"] == [{"id": 1, "name": "John Doe"}]
    assert "1 rows returned" in resp_data["message"]

@pytest.mark.asyncio
async def test_dml_query_execution(async_client: AsyncClient, mock_db_session):
    """
    Test that a DML/non-SELECT query (like UPDATE) returns affected rows count successfully
    and does not crash with ResourceClosedError.
    """
    mock_session, mock_result = mock_db_session
    
    # Register and login
    register_data = {
        "username": "queryuser2",
        "email": "query2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "query2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # Configure mock result for UPDATE (does NOT return rows)
    mock_result.returns_rows = False
    mock_result.rowcount = 3
    
    # Execute the query via API
    query_payload = {
        "query": "UPDATE users SET active = 1 WHERE age > 30",
        "servername": "test-server",
        "database_name": "test-db"
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    assert response.status_code == 200, f"Query execution failed: {response.text}"
    
    resp_data = response.json()
    assert resp_data["response_type"] == "data"
    assert resp_data["data"] == []
    assert resp_data["message"] == "3 rows affected"

```
</details>



#### <a name="web_apitestsintegrationtest_workspacespy"></a> `web_api/tests/integration/test_workspaces.py`
**Açıklama:** Çalışma alanı CRUD işlemlerini ve sahiplik/yetki doğrulamalarını test eden entegrasyon testleri.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/tests/integration/test_workspaces.py b/web_api/tests/integration/test_workspaces.py
new file mode 100644
index 0000000..de63f69
--- /dev/null
+++ b/web_api/tests/integration/test_workspaces.py
@@ -0,0 +1,193 @@
+"""
+Integration tests for workspaces router and service layer.
+Verifies Workspace CRUD operations, ownership validation, and execution rules.
+"""
+import pytest
+from httpx import AsyncClient
+from unittest.mock import MagicMock, AsyncMock, patch
+from contextlib import asynccontextmanager
+
+from app import app
+from app_database.models import Workspace, QueryData
+
+@pytest.fixture
+def mock_db_session():
+    """
+    Fixture that patches DatabaseProvider.get_session to return a mock session.
+    """
+    mock_session = AsyncMock()
+    mock_result = MagicMock()
+    mock_session.execute.return_value = mock_result
+    
+    @asynccontextmanager
+    async def fake_get_session(user, servername, database_name):
+        yield mock_session
+        
+    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
+        yield mock_session, mock_result
+
+
+async def create_user_and_login(async_client: AsyncClient, email: str, username: str) -> None:
+    """
+    Helper function to register and login a user.
+    """
+    register_data = {
+        "username": username,
+        "email": email,
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/register", json=register_data)
+    
+    login_data = {
+        "email": email,
+        "password": "StrongPassword123!"
+    }
+    await async_client.post("/api/login", json=login_data)
+
+
+@pytest.mark.asyncio
+async def test_workspace_crud_operations(async_client: AsyncClient):
+    """
+    Tests creating, listing, updating, retrieving, and deleting workspaces.
+    """
+    # 1. Register and login
+    await create_user_and_login(async_client, "user1@example.com", "user1")
+    
+    # 2. Create workspace
+    create_payload = {
+        "name": "My Workspace",
+        "query": "SELECT * FROM my_table",
+        "servername": "localhost",
+        "database_name": "my_db"
+    }
+    create_response = await async_client.post("/api/workspaces", json=create_payload)
+    assert create_response.status_code == 200, f"Failed to create workspace: {create_response.text}"
+    create_data = create_response.json()
+    assert create_data["success"] is True
+    workspace_id = create_data["workspace_id"]
+    
+    # 3. Get workspace details
+    detail_response = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
+    assert detail_response.status_code == 200
+    detail_data = detail_response.json()
+    assert detail_data["name"] == "My Workspace"
+    assert detail_data["query"] == "SELECT * FROM my_table"
+    assert detail_data["servername"] == "localhost"
+    assert detail_data["database_name"] == "my_db"
+    assert detail_data["status"] == "saved_in_workspace"  # Newly created queries default to saved_in_workspace
+    
+    # 4. List workspaces
+    list_response = await async_client.get("/api/workspaces")
+    assert list_response.status_code == 200
+    list_data = list_response.json()
+    assert len(list_data["workspaces"]) == 1
+    assert list_data["workspaces"][0]["id"] == workspace_id
+    
+    # 5. Update workspace query
+    update_payload = {
+        "query": "SELECT count(*) FROM my_table",
+        "status": "saved_in_workspace"
+    }
+    update_response = await async_client.put(f"/api/workspaces/{workspace_id}", json=update_payload)
+    assert update_response.status_code == 200
+    
+    # Verify update
+    detail_response_2 = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
+    detail_data_2 = detail_response_2.json()
+    assert detail_data_2["query"] == "SELECT count(*) FROM my_table"
+    
+    # 6. Delete workspace
+    delete_response = await async_client.delete(f"/api/workspaces/{workspace_id}")
+    assert delete_response.status_code == 200
+    
+    # Verify deletion
+    list_response_2 = await async_client.get("/api/workspaces")
+    assert len(list_response_2.json()["workspaces"]) == 0
+
+
+@pytest.mark.asyncio
+async def test_workspace_ownership_access_controls(async_client: AsyncClient):
+    """
+    Tests that a user cannot access, modify, or delete workspaces owned by another user.
+    """
+    # 1. Login user1 and create a workspace
+    await create_user_and_login(async_client, "owner@example.com", "owner")
+    create_payload = {
+        "name": "Owner Workspace",
+        "query": "SELECT 1",
+        "servername": "localhost",
+        "database_name": "db"
+    }
+    create_response = await async_client.post("/api/workspaces", json=create_payload)
+    workspace_id = create_response.json()["workspace_id"]
+    
+    # 2. Login user2 (attacker)
+    await create_user_and_login(async_client, "attacker@example.com", "attacker")
+    
+    # 3. Attacker tries to get details -> should fail
+    get_response = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
+    assert get_response.status_code == 403
+    assert get_response.json()["error_code"] == "WORKSPACE_ACCESS_DENIED"
+    
+    # 4. Attacker tries to update -> should fail
+    update_payload = {
+        "query": "DROP TABLE users",
+        "status": "saved_in_workspace"
+    }
+    update_response = await async_client.put(f"/api/workspaces/{workspace_id}", json=update_payload)
+    assert update_response.status_code == 403
+    assert update_response.json()["error_code"] == "WORKSPACE_ACCESS_DENIED"
+    
+    # 5. Attacker tries to delete -> should fail
+    delete_response = await async_client.delete(f"/api/workspaces/{workspace_id}")
+    assert delete_response.status_code == 403
+    assert delete_response.json()["error_code"] == "WORKSPACE_ACCESS_DENIED"
+
+
+@pytest.mark.asyncio
+async def test_workspace_execution_rules(async_client: AsyncClient, mock_db_session):
+    """
+    Tests query execution workflows on a workspace.
+    A workspace query must be approved and show_results must be True to execute.
+    """
+    mock_session, mock_result = mock_db_session
+    
+    # 1. Login and create workspace
+    await create_user_and_login(async_client, "exec@example.com", "exec_user")
+    create_payload = {
+        "name": "Execution Workspace",
+        "query": "SELECT * FROM orders",
+        "servername": "localhost",
+        "database_name": "sales_db"
+    }
+    create_response = await async_client.post("/api/workspaces", json=create_payload)
+    workspace_id = create_response.json()["workspace_id"]
+    
+    # 2. Try to execute immediately (default is saved_in_workspace/unapproved) -> should fail with 400 Bad Request
+    exec_response = await async_client.post(f"/api/execute_workspace/{workspace_id}")
+    assert exec_response.status_code == 400
+    assert exec_response.json()["error_code"] == "QUERY_REJECTED_BY_ANALYZER"
+    
+    # 3. Manually approve workspace with show_results=True in metadata DB
+    app_db = app.state.app_db
+    async with app_db.get_app_db() as db:
+        ws = await db.get(Workspace, workspace_id)
+        ws.show_results = True
+        
+        query_data = await db.get(QueryData, ws.query_id)
+        query_data.status = "approved_with_results"
+        await db.commit()
+        
+    # 4. Configure mock result for SELECT query
+    mock_result.returns_rows = True
+    mock_row = MagicMock()
+    mock_row._mapping = {"order_id": 101, "amount": 250.0}
+    mock_result.fetchmany.return_value = [mock_row]
+    
+    # 5. Try executing again -> should succeed
+    exec_response_2 = await async_client.post(f"/api/execute_workspace/{workspace_id}")
+    assert exec_response_2.status_code == 200
+    resp_data = exec_response_2.json()
+    assert resp_data["response_type"] == "data"
+    assert resp_data["data"] == [{"order_id": 101, "amount": 250.0}]
+    assert "1 rows returned" in resp_data["message"]
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (test_workspaces.py)</summary>

```python
"""
Integration tests for workspaces router and service layer.
Verifies Workspace CRUD operations, ownership validation, and execution rules.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from app import app
from app_database.models import Workspace, QueryData

@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, servername, database_name):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result


async def create_user_and_login(async_client: AsyncClient, email: str, username: str) -> None:
    """
    Helper function to register and login a user.
    """
    register_data = {
        "username": username,
        "email": email,
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": email,
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)


@pytest.mark.asyncio
async def test_workspace_crud_operations(async_client: AsyncClient):
    """
    Tests creating, listing, updating, retrieving, and deleting workspaces.
    """
    # 1. Register and login
    await create_user_and_login(async_client, "user1@example.com", "user1")
    
    # 2. Create workspace
    create_payload = {
        "name": "My Workspace",
        "query": "SELECT * FROM my_table",
        "servername": "localhost",
        "database_name": "my_db"
    }
    create_response = await async_client.post("/api/workspaces", json=create_payload)
    assert create_response.status_code == 200, f"Failed to create workspace: {create_response.text}"
    create_data = create_response.json()
    assert create_data["success"] is True
    workspace_id = create_data["workspace_id"]
    
    # 3. Get workspace details
    detail_response = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["name"] == "My Workspace"
    assert detail_data["query"] == "SELECT * FROM my_table"
    assert detail_data["servername"] == "localhost"
    assert detail_data["database_name"] == "my_db"
    assert detail_data["status"] == "saved_in_workspace"  # Newly created queries default to saved_in_workspace
    
    # 4. List workspaces
    list_response = await async_client.get("/api/workspaces")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert len(list_data["workspaces"]) == 1
    assert list_data["workspaces"][0]["id"] == workspace_id
    
    # 5. Update workspace query
    update_payload = {
        "query": "SELECT count(*) FROM my_table",
        "status": "saved_in_workspace"
    }
    update_response = await async_client.put(f"/api/workspaces/{workspace_id}", json=update_payload)
    assert update_response.status_code == 200
    
    # Verify update
    detail_response_2 = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
    detail_data_2 = detail_response_2.json()
    assert detail_data_2["query"] == "SELECT count(*) FROM my_table"
    
    # 6. Delete workspace
    delete_response = await async_client.delete(f"/api/workspaces/{workspace_id}")
    assert delete_response.status_code == 200
    
    # Verify deletion
    list_response_2 = await async_client.get("/api/workspaces")
    assert len(list_response_2.json()["workspaces"]) == 0


@pytest.mark.asyncio
async def test_workspace_ownership_access_controls(async_client: AsyncClient):
    """
    Tests that a user cannot access, modify, or delete workspaces owned by another user.
    """
    # 1. Login user1 and create a workspace
    await create_user_and_login(async_client, "owner@example.com", "owner")
    create_payload = {
        "name": "Owner Workspace",
        "query": "SELECT 1",
        "servername": "localhost",
        "database_name": "db"
    }
    create_response = await async_client.post("/api/workspaces", json=create_payload)
    workspace_id = create_response.json()["workspace_id"]
    
    # 2. Login user2 (attacker)
    await create_user_and_login(async_client, "attacker@example.com", "attacker")
    
    # 3. Attacker tries to get details -> should fail
    get_response = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
    assert get_response.status_code == 403
    assert get_response.json()["error_code"] == "WORKSPACE_ACCESS_DENIED"
    
    # 4. Attacker tries to update -> should fail
    update_payload = {
        "query": "DROP TABLE users",
        "status": "saved_in_workspace"
    }
    update_response = await async_client.put(f"/api/workspaces/{workspace_id}", json=update_payload)
    assert update_response.status_code == 403
    assert update_response.json()["error_code"] == "WORKSPACE_ACCESS_DENIED"
    
    # 5. Attacker tries to delete -> should fail
    delete_response = await async_client.delete(f"/api/workspaces/{workspace_id}")
    assert delete_response.status_code == 403
    assert delete_response.json()["error_code"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_workspace_execution_rules(async_client: AsyncClient, mock_db_session):
    """
    Tests query execution workflows on a workspace.
    A workspace query must be approved and show_results must be True to execute.
    """
    mock_session, mock_result = mock_db_session
    
    # 1. Login and create workspace
    await create_user_and_login(async_client, "exec@example.com", "exec_user")
    create_payload = {
        "name": "Execution Workspace",
        "query": "SELECT * FROM orders",
        "servername": "localhost",
        "database_name": "sales_db"
    }
    create_response = await async_client.post("/api/workspaces", json=create_payload)
    workspace_id = create_response.json()["workspace_id"]
    
    # 2. Try to execute immediately (default is saved_in_workspace/unapproved) -> should fail with 400 Bad Request
    exec_response = await async_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response.status_code == 400
    assert exec_response.json()["error_code"] == "QUERY_REJECTED_BY_ANALYZER"
    
    # 3. Manually approve workspace with show_results=True in metadata DB
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        ws.show_results = True
        
        query_data = await db.get(QueryData, ws.query_id)
        query_data.status = "approved_with_results"
        await db.commit()
        
    # 4. Configure mock result for SELECT query
    mock_result.returns_rows = True
    mock_row = MagicMock()
    mock_row._mapping = {"order_id": 101, "amount": 250.0}
    mock_result.fetchmany.return_value = [mock_row]
    
    # 5. Try executing again -> should succeed
    exec_response_2 = await async_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response_2.status_code == 200
    resp_data = exec_response_2.json()
    assert resp_data["response_type"] == "data"
    assert resp_data["data"] == [{"order_id": 101, "amount": 250.0}]
    assert "1 rows returned" in resp_data["message"]

```
</details>




### 📂 Kategori 9: Proje Yapılandırma ve Kök Dosyalar (Configuration & Root Setup)
---

#### <a name="web_apidependenciespy"></a> `web_api/dependencies.py`
**Açıklama:** FastAPI bağımlılık enjeksiyon sistemini güncelleyerek eski Redis parola cache ve şifreleme mekanizmalarını kaldıran ve stateless asenkron oturum yönetimini kuran modül.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/dependencies.py b/web_api/dependencies.py
index 6ae78ad..d586ca3 100644
--- a/web_api/dependencies.py
+++ b/web_api/dependencies.py
@@ -1,68 +1,52 @@
 """
-Ortak Dependency Injection Fonksiyonları
-Tüm router'lar bu fonksiyonları kullanarak app.state'ten instance'ları alır
+Common Dependency Injection Functions
+All routers use these functions to retrieve service instances from app.state.
 """
 from fastapi import Request
 from fastapi import Depends, HTTPException, status
-from cryptography.fernet import Fernet
 
 from app_database.app_database import AppDatabase
 from database_provider import DatabaseProvider
 from authentication.services import get_current_user
-from app_database.models import Workspace, QueryData, User
+from app_database.models import Workspace, User
 
 from query_execution.services import QueryService
 from workspaces.services import WorkspaceService
+from workspaces.exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError
 
 def get_app_db(request: Request) -> AppDatabase:
     """
-    AppDatabase instance'ını döndürür.
-    Kullanım: app_db: AppDatabase = Depends(get_app_db)
+    Returns the AppDatabase instance.
+    Usage: app_db: AppDatabase = Depends(get_app_db)
     """
     return request.app.state.app_db
 
 
 def get_db_provider(request: Request) -> DatabaseProvider:
     """
-    DatabaseProvider instance'ını döndürür.
-    Kullanım: db_provider: DatabaseProvider = Depends(get_db_provider)
+    Returns the DatabaseProvider instance.
+    Usage: db_provider: DatabaseProvider = Depends(get_db_provider)
     """
     return request.app.state.db_provider
 
 
-from session.session_cache import SessionCache
-
-def get_session_cache(request: Request) -> SessionCache:
-    """
-    SessionCache instance'ını döndürür (kullanıcı şifrelerini geçici saklar).
-    Kullanım: session_cache: SessionCache = Depends(get_session_cache)
-    """
-    return request.app.state.session_cache
-
-
-def get_fernet(request: Request) -> Fernet:
-    """
-    Fernet şifreleme instance'ını döndürür.
-    Kullanım: fernet: Fernet = Depends(get_fernet)
-    """
-    return request.app.state.fernet
+# removed session cache and fernet dependencies as password caching is eliminated
 
 def get_query_service(request: Request) -> QueryService:
     """
-    QueryService instance'ını döndürür.
-    Kullanım: query_service: QueryService = Depends(get_query_service)
+    Returns the QueryService instance.
+    Usage: query_service: QueryService = Depends(get_query_service)
     """
     app_db = get_app_db(request)
     db_provider = get_db_provider(request)
     notification_service = get_notification_service(request)
     return QueryService(database_provider=db_provider, app_db=app_db, notification_service=notification_service)
 
-from workspaces.services import WorkspaceService
 
 def get_workspace_service(request: Request) -> WorkspaceService:
     """
-    WorkspaceService instance'ını döndürür.
-    Kullanım: workspace_service: WorkspaceService = Depends(get_workspace_service)
+    Returns the WorkspaceService instance.
+    Usage: workspace_service: WorkspaceService = Depends(get_workspace_service)
     """
     app_db = get_app_db(request)
     return WorkspaceService(app_db=app_db)
@@ -71,8 +55,8 @@ from admin.services import AdminService
 
 def get_admin_service(request: Request) -> AdminService:
     """
-    AdminService instance'ını döndürür.
-    Kullanım: admin_service: AdminService = Depends(get_admin_service)
+    Returns the AdminService instance.
+    Usage: admin_service: AdminService = Depends(get_admin_service)
     """
     app_db = get_app_db(request)
     db_provider = get_db_provider(request)
@@ -93,9 +77,9 @@ async def ensure_owner(workspace_id: int,
     async with app_db.get_app_db() as db:
         ws = await db.get(Workspace, workspace_id)
         if not ws:
-            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
+            raise WorkspaceNotFoundError("Workspace not found")
         if ws.user_id != current_user.id:
-            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't own this workspace.")
+            raise WorkspaceAccessDeniedError("You don't own this workspace.")
         return ws
 
 
@@ -103,7 +87,7 @@ from notification import NotificationService
 
 def get_notification_service(request: Request) -> NotificationService:
     """
-    NotificationService instance'ını döndürür.
-    Kullanım: notification_service: NotificationService = Depends(get_notification_service)    
+    Returns the NotificationService instance.
+    Usage: notification_service: NotificationService = Depends(get_notification_service)    
     """
     return NotificationService()
\ No newline at end of file
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (dependencies.py)</summary>

```python
"""
Common Dependency Injection Functions
All routers use these functions to retrieve service instances from app.state.
"""
from fastapi import Request
from fastapi import Depends, HTTPException, status

from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from authentication.services import get_current_user
from app_database.models import Workspace, User

from query_execution.services import QueryService
from workspaces.services import WorkspaceService
from workspaces.exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError

def get_app_db(request: Request) -> AppDatabase:
    """
    Returns the AppDatabase instance.
    Usage: app_db: AppDatabase = Depends(get_app_db)
    """
    return request.app.state.app_db


def get_db_provider(request: Request) -> DatabaseProvider:
    """
    Returns the DatabaseProvider instance.
    Usage: db_provider: DatabaseProvider = Depends(get_db_provider)
    """
    return request.app.state.db_provider


# removed session cache and fernet dependencies as password caching is eliminated

def get_query_service(request: Request) -> QueryService:
    """
    Returns the QueryService instance.
    Usage: query_service: QueryService = Depends(get_query_service)
    """
    app_db = get_app_db(request)
    db_provider = get_db_provider(request)
    notification_service = get_notification_service(request)
    return QueryService(database_provider=db_provider, app_db=app_db, notification_service=notification_service)


def get_workspace_service(request: Request) -> WorkspaceService:
    """
    Returns the WorkspaceService instance.
    Usage: workspace_service: WorkspaceService = Depends(get_workspace_service)
    """
    app_db = get_app_db(request)
    return WorkspaceService(app_db=app_db)

from admin.services import AdminService

def get_admin_service(request: Request) -> AdminService:
    """
    Returns the AdminService instance.
    Usage: admin_service: AdminService = Depends(get_admin_service)
    """
    app_db = get_app_db(request)
    db_provider = get_db_provider(request)
    return AdminService(app_db=app_db, db_provider=db_provider)


async def admin_required(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: ensures current_user is admin."""
    if not current_user or not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


async def ensure_owner(workspace_id: int,
                       current_user: User = Depends(get_current_user),
                       app_db: AppDatabase = Depends(get_app_db)) -> Workspace:
    """Dependency: ensures the current_user is the owner of the workspace. Returns the Workspace."""
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        if not ws:
            raise WorkspaceNotFoundError("Workspace not found")
        if ws.user_id != current_user.id:
            raise WorkspaceAccessDeniedError("You don't own this workspace.")
        return ws


from notification import NotificationService

def get_notification_service(request: Request) -> NotificationService:
    """
    Returns the NotificationService instance.
    Usage: notification_service: NotificationService = Depends(get_notification_service)    
    """
    return NotificationService()
```
</details>



#### <a name="web_apientrypointsh"></a> `web_api/entrypoint.sh`
**Açıklama:** Docker container başlatma betiğini, asenkron veritabanı migrasyonlarını ve uvicorn asenkron sunucu işçilerini güvenle başlatacak şekilde güncellenen betik.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/entrypoint.sh b/web_api/entrypoint.sh
index 5a69086..c798812 100644
--- a/web_api/entrypoint.sh
+++ b/web_api/entrypoint.sh
@@ -1,7 +1,7 @@
 #!/bin/bash
 set -e
 
-# Veritabanı bağlantısını bekle (Retry mekanizması)
+# Wait for database connection (Retry mechanism)
 echo "Waiting for SQL Server to be ready..."
 max_retries=30
 count=0
@@ -21,5 +21,5 @@ if [ $count -eq $max_retries ]; then
     exit 1
 fi
 
-# Uygulamayı başlat
+# Start the application
 exec "$@"
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (entrypoint.sh)</summary>

```bash
#!/bin/bash
set -e

# Wait for database connection (Retry mechanism)
echo "Waiting for SQL Server to be ready..."
max_retries=30
count=0
while [ $count -lt $max_retries ]; do
    if python create_db.py; then
        echo "Database initialized successfully."
        break
    else
        echo "Database not ready yet. Retrying in 2 seconds... ($((count+1))/$max_retries)"
        sleep 2
        count=$((count+1))
    fi
done

if [ $count -eq $max_retries ]; then
    echo "Error: Could not connect to database after $max_retries attempts."
    exit 1
fi

# Start the application
exec "$@"

```
</details>



#### <a name="gitignore"></a> `.gitignore`
**Açıklama:** `.venv`, asenkron sqlite lokal test veritabanları, `.idea` gibi IDE ve sanal ortam dizinlerini git takibinden hariç tutacak şekilde güncellenen yapılandırma dosyası.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/.gitignore b/.gitignore
index 4c99967..f17a03b 100644
--- a/.gitignore
+++ b/.gitignore
@@ -30,3 +30,10 @@ htmlcov/
 # Database files / logs
 *.sqlite3
 *.log
+
+# Node dependencies
+node_modules/
+frontend/node_modules/
+
+# Python virtual environments
+.venv/
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (.gitignore)</summary>

```python
# Bytecode and caches (already present but keep concise)
__pycache__/
*.py[cod]
*.pyc

# Virtual environments (your project has `myenv/`)
myenv/
env/

# Distribution / packaging
build/
dist/
pip-wheel-metadata/
*.egg-info/r

# Testing / coverage
.pytest_cache/
.coverage
htmlcov/

# IDEs / editors
.vscode/
.idea/

# Environment variables / secrets
.env
.env.*
!.env.example

# Database files / logs
*.sqlite3
*.log

# Node dependencies
node_modules/
frontend/node_modules/

# Python virtual environments
.venv/

```
</details>



#### <a name="envexample"></a> `.env.example`
**Açıklama:** Merkezi servis hesabı (`CENTRAL_DB_USER` / `CENTRAL_DB_PASSWORD`) gibi kritik parametreleri içeren ve kurulum için kılavuzluk eden örnek çevre değişkenleri şablonu.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/.env.example b/.env.example
index 6b2f530..75906b1 100644
--- a/.env.example
+++ b/.env.example
@@ -1,4 +1,4 @@
-﻿# =============================================================================
+# =============================================================================
 # WebQuery Environment Configuration
 # =============================================================================
 # Bu dosyayı .env olarak kopyalayın ve değerleri düzenleyin
@@ -13,6 +13,12 @@
 DB_USER=sa
 DB_PASSWORD=YourStrongPassword123!
 
+# Target Database Central Service Account (Merkezi Hesap)
+# Hedef veritabanlarında sorgu çalıştırmak için kullanılan merkezi servis kullanıcısı
+CENTRAL_DB_USER=webquery_service
+CENTRAL_DB_PASSWORD=YourStrongServicePassword123!
+
+
 # SQL Server Instance'ları (virgülle ayrılmış liste)
 # Birden fazla server için: SERVER1,SERVER2,SERVER3
 # Tek server için: localhost veya SERVER_NAME
@@ -128,6 +134,20 @@ REDIS_DB=0
 # Yüklenecek environment dosyası (default: .env)
 ENV_FILE=.env
 
+# Uygulama çalışma modu (True: geliştirme, False: production)
+DEBUG=True
+
+# =============================================================================
+# SECURITY
+# =============================================================================
+
+# İzin verilen CORS originleri (Virgülle ayırın, production'da * KULLANMAYIN)
+# Örnek: http://localhost:3000,https://app.yourdomain.com
+CORS_ALLOWED_ORIGINS=*
+
+# Çerez güvenliği (Production ortamında True olmalıdır)
+COOKIE_SECURE=False
+
 # =============================================================================
 # SERVER CONFIGURATION
 # =============================================================================
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (.env.example)</summary>

```python
# =============================================================================
# WebQuery Environment Configuration
# =============================================================================
# Bu dosyayı .env olarak kopyalayın ve değerleri düzenleyin
# Örnek: cp .env.example .env

# =============================================================================
# SQL SERVER CONFIGURATION
# =============================================================================

# SQL Server Kullanıcı Bilgileri
# Admin hesabı ile bağlanmak için kullanılır (master database erişimi için)
DB_USER=sa
DB_PASSWORD=YourStrongPassword123!

# Target Database Central Service Account (Merkezi Hesap)
# Hedef veritabanlarında sorgu çalıştırmak için kullanılan merkezi servis kullanıcısı
CENTRAL_DB_USER=webquery_service
CENTRAL_DB_PASSWORD=YourStrongServicePassword123!


# SQL Server Instance'ları (virgülle ayrılmış liste)
# Birden fazla server için: SERVER1,SERVER2,SERVER3
# Tek server için: localhost veya SERVER_NAME
SQL_SERVER_NAMES=localhost

# =============================================================================
# APPLICATION DATABASE
# =============================================================================

# Uygulama veritabanı connection string (opsiyonel - override için)
# Belirtilmezse DB_USER, DB_PASSWORD ve localhost kullanılarak otomatik oluşturulur
# APP_DATABASE_URL=mssql+aioodbc://sa:password@localhost/dba_application_db?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&connection timeout=30

# =============================================================================
# ENGINE CACHE CONFIGURATION
# =============================================================================

# Engine Cache temizleme aralığı (saniye)
# Kullanılmayan engine'lerin bellekten silinme süresi
# Default: 1800 (30 dakika)
ENGINE_CACHE_TTL_SECONDS=1800

# =============================================================================
# JWT AUTHENTICATION
# =============================================================================

# JWT Secret Key (ÖNEMLİ: Production'da mutlaka değiştirilmeli!)
# Güçlü, rastgele bir anahtar kullanın
# Örnek: openssl rand -hex 32
SECRET_KEY=your-secret-key-here-change-in-production

# JWT Algoritması
JWT_ALGORITHM=HS256

# JWT Token Geçerlilik Süreleri (dakika)
# Access token ne kadar süre geçerli olsun
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Cookie'de saklanan token ne kadar süre geçerli olsun (saniye)
COOKIE_TOKEN_EXPIRE_MINUTES=86400

# Session timeout süresi (dakika)
# Kullanıcı bu süre boyunca aktif değilse session sonlanır
SESSION_TIMEOUT_MINUTES=60

# =============================================================================
# RATE LIMITING
# =============================================================================

# Login/Register endpoint rate limit
# Format: "istek_sayısı/zaman_birimi"
# Örnek: "3/minute" = dakikada 3 istek
RATE_LIMITER=3/minute

# Query execution endpoint rate limit
QUERY_RATE_LIMITER=10/minute

# =============================================================================
# QUERY EXECUTION LIMITS
# =============================================================================

# Tek seferde çalıştırılabilecek maksimum query sayısı
MULTIPLE_QUERY_COUNT=10

# Bu sayıdan fazla satır dönerse warning loglanır
MAX_ROW_COUNT_WARNING=10000

# Response'da döndürülecek maksimum satır sayısı
# Daha fazla satır varsa kesilir ve kullanıcıya bilgi verilir
MAX_ROW_COUNT_LIMIT=1000

# =============================================================================
# NOTIFICATION (WEBHOOK)
# =============================================================================

# Slack bildirimi almak için slack webhook adresiniz (Eski/Basit entegrasyon)
SLACK_URL=your-slack-webhook-url

# =============================================================================
# SLACK INTEGRATION (INTERACTIVE BOT)
# =============================================================================

# Slack Bot Token (xoxb-...)
# Mesaj göndermek ve API çağrıları yapmak için kullanılır
SLACK_BOT_TOKEN=xoxb-your-bot-token

# Slack App Token (xapp-...)
# Socket Mode ile olayları dinlemek için kullanılır
SLACK_APP_TOKEN=xapp-your-app-token

# Admin Kanal ID'si
# Onay mesajlarının gönderileceği kanal ID'si (örn: C0123456789)
SLACK_ADMIN_CHANNEL=C0123456789

# =============================================================================
# REDIS CONFIGURATION
# =============================================================================

# Redis Sunucu Adresi
# Docker üzerinden çalıştırırken 'redis', lokalde çalıştırırken 'localhost'
REDIS_HOST=localhost

# Redis Sunucu Portu
REDIS_PORT=6379

# Redis Veritabanı Numarası (0-15 arası)
REDIS_DB=0

# =============================================================================
# GENERAL
# =============================================================================

# Yüklenecek environment dosyası (default: .env)
ENV_FILE=.env

# Uygulama çalışma modu (True: geliştirme, False: production)
DEBUG=True

# =============================================================================
# SECURITY
# =============================================================================

# İzin verilen CORS originleri (Virgülle ayırın, production'da * KULLANMAYIN)
# Örnek: http://localhost:3000,https://app.yourdomain.com
CORS_ALLOWED_ORIGINS=*

# Çerez güvenliği (Production ortamında True olmalıdır)
COOKIE_SECURE=False

# =============================================================================
# SERVER CONFIGURATION
# =============================================================================

# Uygulamanın çalışacağı host ve port
# Default: 0.0.0.0 (tüm interface'ler)
# DİKKAT: Docker içinde çalışırken erişilebilir olması için 0.0.0.0 olmalıdır.
# Localhost yaparsanız dışarıdan erişilemez!
HOST=0.0.0.0

# Uygulamanın çalışacağı port
# Default: 8080
PORT=8080

# Uygulamanın eş zamanlı olarak çalıştıracağı Uvicorn/Gunicorn worker sayısı
# Çok çekirdekli sistemlerde performansı artırmak için çekirdek sayısına göre artırılabilir (Örn: 4)
# Default: 1
WORKERS=1

```
</details>



#### <a name="readmemd"></a> `README.md`
**Açıklama:** Projenin tüm B2B güvenlik mimarisini, dizin yapısını, connection pooling mantığını, AST risk analiz katmanını ve test çalıştırma adımlarını detaylıca anlatan İngilizce rehber.

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/README.md b/README.md
index cc129fa..d44d2c7 100644
--- a/README.md
+++ b/README.md
@@ -1,331 +1,175 @@
-## WebQuery
+# WebQuery - Enterprise SQL Execution Platform
 
 ![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
 ![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
 ![License](https://img.shields.io/badge/license-MIT-green)
+![Architecture](https://img.shields.io/badge/architecture-modular-orange)
 
-Çoklu veritabanı desteği ile sorgu analizi ve güvenli yürütme özellikleri sunan FastAPI tabanlı bir uygulama. MSSQL, MySQL ve PostgreSQL veritabanlarına bağlanabilir. Kimlik doğrulama (JWT), hız sınırlama, çoklu sorgu yürütme ve risk analizi içerir.
-
-## Özellikler
-- **Çoklu Veritabanı Desteği**: MSSQL, MySQL, PostgreSQL
-- **Gelişmiş Connection Pooling**: `EngineCache` ile sunucu kaynaklarını yormayan akıllı bağlantı yönetimi (LRU, TTL, Active Connection Check)
-- **Risk Analizi ve Onay Mekanizması**: Tehlikeli sorgular için otomatik tespit ve Admin onay süreci
-- **Workspace Yönetimi**: Sorguları kaydetme, düzenleme ve paylaşma
-- JWT ile kullanıcı doğrulama ve oturum yönetimi
-- Hız sınırlama (slowapi)
-- Otomatik driver seçimi ve connection string yönetimi
-
-## Mimari ve Teknolojiler
-- **Backend**: FastAPI 0.116.x, Uvicorn
-- **ORM**: SQLAlchemy 2.x (async)
-- **Drivers**: 
-  - MSSQL: `aioodbc` / `pyodbc`
-  - MySQL: `aiomysql`
-  - PostgreSQL: `asyncpg`
-- **Güvenlik**: python-jose (JWT), cryptography (Fernet), bcrypt
-- **Konfigürasyon**: python-dotenv
-
-## Proje Yapısı
-Modüler bir mimari benimsenmiştir:
-- `app_database/`: Uygulama içi veritabanı (User, Log, Workspace) modelleri ve işlemleri
-- `database_provider/`: Hedef veritabanlarına (MSSQL, MySQL, PG) bağlantı yönetimi (`EngineCache`)
-- `query_execution/`: Sorgu çalıştırma, risk analizi (`QueryAnalyzer`) ve loglama
-- `admin/`: Yönetici onay mekanizması ve işlemleri
-- `workspaces/`: Kullanıcı çalışma alanları yönetimi
-- `authentication/`: Login, register ve token işlemleri
-- `middlewares/`: Auth ve rate limiting middleware'leri
-
-## Gelişmiş Özellikler Detayı
-
-### 1. Akıllı Engine Cache (Connection Management)
-Uygulama, veritabanı bağlantılarını `EngineCache` sınıfı ile yönetir. Bu yapı, "Web Query Tool" senaryosu için özel olarak optimize edilmiştir:
-- **Pool Size = 0**: Sunucuda boşta (idle) bağlantı tutulmaz. Her sorgu bittiğinde bağlantı kapatılır.
-- **Max Overflow = 20**: Anlık yoğunlukta 20 eşzamanlı bağlantıya kadar izin verilir.
-- **LRU Eviction**: Cache dolduğunda en az kullanılan engine silinir.
-- **TTL Cleanup**: Belirli bir süre kullanılmayan engine'ler arka planda temizlenir.
-- **Active Check**: Temizlik sırasında, o an sorgu çalıştıran engine'ler (`checkedout > 0`) korunur, işlem yarıda kesilmez.
-
-### 2. Sorgu Risk Analizi (Query Analyzer)
-Her sorgu çalıştırılmadan önce `QueryAnalyzer` tarafından taranır. Riskler 4 seviyede değerlendirilir:
-1.  **SQL Injection**: `UNION SELECT`, `OR 1=1`, yorum satırları (`--`, `/*`) vb.
-2.  **DDL (Yapısal Değişiklik)**: `DROP`, `CREATE`, `ALTER`, `TRUNCATE`.
-3.  **Riskli DML**: `WHERE` koşulu olmayan `DELETE` veya `UPDATE` işlemleri.
-4.  **Performans**: 3'ten fazla `JOIN`, `CROSS JOIN`, `LIKE '%...%'`, büyük `LIMIT` + `ORDER BY`.
-
-**Onay Mekanizması**: Riskli bulunan sorgular (Admin değilse) doğrudan çalıştırılmaz. "Onay Bekliyor" durumuna alınır. Adminler bu sorguları inceleyip onaylayabilir veya reddedebilir.
-
-### 3. Workspace Sistemi
-Kullanıcılar sorgularını "Workspace" olarak kaydedebilir. Her workspace:
-- Bir SQL sorgusu içerir.
-- Sorgunun son çalışma durumu ve risk seviyesini tutar.
-- Admin onayı gerekiyorsa durumunu takip eder.
-
-## Gereksinimler
-
-### Python ve Temel Bağımlılıklar
-- Python 3.11+
-- `requirements.txt` içindeki tüm paketler
-
-### Veritabanı Driver'ları (Zorunlu)
-
-Kullanmayı planladığınız veritabanı teknolojisine göre ilgili driver'ların sisteminizde kurulu olması **zorunludur**:
-
-#### **MSSQL (Microsoft SQL Server)**
-- **ODBC Driver 18 for SQL Server** (sistem seviyesinde kurulu olmalı)
-- Windows: [Microsoft Download Center](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
-- Linux: [Linux ODBC Driver Installation](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
-- Python paketleri: `aioodbc`, `pyodbc` (requirements.txt'te mevcut)
-
-#### **MySQL**
-- **MySQL Client Libraries** (opsiyonel, bazı sistemlerde gerekebilir)
-- Python paketleri: `aiomysql`, `PyMySQL` (requirements.txt'te mevcut)
-
-#### **PostgreSQL**
-- **PostgreSQL Client** (asyncpg için genellikle gerekli değil)
-- Python paketi: `asyncpg` (requirements.txt'te mevcut)
-
-### Veritabanı Erişimi
-- İlgili veritabanı sunucusuna erişim (kullanıcı adı/şifre)
-- Gerekli izinler (SELECT, INSERT vb.)
-
-## Hızlı Başlangıç (Geliştirme)
-1) Depoyu klonla
-```powershell
-git clone https://github.com/erdemdnmz2/WebQuery
-cd WebQuery
-```
+WebQuery is a powerful, secure, and production-ready enterprise SQL execution platform built on FastAPI. It allows teams to safely run, share, and audit queries across multiple target databases (MSSQL, MySQL, PostgreSQL). 
 
-2) Sanal ortam ve bağımlılıklar
-```powershell
-python -m venv venv
-.\venv\Scripts\pip.exe install -r requirements.txt
-```
+Designed with zero-trust B2B security principles, WebQuery eliminates the need to store individual database credentials by employing a **Centralized Service Account Architecture** coupled with advanced AST-based query analysis, global error translation, and a real-time request tracing system.
 
-3) Ortam dosyası
-- `.env.example` dosyasını kopyalayıp değerleri düzenleyin:
-```powershell
-Copy-Item .env.example .env
-```
-- Bu dosyada tanımlı değişkenler: DB_USER, DB_PASSWORD, SQL_SERVER_NAMES, SECRET_KEY, JWT ayarları, rate limit, sorgu limitleri, HOST ve PORT (tam liste için `.env.example`’a bakın).
+---
 
-4) Çalıştırma (dev)
-- Varsayılan olarak `.env` okunur; isterseniz özel dosya seçebilirsiniz:
-```powershell
-$env:ENV_FILE = ".env"          # veya ".env.staging" / ".env.production"
-.\venv\Scripts\python.exe -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
-```
+## Architecture & Core Features
 
-## Production Çalıştırma (Önerilen Yol)
-1) Kodu sunucuya kopyalayın (ENV dosyaları hariç)
-2) Sunucuda `.env.production` oluşturun ve güvenli değerleri yazın
-3) Sunucuda bağımlılıkları kurun ve uygulamayı başlatın
+### 1. Centralized Service Account Architecture (Zero-Trust Security)
+* **No User-Stored Credentials:** Individual database passwords are never requested, stored, or cached (removing any risk of credential leaks).
+* **Central Credentials:** Connections to target databases are established dynamically using highly restricted central service credentials (`CENTRAL_DB_USER` and `CENTRAL_DB_PASSWORD`) defined securely in the environment.
+* **Granular Audit Logging:** Although execution is centralized, every query is strictly audited. The platform logs the exact user, trace ID, timestamp, and machine name for every action in the `ActionLogging` table.
+* **Stateless JWT Authorization:** Session management is completely stateless. Authenticated requests use cryptographically signed JWT tokens stored in secure, HttpOnly cookies, completely eliminating the need for a Redis credential cache.
 
-```powershell
-python -m venv venv
-.\venv\Scripts\pip.exe install -r requirements.txt
+### 2. Intelligent Connection Pooling & Engine Cache
+* **Zero Idle Connections:** Connection engines to target databases are managed by an advanced `EngineCache`. It sets `pool_size=0` to release idle server-side connections immediately after query execution.
+* **Max Overflow Handling:** Dynamically allows up to 20 concurrent connections during peak query bursts.
+* **LRU Eviction & TTL Cleanup:** Least Recently Used (LRU) engines are evicted when the cache limit is reached. A background task cleans up expired engines based on a configurable Time-to-Live (TTL), while ensuring active, currently executing engines (`checkedout > 0`) are safely protected.
 
-# Uygulamaya hangi .env dosyasını kullanacağını söyleyin
-$env:ENV_FILE = ".env.production"
-.\venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
-```
+### 3. Dynamic SQL Risk Analysis (AST Parsing)
+Before execution, every query is analyzed by a custom `QueryAnalyzer` utilizing the `sqlglot` library for abstract syntax tree (AST) parsing. It supports target-specific SQL dialects (`tsql`, `mysql`, `postgres`) and grades queries into four risk levels:
+1. **SQL Injection:** Checks for structural anomalies (e.g., `UNION SELECT`, `OR 1=1`, inline comments).
+2. **DDL (Structural Modifications):** Detects `DROP`, `CREATE`, `ALTER`, `TRUNCATE`.
+3. **Risky DML:** Blocks `DELETE` or `UPDATE` statements lacking a `WHERE` clause.
+4. **Performance Anomalies:** Flagging queries with more than 3 `JOIN`s, `CROSS JOIN`s, un-indexed `LIKE '%...%'`, or massive `LIMIT` operations.
 
-> Not: Docker kullanacaksanız gizli bilgileri imajın içine koymayın. Konfigürasyonu runtime’da verin:
-```powershell
-docker run --env-file C:\path\to\.env.production -p 8000:8000 yourimage:tag
-```
+> [!NOTE]
+> **Approval Workflow:** Risky queries submitted by non-admin users are automatically put into a "Pending Approval" state. Authorized administrators can inspect, approve, or reject these queries via Slack or the Admin Panel.
+
+### 4. Advanced Request Tracing & Auditing Middleware
+* **Trace ID Generation:** The `TraceMiddleware` automatically assigns a unique UUID (Trace ID) to every incoming HTTP request and attaches it as the `X-Request-ID` header in the response.
+* **Context-Aware Auditing:** Utilizes Python `contextvars` to dynamically propagate the active Trace ID and authenticated User ID to all logging handlers. Every log entry automatically prints the trace context without passing request objects down the call stack.
 
-## Docker ile Çalıştırma
+### 5. Unified Error Translation (Exception Translation Pattern)
+* **Modular Domain Exceptions:** Low-level infrastructure, driver, or database errors (such as SQLAlchemy or network exceptions) are caught at the service boundary and translated into domain-specific exceptions (e.g., `WorkspaceNotFoundError`, `QueryExecutionError`, `UserAlreadyExistsError`).
+* **Global Handling:** A centralized exception handler intercepts all domain exceptions, logs their detailed tracebacks internally, and returns a clean, secure, and standardized JSON response containing `success: false`, the enterprise `error_code`, a safe client-facing `message`, and the associated `trace_id`.
 
-Proje, tüm bağımlılıkları (MSSQL, Redis, Nginx) içeren bir `docker-compose.yml` ile birlikte gelir. Tek komutla tüm sistemi ayağa kaldırabilirsiniz.
+---
+
+## Directory Structure
+
+WebQuery adopts a clean, modular package architecture:
 
-### Servis Mimarisi
 ```
-                    ┌─────────────┐
-         :80        │    Nginx    │
-  Kullanıcı ──────► │  (Reverse   │
-                    │   Proxy)    │
-                    └──────┬──────┘
-                   /               \
-            /api /                   \ /
-    ┌───────▼──────┐           ┌─────▼───────┐
-    │  Backend     │           │  Frontend   │
-    │  (FastAPI)   │           │  (React +   │
-    │  :8080       │           │   Nginx)    │
-    └──┬───────┬───┘           └─────────────┘
-       │       │
-  ┌────▼──┐ ┌──▼────┐
-  │ MSSQL │ │ Redis │
-  │ :1433 │ │ :6379 │
-  └───────┘ └───────┘
+web_api/
+│
+├── common/                  # Centralized utilities (Exceptions, Logging, Rate Limiting)
+│   ├── exceptions.py        # BaseServiceException and global hierarchy
+│   ├── logging_config.py    # Custom contextvars logger formatting
+│   └── limiter.py           # Consolidated, shared slowapi Limiter
+│
+├── middlewares/             # FastAPI Middlewares (Trace ID, Stateless Auth)
+│   ├── trace_middleware.py  # Request ID generation and log context binding
+│   └── auth_middleware.py   # JWT validation and user context binding
+│
+├── database_provider/       # Connection management and target DB sessions
+│   ├── database.py          # DatabaseProvider session generator
+│   ├── engine_cache.py      # LRU and TTL-based SQLAlchemy connection engine caching
+│   └── config.py            # Central and target database driver configurations
+│
+├── query_execution/         # SQL execution, AST risk analysis, and audit logging
+│   ├── services.py          # QueryService with SELECT and DML execution safety
+│   └── router.py            # Query execution HTTP entrypoints
+│
+├── workspaces/              # User workspace management (Saved queries and metadata)
+├── authentication/          # User registration, stateless login, and cookies
+├── admin/                   # Administrative actions (Database registration, manual approvals)
+└── tests/                   # Test Suite (Unit and Integration tests with SQLite in-memory)
 ```
 
-### Ön Gereksinimler
-- [Docker](https://docs.docker.com/get-docker/) (20.10+)
-- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)
+---
+
+## Driver Requirements
+
+To connect to target databases, the corresponding system-level drivers and client libraries must be installed on your host machine:
+
+### **Microsoft SQL Server (MSSQL)**
+* **ODBC Driver 18 for SQL Server** (System-level installation is mandatory).
+  * Windows: [Microsoft ODBC Download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
+  * Linux/macOS: [ODBC Installation Guide](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
+  * Python packages: `aioodbc`, `pyodbc` (included in requirements)
+
+### **MySQL**
+* Python packages: `aiomysql`, `PyMySQL` (included in requirements)
+
+### **PostgreSQL**
+* Python package: `asyncpg` (included in requirements)
+
+---
+
+## Quick Start (Development)
 
-### Hızlı Başlangıç (Docker)
-1) `.env` dosyasını oluşturun:
+### 1. Clone the Repository
 ```bash
-cp .env.example .env
-# .env dosyasını düzenleyip en azından DB_PASSWORD ayarlayın
+git clone https://github.com/erdemdnmz2/WebQuery
+cd WebQuery
 ```
 
-2) Tüm servisleri başlatın:
+### 2. Set Up Virtual Environment and Install Dependencies
 ```bash
-docker-compose up -d --build
+python -m venv .venv
+source .venv/bin/activate  # On Windows: .venv\Scripts\activate
+pip install -r web_api/requirements.txt
 ```
 
-3) Logları izleyin:
+### 3. Configure Environment Variables
+Copy the template `.env.example` to `.env` and configure your credentials:
 ```bash
-docker-compose logs -f web    # Backend logları
-docker-compose logs -f        # Tüm servisler
+cp .env.example .env
 ```
 
-4) Erişim:
-   - **Uygulama**: http://localhost (Nginx üzerinden)
-   - **API**: http://localhost/api
-   - **Health Check**: http://localhost/api/health
+Ensure the following variables are set correctly:
+* `DB_USER` and `DB_PASSWORD` (For the WebQuery metadata application database)
+* `CENTRAL_DB_USER` and `CENTRAL_DB_PASSWORD` (Central service account for target database executions)
+* `SECRET_KEY` (Strong secret key for JWT signatures)
+* `SQL_SERVER_NAMES` (Comma-separated list of target servers, e.g., `localhost`)
 
-### Servisler ve Portlar
+### 4. Initialize Database
+Initialize the SQLite metadata database (or MSSQL if configured):
+```bash
+cd web_api
+python create_db.py
+```
 
-| Servis | Image | Port | Açıklama |
-|--------|-------|------|----------|
-| `nginx` | nginx:latest | **80** → 80 | Reverse proxy (frontend + API) |
-| `web` | Dockerfile (root) | **8080** → 8080 | FastAPI backend |
-| `frontend` | Dockerfile (frontend/) | - | React SPA (Nginx ile serve) |
-| `db` | mssql/server:2022 | **1433** → 1433 | SQL Server veritabanı |
-| `redis` | redis:alpine | **6379** → 6379 | Session/cache store |
+### 5. Run the Application
+Start the Uvicorn development server:
+```bash
+python app.py
+```
+The API will be accessible at `http://localhost:8080` with interactive Swagger docs at `http://localhost:8080/docs`.
 
-### Docker Ortam Değişkenleri
-`docker-compose.yml` aşağıdaki değişkenleri `.env` dosyasından okur:
+---
 
-| Değişken | Docker Default | Açıklama |
-|----------|---------------|----------|
-| `DB_PASSWORD` | *(zorunlu)* | SQL Server SA şifresi |
-| `DB_USER` | `sa` | SQL Server kullanıcısı |
-| `PORT` | `8080` | Backend port |
-| `HOST` | `0.0.0.0` | Backend bind adresi |
+## Frontend Setup (Development)
 
-> **Önemli:** `DB_PASSWORD` güçlü bir şifre olmalıdır (SQL Server 2022 gereksinimleri: en az 8 karakter, büyük-küçük harf, rakam veya özel karakter).
+The WebQuery frontend is a modern React application built with Vite, TypeScript, and Tailwind CSS.
 
-### Yararlı Docker Komutları
+### 1. Navigate to the Frontend Directory
 ```bash
-# Servisleri durdur
-docker-compose down
-
-# Servisleri durdur ve veritabanı verisini sil
-docker-compose down -v
-
-# Sadece backend'i yeniden derle
-docker-compose up -d --build web
+cd frontend
+```
 
-# Container'a bağlan (debug)
-docker-compose exec web bash
+### 2. Install Dependencies
+```bash
+npm install
 ```
 
-## Ortam Değişkenleri (dotenv)
-- Uygulama başında `app.py` içinde şu mantık vardır:
-  - `ENV_FILE` değişkeni set edilmişse o dosya yüklenir (örn: `.env.production`)
-  - Aksi halde `.env` yüklenir
-- Diğer modüller `os.getenv()` ile bu değerleri okur.
-
-### Hangi dosyalar repo’ya girer?
-- `.env.example` → EVET, commit’leyin (örnek ve dokümantasyon amaçlı)
-- `.env`, `.env.production`, `.env.*` → HAYIR, gizli bilgiler; repo’ya eklemeyin
-
-## CORS (Önemli)
-Geliştirmede `*` kullanılabilir; production'da sadece izinli origin'leri tanımlayın.
-Örnek (internal): `http://10.1.1.1:80`
-
-## Çoklu Veritabanı Yapılandırması
-
-### Desteklenen Veritabanı Tipleri
-Uygulama şu veritabanı teknolojilerini destekler:
-- **MSSQL** → Driver: `aioodbc`
-- **MySQL** → Driver: `aiomysql`
-- **PostgreSQL** → Driver: `asyncpg`
-
-### Databases Tablosu Yapısı
-Uygulama başlangıcında `Databases` tablosundan veritabanı bilgileri okunur:
-
-```sql
-CREATE TABLE Databases (
-    id INT PRIMARY KEY IDENTITY(1,1),
-    servername NVARCHAR(100) NOT NULL,      -- Sunucu adresi
-    database_name NVARCHAR(100) NOT NULL,   -- Veritabanı adı
-    technology NVARCHAR(100) NOT NULL       -- mssql, mysql, postgresql
-);
+### 3. Run the Development Server
+```bash
+npm run dev
 ```
+The application will be accessible at `http://localhost:5173` (or the port specified by Vite) and will automatically proxy API requests to the backend server running at `http://localhost:8080`.
 
-### Örnek Kayıtlar
-```sql
--- MSSQL Sunucu
-INSERT INTO Databases (servername, database_name, technology)
-VALUES ('localhost', 'Northwind', 'mssql'),
-       ('localhost', 'AdventureWorks', 'mssql');
-
--- MySQL Sunucu
-INSERT INTO Databases (servername, database_name, technology)
-VALUES ('mysql-server-1', 'ecommerce', 'mysql'),
-       ('mysql-server-1', 'analytics', 'mysql');
-
--- PostgreSQL Sunucu
-INSERT INTO Databases (servername, database_name, technology)
-VALUES ('postgres-server-1', 'production_db', 'postgresql'),
-       ('postgres-server-1', 'staging_db', 'postgresql');
+---
+
+## Testing
+
+WebQuery comes with a comprehensive testing suite that executes completely in memory using an SQLite async memory database (`sqlite+aiosqlite:///:memory:`) to verify routes, middlewares, error translation, and SQL execution without modifying any external resources.
+
+Run the test suite using pytest:
+```bash
+pytest
 ```
 
-### Otomatik Driver Seçimi
-Uygulama, `technology` alanına göre otomatik olarak doğru driver'ı seçer ve connection string oluşturur. Manuel konfigürasyona gerek yoktur.
-
-## Veritabanı Notları
-
-### MSSQL (SQL Server)
-- SQL Authentication kullanılır: `.env` içinde `DB_USER` ve `DB_PASSWORD`.
-- Uygulama DB'sinde user oluşturun ve uygun rol verin (kolay yol: `db_owner`).
-- Diğer veri tabanlarında sadece okuma gerekiyorsa ilgili DB'de `CREATE USER ... FOR LOGIN ...; GRANT SELECT TO ...` yeterlidir.
-
-### MySQL
-- MySQL server'da kullanıcı oluşturun ve gerekli izinleri verin
-- Örnek: `CREATE USER 'user'@'%' IDENTIFIED BY 'password'; GRANT SELECT ON db.* TO 'user'@'%';`
-
-### PostgreSQL
-- PostgreSQL'de kullanıcı ve izinleri ayarlayın
-- Örnek: `CREATE USER myuser WITH PASSWORD 'mypass'; GRANT CONNECT ON DATABASE mydb TO myuser;`
-
-## Sık Karşılaşılan Sorunlar
-
-### Driver Sorunları
-- **"ODBC Driver bulunamadı"** (MSSQL): 
-  - Sunucuya "ODBC Driver 18 for SQL Server" kurun
-  - Test: `odbcinst -j` (Linux) veya ODBC Data Sources (Windows)
-  
-- **"No module named 'aiomysql'"** (MySQL):
-  - `pip install aiomysql PyMySQL` çalıştırın
-  
-- **"No module named 'asyncpg'"** (PostgreSQL):
-  - `pip install asyncpg` çalıştırın
-
-### Bağlantı Sorunları
-- **"Login failed"**: 
-  - `DB_USER/DB_PASSWORD` doğru mu?
-  - İlgili DB'de USER bağlı mı?
-  - `Databases` tablosunda kayıt var mı?
-  
-- **"Technology not supported"**:
-  - `Databases` tablosunda `technology` alanı doğru mu? (mssql, mysql, postgresql)
-  
-- **"Connection timeout"**:
-  - Sunucu erişilebilir mi?
-  - Firewall kuralları doğru mu?
-
-### Diğer Sorunlar
-- **"CORS hatası"**: Production'da izinli origin eklediniz mi?
-- **"Database not found"**: `Databases` tablosuna kayıt eklediniz mi?
-
-## Lisans
-Bu proje [MIT License](LICENSE) altında lisanslanmıştır.
-
-## Katkıda Bulunma
-Katkıda bulunmak isterseniz lütfen [CONTRIBUTING.md](CONTRIBUTING.md) dosyasını inceleyin. Pull request'lerinizi bekliyoruz!
+---
 
+## License
+This project is licensed under the MIT License.
```
</details>

<details>
<summary>📄 Dosyanın Güncel Tam İçeriğini Göster (README.md)</summary>

```markdown
# WebQuery - Enterprise SQL Execution Platform

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Architecture](https://img.shields.io/badge/architecture-modular-orange)

WebQuery is a powerful, secure, and production-ready enterprise SQL execution platform built on FastAPI. It allows teams to safely run, share, and audit queries across multiple target databases (MSSQL, MySQL, PostgreSQL). 

Designed with zero-trust B2B security principles, WebQuery eliminates the need to store individual database credentials by employing a **Centralized Service Account Architecture** coupled with advanced AST-based query analysis, global error translation, and a real-time request tracing system.

---

## Architecture & Core Features

### 1. Centralized Service Account Architecture (Zero-Trust Security)
* **No User-Stored Credentials:** Individual database passwords are never requested, stored, or cached (removing any risk of credential leaks).
* **Central Credentials:** Connections to target databases are established dynamically using highly restricted central service credentials (`CENTRAL_DB_USER` and `CENTRAL_DB_PASSWORD`) defined securely in the environment.
* **Granular Audit Logging:** Although execution is centralized, every query is strictly audited. The platform logs the exact user, trace ID, timestamp, and machine name for every action in the `ActionLogging` table.
* **Stateless JWT Authorization:** Session management is completely stateless. Authenticated requests use cryptographically signed JWT tokens stored in secure, HttpOnly cookies, completely eliminating the need for a Redis credential cache.

### 2. Intelligent Connection Pooling & Engine Cache
* **Zero Idle Connections:** Connection engines to target databases are managed by an advanced `EngineCache`. It sets `pool_size=0` to release idle server-side connections immediately after query execution.
* **Max Overflow Handling:** Dynamically allows up to 20 concurrent connections during peak query bursts.
* **LRU Eviction & TTL Cleanup:** Least Recently Used (LRU) engines are evicted when the cache limit is reached. A background task cleans up expired engines based on a configurable Time-to-Live (TTL), while ensuring active, currently executing engines (`checkedout > 0`) are safely protected.

### 3. Dynamic SQL Risk Analysis (AST Parsing)
Before execution, every query is analyzed by a custom `QueryAnalyzer` utilizing the `sqlglot` library for abstract syntax tree (AST) parsing. It supports target-specific SQL dialects (`tsql`, `mysql`, `postgres`) and grades queries into four risk levels:
1. **SQL Injection:** Checks for structural anomalies (e.g., `UNION SELECT`, `OR 1=1`, inline comments).
2. **DDL (Structural Modifications):** Detects `DROP`, `CREATE`, `ALTER`, `TRUNCATE`.
3. **Risky DML:** Blocks `DELETE` or `UPDATE` statements lacking a `WHERE` clause.
4. **Performance Anomalies:** Flagging queries with more than 3 `JOIN`s, `CROSS JOIN`s, un-indexed `LIKE '%...%'`, or massive `LIMIT` operations.

> [!NOTE]
> **Approval Workflow:** Risky queries submitted by non-admin users are automatically put into a "Pending Approval" state. Authorized administrators can inspect, approve, or reject these queries via Slack or the Admin Panel.

### 4. Advanced Request Tracing & Auditing Middleware
* **Trace ID Generation:** The `TraceMiddleware` automatically assigns a unique UUID (Trace ID) to every incoming HTTP request and attaches it as the `X-Request-ID` header in the response.
* **Context-Aware Auditing:** Utilizes Python `contextvars` to dynamically propagate the active Trace ID and authenticated User ID to all logging handlers. Every log entry automatically prints the trace context without passing request objects down the call stack.

### 5. Unified Error Translation (Exception Translation Pattern)
* **Modular Domain Exceptions:** Low-level infrastructure, driver, or database errors (such as SQLAlchemy or network exceptions) are caught at the service boundary and translated into domain-specific exceptions (e.g., `WorkspaceNotFoundError`, `QueryExecutionError`, `UserAlreadyExistsError`).
* **Global Handling:** A centralized exception handler intercepts all domain exceptions, logs their detailed tracebacks internally, and returns a clean, secure, and standardized JSON response containing `success: false`, the enterprise `error_code`, a safe client-facing `message`, and the associated `trace_id`.

---

## Directory Structure

WebQuery adopts a clean, modular package architecture:

```
web_api/
│
├── common/                  # Centralized utilities (Exceptions, Logging, Rate Limiting)
│   ├── exceptions.py        # BaseServiceException and global hierarchy
│   ├── logging_config.py    # Custom contextvars logger formatting
│   └── limiter.py           # Consolidated, shared slowapi Limiter
│
├── middlewares/             # FastAPI Middlewares (Trace ID, Stateless Auth)
│   ├── trace_middleware.py  # Request ID generation and log context binding
│   └── auth_middleware.py   # JWT validation and user context binding
│
├── database_provider/       # Connection management and target DB sessions
│   ├── database.py          # DatabaseProvider session generator
│   ├── engine_cache.py      # LRU and TTL-based SQLAlchemy connection engine caching
│   └── config.py            # Central and target database driver configurations
│
├── query_execution/         # SQL execution, AST risk analysis, and audit logging
│   ├── services.py          # QueryService with SELECT and DML execution safety
│   └── router.py            # Query execution HTTP entrypoints
│
├── workspaces/              # User workspace management (Saved queries and metadata)
├── authentication/          # User registration, stateless login, and cookies
├── admin/                   # Administrative actions (Database registration, manual approvals)
└── tests/                   # Test Suite (Unit and Integration tests with SQLite in-memory)
```

---

## Driver Requirements

To connect to target databases, the corresponding system-level drivers and client libraries must be installed on your host machine:

### **Microsoft SQL Server (MSSQL)**
* **ODBC Driver 18 for SQL Server** (System-level installation is mandatory).
  * Windows: [Microsoft ODBC Download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
  * Linux/macOS: [ODBC Installation Guide](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
  * Python packages: `aioodbc`, `pyodbc` (included in requirements)

### **MySQL**
* Python packages: `aiomysql`, `PyMySQL` (included in requirements)

### **PostgreSQL**
* Python package: `asyncpg` (included in requirements)

---

## Quick Start (Development)

### 1. Clone the Repository
```bash
git clone https://github.com/erdemdnmz2/WebQuery
cd WebQuery
```

### 2. Set Up Virtual Environment and Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r web_api/requirements.txt
```

### 3. Configure Environment Variables
Copy the template `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```

Ensure the following variables are set correctly:
* `DB_USER` and `DB_PASSWORD` (For the WebQuery metadata application database)
* `CENTRAL_DB_USER` and `CENTRAL_DB_PASSWORD` (Central service account for target database executions)
* `SECRET_KEY` (Strong secret key for JWT signatures)
* `SQL_SERVER_NAMES` (Comma-separated list of target servers, e.g., `localhost`)

### 4. Initialize Database
Initialize the SQLite metadata database (or MSSQL if configured):
```bash
cd web_api
python create_db.py
```

### 5. Run the Application
Start the Uvicorn development server:
```bash
python app.py
```
The API will be accessible at `http://localhost:8080` with interactive Swagger docs at `http://localhost:8080/docs`.

---

## Frontend Setup (Development)

The WebQuery frontend is a modern React application built with Vite, TypeScript, and Tailwind CSS.

### 1. Navigate to the Frontend Directory
```bash
cd frontend
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Run the Development Server
```bash
npm run dev
```
The application will be accessible at `http://localhost:5173` (or the port specified by Vite) and will automatically proxy API requests to the backend server running at `http://localhost:8080`.

---

## Testing

WebQuery comes with a comprehensive testing suite that executes completely in memory using an SQLite async memory database (`sqlite+aiosqlite:///:memory:`) to verify routes, middlewares, error translation, and SQL execution without modifying any external resources.

Run the test suite using pytest:
```bash
pytest
```

---

## License
This project is licensed under the MIT License.

```
</details>



#### <a name="web_apisessionsession_cachepy"></a> `web_api/session/session_cache.py`
**Açıklama:** Durumsuz (stateless) JWT kimlik doğrulama mimarisine geçilmesi ve Redis şifreli parola önbelleğinin kaldırılmasıyla tamamen işlevsiz kalarak projeden silinen modül. (SİLİNDİ)

<details>
<summary>🔍 Satır Satır Değişiklikleri Göster (Git Diff)</summary>

```diff
diff --git a/web_api/session/session_cache.py b/web_api/session/session_cache.py
deleted file mode 100644
index d9504c0..0000000
--- a/web_api/session/session_cache.py
+++ /dev/null
@@ -1,70 +0,0 @@
-"""
-Session Cache Manager
-Kullanıcı session'larını ve şifrelerini bellekte güvenli bir şekilde saklar
-"""
-from typing import Dict
-from cryptography.fernet import Fernet
-from datetime import datetime
-import os
-import redis
-
-import json
-
-class SessionCache:
-    def __init__(self, fernet: Fernet | None = None):
-        redis_host = os.getenv("REDIS_HOST", "localhost")
-        redis_port = int(os.getenv("REDIS_PORT", 6379))
-        redis_db = int(os.getenv("REDIS_DB", 0))
-
-        self.client = redis.Redis(
-            host=redis_host,
-            port=redis_port,
-            db=redis_db,
-            decode_responses=True
-        )
-        self.fernet_instance = fernet
-
-    def add_to_cache(self, password: str, user_id: int):
-        if not self.fernet_instance:
-            raise RuntimeError("Fernet instance is not initialized")
-        
-        # Redis sadece string tutabildiği için dictionary'i JSON formatına çeviriyoruz.
-        # Fernet şifresi bytes döner, json için string'e çevirmeliyiz (.decode('utf-8'))
-        # Datetime objesini de iso string formatına çeviriyoruz (.isoformat())
-        sub = {
-            "user_password": self.fernet_instance.encrypt(password.encode()).decode('utf-8'),
-            "addition_time": datetime.now().isoformat()
-        }
-        self.client.set(user_id, json.dumps(sub))
-
-    def get_password(self, user_id: int) -> str:
-        if not self.fernet_instance:
-            raise RuntimeError("Fernet instance is not initialized")
-        
-        info_str = self.client.get(user_id)
-        if not info_str:
-            raise KeyError(f"Kullanıcı ({user_id}) cache üzerinde bulunamadı.")
-            
-        info = json.loads(info_str)
-        # JSON'dan gelen string formatındaki şifreli hali tekrar bytes'a çeviriyoruz (.encode('utf-8'))
-        encoded_pw = info["user_password"].encode('utf-8')
-        password = self.fernet_instance.decrypt(encoded_pw).decode()
-        return password
-
-    def remove(self, user_id: int):
-        self.client.delete(user_id)
-
-    def is_valid(self, user_id: int, timeout_minutes: int) -> bool:
-        info_str = self.client.get(user_id)
-        if not info_str:
-            return False
-            
-        info = json.loads(info_str)
-        from datetime import datetime, timedelta
-        timeout = timedelta(minutes=timeout_minutes)
-        addition_time = datetime.fromisoformat(info["addition_time"])
-        
-        if datetime.now() - addition_time > timeout:
-            self.remove(user_id)
-            return False
-        return True
\ No newline at end of file
```
</details>

> *Dosya silindiği veya sistemde bulunmadığı için tam içerik gösterilemiyor.*


