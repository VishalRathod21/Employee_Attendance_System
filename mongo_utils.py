from pymongo import MongoClient
import urllib.parse

class MongoDBClient:
    def __init__(self, uri, db_name):
        self.uri = uri
        self.db_name = db_name
        
    def connect(self):
        try:
            # Auto-encode password if not already encoded
            if "@" in self.uri:
                protocol, rest = self.uri.split("@", 1)
                creds_part = protocol.split("//")[1]
                username, password = creds_part.split(":", 1)
                if "%" not in password:  # Only encode if not already encoded
                    encoded_password = urllib.parse.quote_plus(password)
                    self.uri = self.uri.replace(password, encoded_password)

            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=10000,  # 10-second timeout
                socketTimeoutMS=30000
            )
            self.db = self.client[self.db_name]
            self.client.admin.command('ping')  # Test connection
            print("✅ MongoDB connected!")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {str(e)[:200]}...")
            raise
