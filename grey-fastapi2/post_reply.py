import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
import os
from dotenv import load_dotenv
import openai
from openai import OpenAI
from typing import Optional
import re

# Load environment variables at the start of your script
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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

def generate_response(post_content: str) -> Optional[str]:
    """Generate a response using OpenAI API."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are Greybot, a helpful AI assistant on Bluesky. 
                Keep responses concise, friendly, and under 280 characters. 
                Analyze the content of the post and provide a relevant, thoughtful response.
                Avoid generic responses and engage with the specific content."""},
                {"role": "user", "content": f"Generate a relevant response to this Bluesky post: {post_content}"}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        # If no response is generated, don't return the default message
        if not response.choices[0].message.content.strip():
            print("Error: Empty response from OpenAI")
            return None
            
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating OpenAI response: {str(e)}")
        return None

def post_reply(token, author_handle, post_content, post_uri, bot_did):
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
    
    # Generate AI response
    ai_response = generate_response(post_content)
    reply_with_mention = f"@{author_handle} {ai_response}"
    
    # Create facet for the mention
    facets = [{
        "index": {
            "byteStart": 0,
            "byteEnd": len(author_handle) + 1
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
            "reply": {
                "root": {
                    "uri": post_info['uri'],
                    "cid": post_info['cid']
                },
                "parent": {
                    "uri": post_info['uri'],
                    "cid": post_info['cid']
                }
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"Successfully posted AI-generated reply to {'thread' if post_info['is_reply'] else 'main post'}")
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

def get_viral_ai_posts(token: str, used_posts: set) -> list:
    """Get viral AI-related posts from Bluesky, excluding previously used ones."""
    url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
    
    # Expanded keywords for better variety
    ai_keywords = [
        # General AI
        "AI", "artificial intelligence", "machine learning",
        # Large Language Models
        "GPT", "LLM", "Claude", "Gemini", "Llama", "Mistral",
        # Companies
        "OpenAI", "Anthropic", "DeepMind", "Google AI",
        # Applications
        "AI image", "AI video", "generative AI",
        # Trending Topics
        "AI safety", "AI ethics", "AI regulation"
    ]
    
    viral_posts = []
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Get current time for filtering
        current_time = datetime.now(pytz.UTC)
        
        for keyword in ai_keywords:
            params = {
                "q": keyword,
                "limit": 50
            }
            
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                posts = response.json().get('posts', [])
                
                for post in posts:
                    # Skip if we've already used this post
                    post_text = post.get('record', {}).get('text', '')
                    if post_text in used_posts:
                        continue
                    
                    # Check post time (within last 6 hours)
                    post_time = datetime.fromisoformat(
                        post.get('record', {}).get('createdAt', '').replace('Z', '+00:00')
                    )
                    if (current_time - post_time).total_seconds() > 21600:  # 6 hours
                        continue
                    
                    likes = post.get('likeCount', 0)
                    reposts = post.get('repostCount', 0)
                    replies = post.get('replyCount', 0)
                    
                    # Enhanced engagement scoring
                    time_factor = 1 + (1 - (current_time - post_time).total_seconds() / 21600)
                    engagement = (likes + (reposts * 2) + replies) * time_factor
                    
                    if engagement > 10:
                        viral_posts.append({
                            'text': post_text,
                            'engagement': engagement,
                            'author': post.get('author', {}).get('handle', ''),
                            'likes': likes,
                            'reposts': reposts,
                            'timestamp': post_time
                        })
        
        # Remove duplicates and sort by engagement
        unique_posts = {post['text']: post for post in viral_posts}.values()
        return sorted(unique_posts, key=lambda x: x['engagement'], reverse=True)[:5]
        
    except Exception as e:
        print(f"Error getting viral posts: {str(e)}")
        return []

def generate_thread_content(viral_posts: list, used_topics: set) -> list:
    """Generate a focused thread about a single trending AI topic."""
    if not viral_posts:
        return None
    
    posts_content = "\n\n".join([
        f"Post by @{post['author']}:\n{post['text']}\n"
        f"Engagement: {post['engagement']} (Likes: {post['likes']}, Reposts: {post['reposts']})"
        for post in viral_posts
    ])
    
    try:
        # First, identify the main trending topic
        topic_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI analyst. Identify the single most significant "
                                            "and trending AI topic from the provided posts. Respond with just "
                                            "the topic name, no explanation."},
                {"role": "user", "content": f"What's the main trending AI topic in these posts?\n\n{posts_content}"}
            ],
            max_tokens=50,
            temperature=0.3
        )
        
        main_topic = topic_response.choices[0].message.content.strip()
        
        # Skip if we've recently covered this topic
        if main_topic in used_topics:
            print(f"Topic '{main_topic}' was recently covered, skipping...")
            return None
        
        # Now generate a focused thread about this topic
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"""You are an AI expert creating a focused thread about {main_topic}.
                Create a thread of 4-5 posts that deeply analyzes this specific topic. The thread should:
                
                1. Start with an introduction to {main_topic}
                2. Each subsequent post should explore a different aspect of {main_topic}
                3. End with key takeaways or future implications
                
                Each post MUST:
                - Be under 280 characters
                - Flow naturally from one post to the next
                - Stay strictly focused on {main_topic}
                - Use minimal emojis (1-2 per post)
                - Include relevant hashtags only in the final post
                
                Format as: 'POST 1:', 'POST 2:', etc."""},
                {"role": "user", "content": f"Create a focused thread about {main_topic}, using insights from these posts:\n\n{posts_content}"}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        # Split and clean the posts
        content = response.choices[0].message.content.strip()
        raw_posts = [p.strip() for p in content.split('POST') if p.strip()]
        
        thread_posts = []
        for post in raw_posts:
            clean_post = post.split(':', 1)[-1].strip()
            if len(clean_post) > 280:
                clean_post = clean_post[:277] + "..."
            thread_posts.append(clean_post)
        
        print(f"Generated thread about: {main_topic}")
        return thread_posts
        
    except Exception as e:
        print(f"Error generating thread content: {str(e)}")
        return None

def post_thread(token: str, bot_did: str, thread_posts: list) -> bool:
    """Post a series of posts as a thread."""
    url = "https://bsky.social/xrpc/com.atproto.repo.createRecord"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        root_uri = None
        root_cid = None
        parent_uri = None
        parent_cid = None
        
        for i, post_text in enumerate(thread_posts):
            data = {
                "repo": bot_did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "text": post_text,
                    "$type": "app.bsky.feed.post",
                    "createdAt": datetime.now(pytz.UTC).isoformat().replace('+00:00', 'Z'),
                }
            }
            
            # If this is a reply in the thread, add the reply reference
            if root_uri and root_cid:
                data["record"]["reply"] = {
                    "root": {
                        "uri": root_uri,
                        "cid": root_cid
                    },
                    "parent": {
                        "uri": parent_uri,
                        "cid": parent_cid
                    }
                }
            
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                print(f"Posted thread part {i+1}/{len(thread_posts)}")
                
                # Store the URIs for the thread
                if i == 0:  # First post becomes the root
                    root_uri = response.json()['uri']
                    root_cid = response.json()['cid']
                
                # Update parent for the next post
                parent_uri = response.json()['uri']
                parent_cid = response.json()['cid']
                
                # Small delay between posts
                time.sleep(2)
            else:
                print(f"Failed to post thread part {i+1}: {response.status_code} - {response.text}")
                return False
        
        return True
        
    except Exception as e:
        print(f"Error posting thread: {str(e)}")
        return False

def post_trending_content(token: str, bot_did: str, used_posts: set, used_topics: set) -> bool:
    """Post trending AI content as a thread."""
    try:
        # Get viral AI posts
        print("Finding viral AI posts...")
        viral_posts = get_viral_ai_posts(token, used_posts)
        
        if not viral_posts:
            print("No new viral posts found")
            return False
        
        # Generate thread content
        print("Generating thread content...")
        thread_posts = generate_thread_content(viral_posts, used_topics)
        
        if not thread_posts:
            print("Failed to generate thread content")
            return False
            
        print(f"Generated thread with {len(thread_posts)} posts")
        for i, post in enumerate(thread_posts, 1):
            print(f"Post {i}: {post}\n")
        
        # Post the thread
        print("Posting thread...")
        success = post_thread(token, bot_did, thread_posts)
        
        if success:
            # Update tracking sets
            for post in viral_posts:
                used_posts.add(post['text'])
            # Extract main topic from first post
            main_topic = thread_posts[0].split()[0:3]
            used_topics.add(" ".join(main_topic))
            
            # Limit set sizes
            if len(used_posts) > 1000:
                used_posts.clear()
            if len(used_topics) > 100:
                used_topics.clear()
                
            print("Successfully posted unique AI content")
            return True
        else:
            print(f"Failed to post thread: {str(e)}")
            return False
            
    except Exception as e:
        print(f"Error in post_trending_content: {str(e)}")
        return False

def main():
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
    
    while True:
        try:
            current_time = datetime.now()
            print(f"\n[{current_time}] Starting new check...")
            
            # Token refresh logic
            if (access_token is None or 
                token_creation_time is None or 
                current_time - token_creation_time >= token_expiry):
                
                print("Getting new authentication tokens...")
                access_token, refresh_token = get_auth_token()
                token_creation_time = current_time
                
                if not access_token:
                    print("Failed to get authentication tokens. Waiting...")
                    time.sleep(MENTION_CHECK_INTERVAL)
                    continue
                
                bot_did = get_bot_did(access_token, os.getenv('BSKY_IDENTIFIER'))
                if not bot_did:
                    print("Failed to get bot DID. Waiting...")
                    time.sleep(MENTION_CHECK_INTERVAL)
                    continue
            
            # Check if it's time to post a new thread
            if last_post_time is None or (current_time - last_post_time).total_seconds() >= THREAD_POST_INTERVAL:
                print("\nPosting new AI trending thread...")
                success = post_trending_content(access_token, bot_did, used_posts, used_topics)
                if success:
                    last_post_time = current_time
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
                        print(f"Reply posted: {success}")
                        time.sleep(2)  # Small delay between replies if multiple
                else:
                    print("No new mentions to process")
            except Exception as e:
                print(f"Error handling mentions: {e}")
                
            # Only wait after all processing is complete
            print(f"\nWaiting {MENTION_CHECK_INTERVAL} seconds before next check...")
            time.sleep(MENTION_CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            print(f"Waiting {MENTION_CHECK_INTERVAL} seconds before retry...")
            time.sleep(MENTION_CHECK_INTERVAL)

if __name__ == "__main__":
    print("Starting AI trending bot...")
    main()