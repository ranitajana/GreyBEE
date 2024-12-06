import pinecone
from openai import OpenAI
from typing import Dict, List
from datetime import datetime

class BlueSkyMemory:
    def __init__(self, pinecone_api_key: str, openai_client: OpenAI):
        """Initialize BlueSky memory with Pinecone and OpenAI."""
        self.client = openai_client
        
        # Create a Pinecone instance
        self.pinecone = pinecone.Pinecone(api_key=pinecone_api_key)
        
        # Create or connect to index
        self.index_name = 'unsupervized'
        if self.index_name not in self.pinecone.list_indexes().names():
            self.pinecone.create_index(
                name=self.index_name,
                dimension=1536,  # dimension for text-embedding-ada-002
                metric='cosine',
                spec=pinecone.ServerlessSpec(
                    cloud='aws',
                    region='us-west-2'
                )
            )
        self.index = self.pinecone.Index(self.index_name)

    def create_embedding(self, text: str) -> List[float]:
        """Create embedding for text using OpenAI."""
        response = self.client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding

    def store_post(self, post_data: Dict):
        """Store a Bluesky post in Pinecone."""
        try:
            combined_text = f"{post_data['text']} by {post_data['author']} on {post_data['created_at']}"
            vector = self.create_embedding(combined_text)
            
            self.index.upsert(vectors=[
                (post_data['uri'], vector, {
                    'uri': post_data['uri'],
                    'text': post_data['text'],
                    'author': post_data['author'],
                    'created_at': post_data['created_at'],
                    'reply_to': post_data.get('reply_to'),
                    'likes': post_data.get('likes', 0),
                    'reposts': post_data.get('reposts', 0),
                    'replies_count': post_data.get('replies_count', 0),
                    'thread_root': post_data.get('thread_root'),
                    'is_bot_post': post_data.get('is_bot_post', False)
                })
            ])
            print(f"Stored post in memory: {post_data['uri']}")
            return True
        except Exception as e:
            print(f"Error storing post in memory: {str(e)}")
            return False

    def get_thread_context(self, thread_root: str, limit: int = 10) -> List[Dict]:
        """Retrieve context for a thread."""
        try:
            query_response = self.index.query(
                vector=[0] * 1536,  # placeholder vector
                filter={
                    "thread_root": thread_root
                },
                top_k=limit,
                include_metadata=True
            )
            
            posts = [match.metadata for match in query_response.matches]
            posts.sort(key=lambda x: x['created_at'])
            return posts
        except Exception as e:
            print(f"Error retrieving thread context: {str(e)}")
            return []

    def cleanup_old_posts(self, days_threshold: int = 30):
        """Clean up posts older than the specified threshold."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_threshold)).isoformat()
            self.index.delete(
                filter={
                    "created_at": {"$lt": cutoff_date}
                }
            )
            print(f"Cleaned up posts older than {days_threshold} days")
        except Exception as e:
            print(f"Error cleaning up old posts: {str(e)}") 