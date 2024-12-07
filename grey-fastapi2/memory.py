import os
from datetime import datetime
import time
from openai import OpenAI
from pinecone import Pinecone
from atproto import Client

class BotMemory:
    def __init__(self, client):
        """Initialize the bot's memory system."""
        print("Initializing BotMemory...")
        self.client = client
        self.openai_client = OpenAI()
        self.index = self.initialize_pinecone()
    
    def initialize_pinecone(self):
        """Initialize Pinecone connection."""
        try:
            print("\nConnecting to Pinecone...")
            pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
            
            index_name = "greybot-memory"
            if index_name not in pc.list_indexes().names():
                print(f"Creating new index: {index_name}")
                pc.create_index(
                    name=index_name,
                    dimension=1536,
                    metric='cosine'
                )
            
            return pc.Index(index_name)
            
        except Exception as e:
            print(f"ERROR initializing Pinecone: {str(e)}")
            raise e

    def get_last_post(self, client_atproto: Client, bot_handle: str):
        """Get the last three posts made by the bot."""
        try:
            print(f"\nFetching last three posts for {bot_handle}...")
            profile = client_atproto.get_profile(bot_handle)
            
            # Increased limit to ensure we can find 3 complete threads
            feed = client_atproto.get_author_feed(profile.did, limit=30)
            if not feed.feed:
                print("No posts found")
                return None
            
            # Track three separate threads
            threads = []
            current_thread = None
            current_thread_time = None
            
            for post in feed.feed:
                post_time = datetime.fromisoformat(post.post.record.created_at.replace('Z', '+00:00'))
                
                if current_thread is None:
                    # Start a new thread
                    current_thread = [{
                        'uri': post.post.uri,
                        'cid': post.post.cid,
                        'text': post.post.record.text,
                        'created_at': post.post.record.created_at,
                        'position': 'main'
                    }]
                    current_thread_time = post_time
                else:
                    # Check if this post belongs to current thread (within 1 minute)
                    time_diff = abs((post_time - current_thread_time).total_seconds())
                    
                    if time_diff <= 60:  # Within 1 minute window
                        print(f"\nFound related post (time diff: {time_diff:.1f}s):")
                        print(f"Text: {post.post.record.text[:100]}...")
                        current_thread.append({
                            'uri': post.post.uri,
                            'cid': post.post.cid,
                            'text': post.post.record.text,
                            'created_at': post.post.record.created_at,
                            'position': 'thread'
                        })
                    else:
                        # Start new thread if we haven't stored 3 threads yet
                        if len(threads) < 3:  # Changed from 2 to 3
                            if current_thread:
                                threads.append(current_thread)
                            current_thread = [{
                                'uri': post.post.uri,
                                'cid': post.post.cid,
                                'text': post.post.record.text,
                                'created_at': post.post.record.created_at,
                                'position': 'main'
                            }]
                            current_thread_time = post_time
                        else:
                            break  # We have our 3 threads
            
            # Add the last thread if we haven't stored 3 yet
            if current_thread and len(threads) < 3:  # Changed from 2 to 3
                threads.append(current_thread)
            
            # Flatten the threads into a single list
            all_posts = []
            for thread in threads:
                thread.sort(key=lambda x: x['created_at'])
                all_posts.extend(thread)
            
            print(f"\nTotal threads found: {len(threads)}")
            for idx, post in enumerate(all_posts, 1):
                print(f"\n{idx}. {post['position'].upper()}:")
                print(f"Text: {post['text'][:100]}...")
            
            return all_posts
                
        except Exception as e:
            print(f"Error getting latest posts: {str(e)}")
            return None

    def store_thread_posts(self, posts):
        """Store posts in Pinecone with retries."""
        try:
            if not posts:
                print("No posts to store")
                return False
            
            print(f"\nPreparing to store {len(posts)} posts...")
            
            # Process posts one at a time for better reliability
            for idx, post in enumerate(posts, 1):
                print(f"\nProcessing post {idx}/{len(posts)}:")
                print(f"Text: {post['text'][:100]}...")
                
                try:
                    # Generate embedding
                    embedding = self.openai_client.embeddings.create(
                        input=post['text'],
                        model="text-embedding-3-small"
                    ).data[0].embedding
                    
                    vector = {
                        'id': post['uri'],
                        'values': embedding,
                        'metadata': {
                            'uri': post['uri'],
                            'cid': post['cid'],
                            'text': post['text'],
                            'created_at': post['created_at'],
                            'position': post['position']
                        }
                    }
                    
                    # Store with retries
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            self.index.upsert(vectors=[vector])
                            time.sleep(1)  # Wait for consistency
                            
                            # Verify storage
                            fetch_response = self.index.fetch(ids=[post['uri']])
                            if post['uri'] in fetch_response.vectors:
                                print(f"✓ Successfully stored post {idx} (attempt {attempt + 1})")
                                break
                            else:
                                print(f"! Storage verification failed, retrying... ({attempt + 1}/{max_retries})")
                                time.sleep(2)  # Wait longer between retries
                        except Exception as e:
                            print(f"Error on attempt {attempt + 1}: {str(e)}")
                            if attempt == max_retries - 1:
                                raise e
                            time.sleep(2)
                    
                except Exception as e:
                    print(f"Failed to process post {idx}: {str(e)}")
                    return False
            
            print("\n✓ All posts successfully stored")
            return True
            
        except Exception as e:
            print(f"Error in store_thread_posts: {str(e)}")
            return False

    def update_memory(self, client_atproto: Client, bot_handle: str):
        """Update memory with latest post and its thread components."""
        try:
            print("\nStarting memory update...")
            posts = self.get_last_post(client_atproto, bot_handle)
            
            if posts:
                success = self.store_thread_posts(posts)
                if success:
                    print(f"\n✓ Successfully stored {len(posts)} posts")
                else:
                    print("\n! Some posts may not have been stored correctly")
            else:
                print("No posts to store")
            
        except Exception as e:
            print(f"Error updating memory: {e}")
            raise e