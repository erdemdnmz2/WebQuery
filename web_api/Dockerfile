FROM python:3.11-slim

# System dependencies and ODBC driver
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    apt-transport-https \
    unixodbc \
    unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Run as a dedicated non-root user. A process escaping the application
# (a dependency RCE, a path traversal in a library) inherited root inside the
# container by default, which is a needless privilege to hand it — the app
# writes nothing outside /app and needs no elevated capability at runtime.
RUN groupadd --system webquery && useradd --system --gid webquery --home-dir /app webquery \
    && chown -R webquery:webquery /app
USER webquery

EXPOSE 8080

ENTRYPOINT ["/bin/bash", "./entrypoint.sh"]
CMD ["python", "app.py"]
