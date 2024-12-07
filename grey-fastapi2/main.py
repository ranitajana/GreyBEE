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
    check_notifications
)
from memory import BotMemory

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
    THREAD_POST_INTERVAL = 1800  # 30 minutes in seconds
    CHECK_INTERVAL = 60  # 1 minute in seconds
    last_post_time = None
    #List of keywords to search for viral posts
    keywords = [
    # General World Politics
    "diplomacy", "international relations", "geopolitics", "foreign policy", "global governance",
    # Political Systems
    "democracy", "authoritarianism", "socialism", "capitalism", "communism",
    # International Organizations
    "UN", "NATO", "EU", "WHO", "WTO",
    # Global Issues
    "climate change", "terrorism", "human rights", "nuclear proliferation", "cybersecurity",
    # Economic Concepts
    "globalization", "free trade", "protectionism", "sanctions", "economic integration",
    # Diplomatic Terms
    "summit", "treaty", "alliance", "bilateral relations", "multilateralism",
    # Political Ideologies
    "liberalism", "conservatism", "nationalism", "populism", "environmentalism",
    # Power Dynamics
    "superpower", "hegemony", "balance of power", "soft power", "hard power",
    # Conflict and Security
    "war", "peace", "disarmament", "peacekeeping", "counterterrorism",
    # Trending Topics
    "refugee crisis", "disinformation", "AI in warfare", "deglobalization", "pandemic response"
]
    
    # Define memory update interval
    MEMORY_UPDATE_INTERVAL = 300  # Update memory every hour (3600 seconds)
    MEMORY_RETENTION_PERIOD = 1  
    last_memory_update = None
    
    # Initialize memory system ONCE
    print("Initializing bot memory...")
    bot_memory = BotMemory(client)
    
    # Get the correct bot handle from environment variables
    BOT_HANDLE = os.getenv('BSKY_IDENTIFIER')  # Make sure this matches exactly
    
    while True:
        try:
            current_time = datetime.now()
            print(f"\n[{current_time}] Starting new check...")
            
            # Refresh authentication tokens if expired or not set
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
                
                # Get bot DID using the access token
                bot_did = get_bot_did(access_token, os.getenv('BSKY_IDENTIFIER'))
                if not bot_did:
                    print("Failed to get bot DID. Waiting...")
                    time.sleep(CHECK_INTERVAL)
                    continue
            
            # Update memory every hour
            if (last_memory_update is None or 
                (current_time - last_memory_update).total_seconds() >= MEMORY_UPDATE_INTERVAL):
                print(f"\nChecking for new posts from {BOT_HANDLE}...")
                bot_memory.update_memory(
                    client_atproto, 
                    BOT_HANDLE  # Use the correct handle
                )
                last_memory_update = current_time
            
            # Check notifications with OpenAI client
            # check_notifications(access_token, client, client_atproto)
            
            # Check if it's time to post a new thread
            # if last_post_time is None or (current_time - last_post_time).total_seconds() >= THREAD_POST_INTERVAL:
            #     print("\nPosting new trending thread...")
            #     success = post_trending_content(access_token, bot_did, used_posts, used_topics, client,keywords)
            #     if success:
            #         last_post_time = current_time
            #     print(f"Thread posting result: {success}")
            
            # Wait before the next check
            print(f"\nWaiting {CHECK_INTERVAL} seconds before next check...")
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            print(f"Waiting {CHECK_INTERVAL} seconds before retry...")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print("Starting trending bot...")
    main() 