from fastapi import FastAPI, BackgroundTasks
from datetime import datetime, timedelta
import os
from typing import Dict
import asyncio
from contextlib import asynccontextmanager

# Import functions from post_reply.py
from post_reply import (
    get_auth_token,
    search_mentions,
    post_reply,
    get_bot_did,
    post_trending_content
)

# Global state to track bot status
bot_state: Dict = {
    "is_running": False,
    "last_check_time": None,
    "total_posts": 0,
    "total_replies": 0,
    "task": None  # Store the background task
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    bot_state["is_running"] = True
    bot_state["task"] = asyncio.create_task(run_bot())
    yield
    # Shutdown
    print("Shutting down...")
    bot_state["is_running"] = False
    if bot_state["task"]:
        bot_state["task"].cancel()
        try:
            await bot_state["task"]
        except asyncio.CancelledError:
            pass

app = FastAPI(title="Bluesky Bot API", lifespan=lifespan)

async def run_bot():
    # Initialize variables
    access_token = None
    refresh_token = None
    token_creation_time = None
    token_expiry = timedelta(hours=1)
    bot_did = None
    
    # Track used content for variety
    used_posts = set()
    used_topics = set()
    
    # Define time intervals
    THREAD_POST_INTERVAL = 1800  # 30 minutes in seconds
    MENTION_CHECK_INTERVAL = 60  # 1 minute in seconds
    last_post_time = None

    while bot_state["is_running"]:
        try:
            current_time = datetime.now()
            print(f"\n[{current_time}] Starting new check...")
            bot_state["last_check_time"] = current_time
            
            # Token refresh logic
            if (access_token is None or 
                token_creation_time is None or 
                current_time - token_creation_time >= token_expiry):
                
                print("Getting new authentication tokens...")
                access_token, refresh_token = get_auth_token()
                token_creation_time = current_time
                
                if not access_token:
                    print("Failed to get authentication tokens. Waiting...")
                    await asyncio.sleep(MENTION_CHECK_INTERVAL)
                    continue
                
                bot_did = get_bot_did(access_token, os.getenv('BSKY_IDENTIFIER'))
                if not bot_did:
                    print("Failed to get bot DID. Waiting...")
                    await asyncio.sleep(MENTION_CHECK_INTERVAL)
                    continue
            
            # Check if it's time to post a new thread
            if last_post_time is None or (current_time - last_post_time).total_seconds() >= THREAD_POST_INTERVAL:
                print("\nPosting new AI trending thread...")
                success = post_trending_content(access_token, bot_did, used_posts, used_topics)
                if success:
                    last_post_time = current_time
                    bot_state["total_posts"] += 1
                print(f"Thread posting result: {success}")
            
            # Handle mentions
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
                        if success:
                            bot_state["total_replies"] += 1
                        print(f"Reply posted: {success}")
                        await asyncio.sleep(2)  # Small delay between replies if multiple
                else:
                    print("No new mentions to process")
            except Exception as e:
                print(f"Error handling mentions: {e}")
                
            # Only wait after all processing is complete
            print(f"\nWaiting {MENTION_CHECK_INTERVAL} seconds before next check...")
            await asyncio.sleep(MENTION_CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            print(f"Waiting {MENTION_CHECK_INTERVAL} seconds before retry...")
            await asyncio.sleep(MENTION_CHECK_INTERVAL)

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Bluesky Bot API is running"}

@app.get("/status")
async def get_status():
    return {
        "is_running": bot_state["is_running"],
        "last_check_time": bot_state["last_check_time"],
        "total_posts": bot_state["total_posts"],
        "total_replies": bot_state["total_replies"]
    }

@app.post("/stop")
async def stop_bot():
    if bot_state["task"]:
        bot_state["is_running"] = False
        bot_state["task"].cancel()
        try:
            await bot_state["task"]
        except asyncio.CancelledError:
            pass
        bot_state["task"] = None
    return {"message": "Bot stopped"}

@app.post("/start")
async def start_bot():
    if not bot_state["is_running"]:
        bot_state["is_running"] = True
        bot_state["task"] = asyncio.create_task(run_bot())
        return {"message": "Bot starting..."}
    return {"message": "Bot is already running"}