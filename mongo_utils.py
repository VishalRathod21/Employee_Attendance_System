from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

class MongoDBClient:
    def __init__(self, uri, db_name):
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None
        
    def connect(self):
        try:
            self.client = MongoClient(self.uri)
            self.db = self.client[self.db_name]
            # Verify connection
            self.client.admin.command('ping')
            print("Connected to MongoDB successfully!")
        except ConnectionFailure as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise
    
    def get_collection(self, collection_name):
        if not self.client:
            self.connect()
        return self.db[collection_name]
    
    def close(self):
        if self.client:
            self.client.close()
            print("MongoDB connection closed.")