import os
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv
from openai import OpenAI
from functions import (get_auth_token, get_bot_did, search_mentions, 
                      post_reply, post_trending_content, get_viral_posts, check_notifications)

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Initialize OpenAI client with API key
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
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
            
            # Check notifications with OpenAI client
            check_notifications(access_token, client)
            
            # Check if it's time to post a new thread
            if last_post_time is None or (current_time - last_post_time).total_seconds() >= THREAD_POST_INTERVAL:
                print("\nPosting new trending thread...")
                success = post_trending_content(access_token, bot_did, used_posts, used_topics, client,keywords)
                if success:
                    last_post_time = current_time
                print(f"Thread posting result: {success}")
            
            # Handle mentions by searching and replying
            try:
                print("\nSearching for mentions...")
                df_mentions = search_mentions(access_token, os.getenv('BSKY_IDENTIFIER'))
                if df_mentions is not None and not df_mentions.empty:
                    print(f"Found {len(df_mentions)} mentions to process")
                    for _, mention in df_mentions.iterrows():
                        print(f"Processing mention from @{mention['author_username']}")
                        success = post_reply(
                            token=access_token,
                            author_handle=mention['author_username'],
                            post_content=mention['post_content'],
                            post_uri=mention['uri'],
                            bot_did=bot_did
                        )
                        print(f"Reply posted: {success}")
                        time.sleep(2)  # Small delay between replies if multiple
                else:
                    print("No new mentions to process")
            except Exception as e:
                print(f"Error handling mentions: {e}")
                
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