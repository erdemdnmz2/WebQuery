from database_provider import DatabaseProvider

class QueryService:
    def __init__(self, database_provider: DatabaseProvider):
        self.database_provider = database_provider
        