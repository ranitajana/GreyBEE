from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import os
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv
import asyncio
from threading import Thread

# Import functions from search_post.py
from search_post import (
    get_auth_token,
    search_mentions,
    post_reply,
    get_bot_did
)

app = FastAPI()

# Global variables to store state
global_state = {
    "access_token": None,
    "refresh_token": None,
    "token_creation_time": None,
    "bot_did": None,
    "is_running": False
}

async def monitoring_task():
    token_expiry = timedelta(hours=1)
    
    while global_state["is_running"]:
        try:
            current_time = datetime.now()
            print(f"\n[{current_time}] Starting new check...")
            
            # Token refresh logic
            if (global_state["access_token"] is None or 
                global_state["token_creation_time"] is None or 
                current_time - global_state["token_creation_time"] >= token_expiry):
                
                print("Getting new authentication tokens...")
                access_token, refresh_token = get_auth_token()
                global_state["access_token"] = access_token
                global_state["refresh_token"] = refresh_token
                global_state["token_creation_time"] = current_time
                
                if not access_token:
                    print("Failed to get authentication tokens. Waiting...")
                    await asyncio.sleep(60)
                    continue
                
                global_state["bot_did"] = get_bot_did(access_token, os.getenv('BSKY_IDENTIFIER'))
                if not global_state["bot_did"]:
                    print("Failed to get bot DID. Waiting...")
                    await asyncio.sleep(60)
                    continue
                
                print("Successfully refreshed authentication (hourly update)")
            
            # Search and reply logic
            df_mentions = search_mentions(global_state["access_token"], os.getenv('BSKY_IDENTIFIER'))
            
            if df_mentions is not None and not df_mentions.empty:
                print(f"\nProcessing replies for {len(df_mentions)} posts...")
                
                for index, post in df_mentions.iterrows():
                    post_uri = post['reply_parent'] if post['reply_parent'] else post['uri']
                    author_handle = post['author_username']
                    
                    success = post_reply(global_state["access_token"], 
                                      author_handle,
                                      "Thanks for tagging, I will get back to you soon.", 
                                      post_uri,
                                      global_state["bot_did"])
                    
                    await asyncio.sleep(2)  # Wait between replies
            
            await asyncio.sleep(60)  # Wait for next check
            
        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    global_state["is_running"] = True
    # Start the monitoring task in the background
    asyncio.create_task(monitoring_task())

@app.on_event("shutdown")
async def shutdown_event():
    global_state["is_running"] = False

# API endpoints
@app.get("/status")
async def get_status():
    return {
        "is_running": global_state["is_running"],
        "last_token_refresh": global_state["token_creation_time"],
        "has_valid_token": global_state["access_token"] is not None
    }

@app.post("/stop")
async def stop_monitoring():
    global_state["is_running"] = False
    return {"message": "Monitoring stopped"}

@app.post("/start")
async def start_monitoring():
    if not global_state["is_running"]:
        global_state["is_running"] = True
        asyncio.create_task(monitoring_task())
    return {"message": "Monitoring started"}