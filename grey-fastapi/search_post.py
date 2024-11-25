import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
import os
from dotenv import load_dotenv

# Load environment variables at the start of your script
load_dotenv()

def get_post_thread(token, post_uri):
    """Retrieve the thread (including replies) for a specific post."""
    url = "https://bsky.social/xrpc/app.bsky.feed.getPostThread"
    params = {
        "uri": post_uri,
        "depth": 1  # Get immediate replies only
    }
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)
    
    if response.status_code == 200:
        thread_data = response.json().get('thread', {})
        # Extract post CID from the response
        post_cid = thread_data.get('post', {}).get('cid')
        return thread_data, post_cid
    else:
        print(f"Error retrieving thread: {response.status_code} - {response.text}")
        return None, None

def convert_to_ist(utc_time_str):
    """Convert UTC time string to Indian Standard Time (IST)."""
    try:
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        ist_timezone = pytz.timezone('Asia/Kolkata')
        ist_time = utc_time.astimezone(ist_timezone)
        return ist_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    except Exception as e:
        print(f"Error converting time: {e}")
        return utc_time_str

def has_bot_replied(token, post_uri, bot_handle):
    """Check if the bot has already replied to this post."""
    thread_data, _ = get_post_thread(token, post_uri)
    if thread_data and 'replies' in thread_data:
        replies = thread_data.get('replies', [])
        for reply in replies:
            if reply.get('post', {}).get('author', {}).get('handle') == bot_handle:
                print(f"Bot has already replied to {post_uri}")
                return True
    return False

def search_mentions(token, handle):
    url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
    
    current_time = datetime.now(pytz.UTC)
    one_minute_ago = current_time - timedelta(minutes=1)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {
        "q": f"mentions:{handle}",
        "limit": 20
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        posts = response.json().get('posts', [])
        if not posts:
            return None
        
        recent_posts = []
        for post in posts:
            created_at = datetime.fromisoformat(post['record']['createdAt'].replace('Z', '+00:00'))
            
            if created_at >= one_minute_ago:
                post_uri = post['uri']
                
                # Check if this is a reply
                reply_parent = None
                if 'reply' in post['record']:
                    reply_parent = post['record']['reply']['parent']['uri']
                    print(f"Found mention in a reply. Parent URI: {reply_parent}")
                
                if not has_bot_replied(token, post_uri, handle):
                    post_details = {
                        'post_id': post_uri.split('/')[-1],
                        'uri': post_uri,
                        'reply_parent': reply_parent,  # Add parent URI if it's a reply
                        'author_username': post['author']['handle'],
                        'created_at': convert_to_ist(post['record']['createdAt']),
                        'post_content': post['record']['text'],
                        'reply_count': len(post.get('replies', [])),
                    }
                    recent_posts.append(post_details)
                    print(f"Found new post to reply: {post['record']['text'][:50]}...")
        
        if not recent_posts:
            return None
            
        print(f"Found {len(recent_posts)} posts needing replies")
        return pd.DataFrame(recent_posts)
        
    except Exception as e:
        print(f"Error in search_mentions: {str(e)}")
        return None

def get_bot_did(token, handle):
    """Get the DID for a given handle."""
    url = "https://bsky.social/xrpc/com.atproto.identity.resolveHandle"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "handle": handle
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        did = response.json().get('did')
        print(f"Successfully retrieved DID for {handle}: {did}")
        return did
    else:
        print(f"Failed to get DID: {response.status_code} - {response.text}")
        return None

def get_post_info(token, post_uri):
    """Get post CID and other details."""
    url = "https://bsky.social/xrpc/app.bsky.feed.getPostThread"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "uri": post_uri
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            thread = response.json().get('thread', {})
            post_data = thread.get('post', {})
            
            # Check if this is a reply
            is_reply = 'reply' in post_data.get('record', {})
            
            if is_reply:
                print(f"Processing a reply in thread: {post_uri}")
            else:
                print(f"Processing a main post: {post_uri}")
                
            return {
                'uri': post_data.get('uri'),
                'cid': post_data.get('cid'),
                'is_reply': is_reply
            }
    except Exception as e:
        print(f"Error getting post info: {str(e)}")
    return None

def post_reply(token, author_handle, reply_text, post_uri, bot_did):
    """Post a reply to a specific post."""
    url = "https://bsky.social/xrpc/com.atproto.repo.createRecord"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Get the post info including CID
    post_info = get_post_info(token, post_uri)
    if not post_info:
        print(f"Failed to get post info for URI: {post_uri}")
        return False
    
    print(f"Preparing reply for {'thread' if post_info['is_reply'] else 'main post'}")
    
    # Add mention to the reply text
    reply_with_mention = f"@{author_handle} {reply_text}"
    
    # Construct reply reference
    reply_ref = {
        "root": {
            "uri": post_info['uri'],
            "cid": post_info['cid']
        },
        "parent": {
            "uri": post_info['uri'],
            "cid": post_info['cid']
        }
    }
    
    # Create facet for the mention
    facets = [{
        "index": {
            "byteStart": 0,
            "byteEnd": len(author_handle) + 1  # +1 for the @ symbol
        },
        "features": [{
            "$type": "app.bsky.richtext.facet#mention",
            "did": get_user_did(token, author_handle)
        }]
    }]
    
    data = {
        "repo": bot_did,
        "collection": "app.bsky.feed.post",
        "record": {
            "text": reply_with_mention,
            "facets": facets,
            "$type": "app.bsky.feed.post",
            "createdAt": datetime.now(pytz.UTC).isoformat().replace('+00:00', 'Z'),
            "reply": reply_ref
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"Successfully posted reply to {'thread' if post_info['is_reply'] else 'main post'}")
            return True
        else:
            print(f"Failed to post reply: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error posting reply: {str(e)}")
        return False

def get_user_did(token, handle):
    """Get user's DID from their handle."""
    url = "https://bsky.social/xrpc/com.atproto.identity.resolveHandle"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "handle": handle
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get('did')
    except Exception as e:
        print(f"Error getting user DID: {str(e)}")
    return None

def get_auth_token():
    """Get fresh authentication tokens (access and refresh)."""
    url = "https://bsky.social/xrpc/com.atproto.server.createSession"
    data = {
        "identifier": os.getenv('BSKY_IDENTIFIER'),
        "password": os.getenv('BSKY_PASSWORD')
    }
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            access_token = response.json().get('accessJwt')
            refresh_token = response.json().get('refreshJwt')
            print("Successfully obtained new auth tokens")
            return access_token, refresh_token
        else:
            print(f"Failed to get auth token: {response.status_code} - {response.text}")
            return None, None
    except Exception as e:
        print(f"Exception during authentication: {str(e)}")
        return None, None

def refresh_access_token(refresh_token):
    """Get a new access token using the refresh token."""
    url = "https://bsky.social/xrpc/com.atproto.server.refreshSession"
    headers = {
        "Authorization": f"Bearer {refresh_token}"
    }
    
    try:
        response = requests.post(url, headers=headers)
        if response.status_code == 200:
            new_access_token = response.json().get('accessJwt')
            new_refresh_token = response.json().get('refreshJwt')
            print("Successfully refreshed access token")
            return new_access_token, new_refresh_token
        else:
            print(f"Failed to refresh token: {response.status_code} - {response.text}")
            return None, None
    except Exception as e:
        print(f"Exception during token refresh: {str(e)}")
        return None, None

def main():
    # Initialize token variables
    access_token = None
    refresh_token = None
    token_creation_time = None
    token_expiry = timedelta(hours=1)  # Tokens typically expire after 1 hour
    bot_did = None
    
    while True:
        try:
            current_time = datetime.now()
            print(f"\n[{current_time}] Starting new check...")
            
            # Check if we need new tokens (once per hour)
            if (access_token is None or 
                token_creation_time is None or 
                current_time - token_creation_time >= token_expiry):
                
                print("Getting new authentication tokens...")
                access_token, refresh_token = get_auth_token()
                token_creation_time = current_time
                
                if not access_token:
                    print("Failed to get authentication tokens. Waiting...")
                    time.sleep(60)
                    continue
                
                # Get bot DID only when getting new tokens
                bot_did = get_bot_did(access_token, os.getenv('BSKY_IDENTIFIER'))
                if not bot_did:
                    print("Failed to get bot DID. Waiting...")
                    time.sleep(60)
                    continue
                
                print("Successfully refreshed authentication (hourly update)")
            
            # Search for new posts (every minute)
            print("\nSearching for mentions from last minute...")
            df_mentions = search_mentions(access_token, os.getenv('BSKY_IDENTIFIER'))
            
            if df_mentions is not None and not df_mentions.empty:
                print(f"\nProcessing replies for {len(df_mentions)} posts...")
                
                for index, post in df_mentions.iterrows():
                    post_uri = post['reply_parent'] if post['reply_parent'] else post['uri']
                    author_handle = post['author_username']
                    print(f"\nAttempting to reply to:")
                    print(f"Post URI: {post_uri}")
                    print(f"Author: {author_handle}")
                    print(f"Content: {post['post_content']}")
                    
                    success = post_reply(access_token, 
                                      author_handle,
                                      "Thanks for tagging, I will get back to you soon.", 
                                      post_uri,
                                      bot_did)
                    if success:
                        print("Reply posted successfully")
                    else:
                        print("Failed to post reply")
                    
                    time.sleep(2)  # Wait between replies
            else:
                print("No new posts found that need replies")

            # Wait for next minute
            print("\nWaiting 60 seconds before next check...")
            time.sleep(60)
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            print("Waiting 60 seconds before retry...")
            time.sleep(60)

if __name__ == "__main__":
    main()