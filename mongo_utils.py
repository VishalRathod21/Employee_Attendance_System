from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import urllib.parse

class MongoDBClient:
    def __init__(self, uri, db_name):
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None
        
    def connect(self):
        try:
            # Handle special characters in password
            if "@" in self.uri:
                protocol_part = self.uri.split("@")[0]
                rest_part = self.uri.split("@")[1]
                username_password = protocol_part.split("//")[1]
                password = username_password.split(":")[1]
                encoded_password = urllib.parse.quote_plus(password)
                self.uri = self.uri.replace(password, encoded_password)

            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                socketTimeoutMS=30000          # 30 second query timeout
            )
            self.db = self.client[self.db_name]
            self.client.admin.command('ping')
            print("✅ MongoDB connected successfully!")
        except Exception as e:
            print(f"❌ Connection failed: {str(e)[:200]}...")
            raise
