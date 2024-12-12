import os
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv
from openai import OpenAI
from atproto import Client
from functions import (
    get_auth_token, 
    get_bot_did, 
    post_reply,
    post_trending_content, 
    check_notifications,
    post_ai_news,
    save_used_content,
    load_used_content
)
from memory import BotMemory
import pytz
from config import MEMORY_UPDATE_TIME, MEMORY_UPDATE_TIMEZONE

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Initialize OpenAI client with API key
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    client_atproto = Client()
    client_atproto.login(os.getenv('BSKY_IDENTIFIER'), os.getenv('BSKY_PASSWORD'))
    
    # Initialize variables for authentication tokens and bot DID
    access_token = None
    refresh_token = None
    token_creation_time = None
    token_expiry = timedelta(hours=1)
    bot_did = None
    
    # Sets to track used content and topics to ensure variety
    used_posts = set()
    used_topics = set()
    
    # Define time intervals for posting and checking mentions/notifications
    THREAD_POST_INTERVAL = 2700  # 45 minutes in seconds
    CHECK_INTERVAL = 60  # 1 minute in seconds
    last_post_time = None
    
    # List of keywords to search for viral posts on Artificial Intelligence
    keywords = [
    # General AI Concepts
    "artificial intelligence", "machine learning", "deep learning", "neural networks", "natural language processing",
    
    # AI Applications
    "computer vision", "speech recognition", "robotics", "autonomous vehicles", "AI in healthcare",
    
    # Ethical Considerations
    "AI ethics", "bias in AI", "transparency", "accountability", "privacy concerns",
    
    # AI Technologies
    "reinforcement learning", "supervised learning", "unsupervised learning", "generative adversarial networks", "edge computing",
    
    # Industry Impact
    "AI in business", "AI in finance", "AI in education", "AI in marketing", "AI and job displacement",
    
    # AI Research and Development
    "AI algorithms", "data science", "big data", "cloud computing", "quantum computing",
    
    # Future of AI
    "singularity", "AGI (Artificial General Intelligence)", "AI governance", "human-AI collaboration", "future of work",
    
    # AI Trends
    "AI startups", "AI funding", "AI conferences", "open-source AI", "AI regulations"
    ]

    
    # Define memory update interval
    MEMORY_UPDATE_INTERVAL = 86400  # 24 hours in seconds (24 * 60 * 60)
    MEMORY_RETENTION_PERIOD = 1  
    last_memory_update = None
    
    # Initialize memory system ONCE
    print("Initializing bot memory...")
    bot_memory = BotMemory(client)
    
    # Get the correct bot handle from environment variables
    BOT_HANDLE = os.getenv('BSKY_IDENTIFIER')  # Make sure this matches exactly
    
    # Load previously used content
    used_posts, used_topics = load_used_content()
    
    # Add news posting interval
    NEWS_POST_INTERVAL = 7200  # 2 hours in seconds
    last_news_post_time = None
    
    while True:
        try:
            current_time = datetime.now()
            ist_time = current_time.astimezone(MEMORY_UPDATE_TIMEZONE)
            print(f"\n[{ist_time}] Starting new check...")

            # Check for memory update time first
            if bot_memory.is_memory_update_time():
                print(f"\n🚨 MEMORY UPDATE TIME - {MEMORY_UPDATE_TIME.hour:02d}:{MEMORY_UPDATE_TIME.minute:02d} {MEMORY_UPDATE_TIMEZONE.zone}")
                print("=======================================")
                print("FORCING ALL OPERATIONS TO STOP")
                print("=======================================")
                
                # Set force stop flag
                bot_memory.force_stop_needed = True
                
                # Wait for any ongoing operations to complete their force stop
                time.sleep(5)
                
                # Perform memory update
                if not bot_memory.is_memory_updating():
                    print("\nStarting memory update process...")
                    success = bot_memory.update_memory(
                        client_atproto, 
                        BOT_HANDLE
                    )
                    if success:
                        print("\n✅ Memory update complete")
                        bot_memory.clear_force_stop()
                        last_memory_update = current_time
                    else:
                        print("\n❌ Memory update failed")
                    
                    # Wait before resuming operations
                    time.sleep(60)
                    continue
            
            # Regular operations
            if not bot_memory.should_force_stop():
                # Refresh authentication tokens if needed
                if (access_token is None or 
                    token_creation_time is None or 
                    current_time - token_creation_time >= token_expiry):
                    
                    print("Getting new authentication tokens...")
                    access_token, refresh_token = get_auth_token()
                    token_creation_time = current_time
                    
                    if not access_token:
                        print("Failed to get authentication tokens. Waiting...")
                        time.sleep(CHECK_INTERVAL)
                        continue
                    
                    bot_did = get_bot_did(access_token, os.getenv('BSKY_IDENTIFIER'))
                    if not bot_did:
                        print("Failed to get bot DID. Waiting...")
                        time.sleep(CHECK_INTERVAL)
                        continue
                
                # Regular operations
                check_notifications(access_token, client, client_atproto, bot_memory)
                
                # Check for news posts
                if last_news_post_time is None or (current_time - last_news_post_time).total_seconds() >= NEWS_POST_INTERVAL:
                    print("\nChecking for AI news...")
                    success = post_ai_news(
                        access_token,
                        bot_did,
                        used_posts,
                        client,
                        bot_memory
                    )
                    if success:
                        last_news_post_time = current_time
                        # Save used content after successful post
                        save_used_content(used_posts, used_topics)
                
                if last_post_time is None or (current_time - last_post_time).total_seconds() >= THREAD_POST_INTERVAL:
                    print("\nPosting new trending thread...")
                    success = post_trending_content(
                        access_token, 
                        bot_did, 
                        used_posts, 
                        used_topics, 
                        client, 
                        keywords,
                        bot_memory  # Pass bot_memory to check for update time
                    )
                    if success:
                        last_post_time = current_time
                    print(f"Thread posting result: {success}")
            
            # Wait before next check
            print(f"\nWaiting {CHECK_INTERVAL} seconds before next check...")
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            print(f"Waiting {CHECK_INTERVAL} seconds before retry...")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print("Starting trending bot...")
    main() 