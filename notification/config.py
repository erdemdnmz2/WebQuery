import os
from dotenv import load_dotenv

load_dotenv()

SLACK_URL = os.getenv('SLACK_URL')

approval_message_format = """
*New SQL Query Approval Request*

*User:* {username}
*Date:* {request_time}
*Database:* {database_name}
*Machine Name:* {servername}
*Risk type:* {risk_type}

*Query:*
```{query}```

Please approve or reject the execution of this query.
"""

message_format = """
Hello,

The result of your SQL query below:

Database: {database_name}
User: {username}
Date: {execution_time}

Query:
{query}

Result:
- Total record count: {total_rows}

Best regards,
DBA Application
"""
