import os
from datetime import datetime
import time
from openai import OpenAI
from pinecone import Pinecone
from atproto import Client
import pytz
from config import MEMORY_UPDATE_TIME, MEMORY_UPDATE_TIMEZONE

class BotMemory:
    def __init__(self, client):
        """Initialize the bot's memory system."""
        print("Initializing BotMemory...")
        self.client = client
        self.openai_client = OpenAI()
        self.index = self.initialize_pinecone()
        self.is_updating = False  # Flag to track update status
        self.last_update_time = None
        self.force_update_needed = False  # Add this new flag
        self.is_update_time = False  # New flag for update time
        self.force_stop_needed = False  # New flag for immediate stops
    
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
        """Get the last 1000 posts made by the bot."""
        try:
            print(f"\nFetching last 1000 posts for {bot_handle}...")
            profile = client_atproto.get_profile(bot_handle)
            
            # Initialize variables for pagination
            all_threads = []
            cursor = None
            posts_collected = 0
            MAX_POSTS = 1000
            POSTS_PER_PAGE = 100  # Maximum allowed by the API
            
            while posts_collected < MAX_POSTS:
                # Get feed with pagination
                feed = client_atproto.get_author_feed(
                    profile.did, 
                    limit=POSTS_PER_PAGE,
                    cursor=cursor
                )
                
                if not feed.feed:
                    break
                    
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
                            # Store current thread and start a new one
                            if current_thread:
                                all_threads.append(current_thread)
                                posts_collected += len(current_thread)
                                
                                if posts_collected >= MAX_POSTS:
                                    break
                                    
                            current_thread = [{
                                'uri': post.post.uri,
                                'cid': post.post.cid,
                                'text': post.post.record.text,
                                'created_at': post.post.record.created_at,
                                'position': 'main'
                            }]
                            current_thread_time = post_time
                
                # Add the last thread from this page
                if current_thread and posts_collected < MAX_POSTS:
                    all_threads.append(current_thread)
                    posts_collected += len(current_thread)
                
                # Update cursor for next page
                if hasattr(feed, 'cursor') and feed.cursor:
                    cursor = feed.cursor
                else:
                    break
                    
                print(f"Collected {posts_collected} posts so far...")
                time.sleep(1)  # Rate limiting
            
            # Flatten the threads into a single list
            all_posts = []
            for thread in all_threads:
                thread.sort(key=lambda x: x['created_at'])
                all_posts.extend(thread)
            
            # Trim to exactly 1000 if we got more
            all_posts = all_posts[:MAX_POSTS]
            
            print(f"\nTotal threads found: {len(all_threads)}")
            print(f"Total posts collected: {len(all_posts)}")
            
            # Log sample of posts (first 5 and last 5)
            print("\nSample of first 5 posts:")
            for idx, post in enumerate(all_posts[:5], 1):
                print(f"\n{idx}. {post['position'].upper()}:")
                print(f"Text: {post['text'][:100]}...")
            
            print("\nSample of last 5 posts:")
            for idx, post in enumerate(all_posts[-5:], len(all_posts)-4):
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
            
            # Process posts in batches for better efficiency
            BATCH_SIZE = 50
            for i in range(0, len(posts), BATCH_SIZE):
                batch = posts[i:i + BATCH_SIZE]
                print(f"\nProcessing batch {i//BATCH_SIZE + 1}/{(len(posts) + BATCH_SIZE - 1)//BATCH_SIZE}:")
                
                vectors = []
                for post in batch:
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
                        vectors.append(vector)
                        
                    except Exception as e:
                        print(f"Failed to process post: {str(e)}")
                        continue
                
                # Store batch with retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.index.upsert(vectors=vectors)
                        time.sleep(1)  # Wait for consistency
                        
                        print(f"✓ Successfully stored batch {i//BATCH_SIZE + 1}")
                        break
                        
                    except Exception as e:
                        print(f"Error on attempt {attempt + 1}: {str(e)}")
                        if attempt == max_retries - 1:
                            return False
                        time.sleep(2)
            
            print("\n✓ All posts successfully stored")
            return True
            
        except Exception as e:
            print(f"Error in store_thread_posts: {str(e)}")
            return False

    def clear_old_records(self):
        """Clear all existing records from the index."""
        try:
            print("\nClearing old records from memory...")
            # Get list of namespaces
            describe_index = self.index.describe_index_stats()
            namespaces = describe_index.namespaces

            if namespaces:
                # Delete vectors if namespaces exist
                self.index.delete(delete_all=True, namespace="")
                print("✓ Successfully cleared old records")
            else:
                print("No existing records to clear")
            return True
        except Exception as e:
            print(f"Error clearing old records: {str(e)}")
            return False

    def is_memory_updating(self):
        """Check if memory update is in progress."""
        return self.is_updating

    def update_memory(self, client_atproto: Client, bot_handle: str):
        """Update memory with latest 1000 posts."""
        if self.is_updating:
            return False
        
        try:
            print("\nStarting memory update...")
            self.is_updating = True
            self.force_stop_needed = False  # Clear force stop flag during update
            
            # Clear old records
            if not self.clear_old_records():
                self.is_updating = False
                return False
            
            # Get and store new posts
            posts = self.get_last_post(client_atproto, bot_handle)
            if posts:
                success = self.store_thread_posts(posts)
                if success:
                    print(f"\n✅ Successfully stored {len(posts)} new posts")
                    self.last_update_time = datetime.now()
                else:
                    print("\n❌ Some posts may not have been stored correctly")
            
            self.is_updating = False
            return True
            
        except Exception as e:
            print(f"Error updating memory: {e}")
            self.is_updating = False
            raise e

    def search_relevant_memory(self, query_text, limit=5):
        """Search for relevant past interactions based on the query text."""
        try:
            print(f"\nSearching memory for context relevant to: {query_text[:100]}...")
            
            # Generate embedding for the query
            query_embedding = self.openai_client.embeddings.create(
                input=query_text,
                model="text-embedding-3-small"
            ).data[0].embedding
            
            # Search Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=limit,
                include_metadata=True
            )
            
            if not results.matches:
                print("No relevant memories found")
                return []
                
            # Format results
            memories = []
            for match in results.matches:
                if match.score < 0.7:  # Similarity threshold
                    continue
                    
                memories.append({
                    'text': match.metadata['text'],
                    'created_at': match.metadata['created_at'],
                    'position': match.metadata['position'],
                    'similarity': match.score
                })
            
            print(f"\nFound {len(memories)} relevant memories")
            for i, mem in enumerate(memories, 1):
                print(f"\nMemory {i} (similarity: {mem['similarity']:.3f}):")
                print(f"Position: {mem['position']}")
                print(f"Text: {mem['text'][:100]}...")
            
            return memories
            
        except Exception as e:
            print(f"Error searching memory: {str(e)}")
            return []

    def set_force_update(self):
        """Signal that a memory update is needed."""
        self.force_update_needed = True
        
    def clear_force_update(self):
        """Clear the force update flag after update is complete."""
        self.force_update_needed = False
        
    def needs_force_update(self):
        """Check if force update is needed."""
        return self.force_update_needed

    def is_memory_update_time(self):
        """Check if current time matches the configured memory update time."""
        current_time = datetime.now().astimezone(MEMORY_UPDATE_TIMEZONE)
        return (current_time.hour == MEMORY_UPDATE_TIME.hour and 
                current_time.minute == MEMORY_UPDATE_TIME.minute)
    
    def should_stop_operations(self):
        """Check if all operations should be stopped for memory update."""
        return self.is_memory_update_time() or self.force_update_needed

    def should_force_stop(self):
        """Check if immediate stop is needed."""
        current_time = datetime.now().astimezone(MEMORY_UPDATE_TIMEZONE)
        is_update_time = (current_time.hour == MEMORY_UPDATE_TIME.hour and 
                         current_time.minute == MEMORY_UPDATE_TIME.minute)
        if is_update_time:
            self.force_stop_needed = True
        return self.force_stop_needed
    
    def clear_force_stop(self):
        """Clear the force stop flag."""
        self.force_stop_needed = False