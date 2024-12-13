import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
import os
from typing import Optional
from config import MEMORY_UPDATE_TIME, MEMORY_UPDATE_TIMEZONE
import feedparser
from bs4 import BeautifulSoup
import json
import hashlib
import random



def get_post_thread(token, post_uri):
    """Retrieve the thread (including replies) for a specific post."""
    url = "https://bsky.social/xrpc/app.bsky.feed.getPostThread"
    params = {
        "uri": post_uri,
        "depth": 10  # Get 10 level deeper replies
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

# def has_bot_replied(token, post_uri, bot_handle):
#     """Check if the bot has already replied to this post."""
#     thread_data, _ = get_post_thread(token, post_uri)
#     if thread_data and 'replies' in thread_data:
#         replies = thread_data.get('replies', [])
#         for reply in replies:
#             if reply.get('post', {}).get('author', {}).get('handle') == bot_handle:
#                 print(f"Bot has already replied to {post_uri}")
#                 return True
#     return False

# def search_mentions(token, handle):
#     url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
    
#     current_time = datetime.now(pytz.UTC)
#     one_minute_ago = current_time - timedelta(minutes=1)
    
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json"
#     }
#     params = {
#         "q": f"mentions:{handle}",
#         "limit": 20
#     }
    
#     try:
#         response = requests.get(url, headers=headers, params=params)
#         response.raise_for_status()
        
#         posts = response.json().get('posts', [])
#         if not posts:
#             return None
        
#         recent_posts = []
#         for post in posts:
#             created_at = datetime.fromisoformat(post['record']['createdAt'].replace('Z', '+00:00'))
            
#             if created_at >= one_minute_ago:
#                 post_uri = post['uri']
                
#                 # Check if this is a reply
#                 reply_parent = None
#                 if 'reply' in post['record']:
#                     reply_parent = post['record']['reply']['parent']['uri']
#                     print(f"Found mention in a reply. Parent URI: {reply_parent}")
                
#                 if not has_bot_replied(token, post_uri, handle):
#                     post_details = {
#                         'post_id': post_uri.split('/')[-1],
#                         'uri': post_uri,
#                         'reply_parent': reply_parent,  # Add parent URI if it's a reply
#                         'author_username': post['author']['handle'],
#                         'created_at': convert_to_ist(post['record']['createdAt']),
#                         'post_content': post['record']['text'],
#                         'reply_count': len(post.get('replies', [])),
#                     }
#                     recent_posts.append(post_details)
#                     print(f"Found new post to reply: {post['record']['text'][:50]}...")
        
#         if not recent_posts:
#             return None
            
#         print(f"Found {len(recent_posts)} posts needing replies")
#         return pd.DataFrame(recent_posts)
        
#     except Exception as e:
#         print(f"Error in search_mentions: {str(e)}")
#         return None

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

def generate_response(post_content: str, client) -> Optional[str]:
    """Generate an AI-powered response to a Bluesky post using OpenAI's API.
    Ensures responses are concise (under 300 characters) and contextually relevant."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are GreyBEE, a social media influencer on Bluesky who posts engaging content about AI. 
                CRITICAL: Your response MUST be under 250 characters total (including spaces).
                Be concise, friendly, and relevant. Use hashtags and emojis."""},
                {"role": "user", "content": f"""Generate a very concise response (under 250 characters) to: {post_content}
                
                """}
            ],
            max_tokens=100,
            temperature=0.7,
            presence_penalty=0.6,  # Encourage more concise responses
            frequency_penalty=0.6
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Safety check: truncate if still too long
        if len(ai_response) > 300:
            ai_response = ai_response[:299] + "..."
            
        return ai_response
        
    except Exception as e:
        print(f"Error generating OpenAI response: {str(e)}")
        return None

def post_reply(token, author_handle, post_content, post_uri, bot_did, client, ai_response, bot_memory, is_meme=False):
    """Post reply with force stop check. Always mention author but format memes without quotes."""
    if bot_memory.should_force_stop():
        print(f"\n🛑 FORCE STOP: Memory update time - Reply cancelled")
        return False
        
    url = "https://bsky.social/xrpc/com.atproto.repo.createRecord"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Get the post info including CID
    thread_data, post_cid = get_post_thread(token, post_uri)
    if not thread_data or not post_cid:
        print(f"Failed to get post info for URI: {post_uri}")
        return False

    # Extract root post information
    root_uri = thread_data.get('post', {}).get('uri')
    root_cid = thread_data.get('post', {}).get('cid')
    
    if not root_uri or not root_cid:
        print("Failed to get root post information")
        return False

    # Always mention the author, but format meme responses differently
    if is_meme:
        # Remove any quotes from meme response
        clean_meme = ai_response.strip('"').strip("'")
        reply_text = f"@{author_handle} {clean_meme}"
    else:
        reply_text = f"@{author_handle} {ai_response}"

    # Always include facets for the mention
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
            "text": reply_text,
            "facets": facets,
            "$type": "app.bsky.feed.post",
            "createdAt": datetime.now(pytz.UTC).isoformat().replace('+00:00', 'Z'),
            "reply": {
                "root": {
                    "uri": root_uri,
                    "cid": root_cid
                },
                "parent": {
                    "uri": post_uri,
                    "cid": post_cid
                }
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"Successfully posted reply to @{author_handle}")
            # Add a shorter delay between posts (15-30 seconds)
            time.sleep(random.uniform(15, 30))
            return True
        else:
            print(f"Failed to post reply: {response.status_code} - {response.text}")
            # If rate limited, wait longer
            if response.status_code == 429:
                time.sleep(60)
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

def get_viral_posts(token: str, used_posts: set, keywords: list) -> list:
    """Search and retrieve viral posts from Bluesky based on provided keywords, filtering by engagement metrics 
    and excluding previously used posts. Posts must be within the last 6 hours and have significant engagement 
    (likes, reposts, replies). Returns a list of the top 5 most engaging posts."""
    
    url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
    viral_posts = []
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Get current time for filtering
        current_time = datetime.now(pytz.UTC)
        
        for keyword in keywords:
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

def generate_thread_content(viral_posts: list, used_topics: set, client) -> list:
    """Generate a cohesive thread of 4-5 posts about a trending topic identified from the viral posts.
    Uses OpenAI to identify the main topic and create engaging, informative content.
    Ensures no duplicate topics and maintains post length limits."""
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
                {"role": "system", "content": "You are an analyst. Identify the single most significant "
                                            "and trending topic from the provided posts. Respond with just "
                                            "the topic name, no explanation."},
                {"role": "user", "content": f"What's the main trending topic in these posts?\n\n{posts_content}"}
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
                {"role": "system", "content": f"""You are an expert creating a focused thread about {main_topic}.
                Create a thread of 4-5 posts that deeply analyzes this specific topic. The thread should:
                
                1. Start with an introduction to {main_topic}. Begin with a compelling hook that grabs attention.
                2. Each subsequent post should explore a different aspect of {main_topic}
                3. Conclude with an open-ended question that encourages discussion.
                4. Incorporate relevant hashtags to increase visibility
                5. Avoid using terms like Key details, conclusions, Final thoughts etc so that it flows naturally.
                
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

def upload_image_to_bsky(token: str, image_url: str) -> Optional[dict]:
    """Download image from URL and upload to Bluesky's blob storage."""
    try:
        # Download image
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        img_response = requests.get(image_url, headers=headers)
        if img_response.status_code != 200:
            print(f"Failed to download image: {img_response.status_code}")
            return None

        # Determine content type
        content_type = img_response.headers.get('content-type', 'image/jpeg')
        
        # Upload to Bluesky
        upload_url = "https://bsky.social/xrpc/com.atproto.repo.uploadBlob"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type
        }
        
        upload_response = requests.post(
            upload_url,
            headers=headers,
            data=img_response.content
        )

        if upload_response.status_code == 200:
            blob = upload_response.json().get('blob')
            print("Successfully uploaded image to Bluesky")
            return blob
        else:
            print(f"Failed to upload image: {upload_response.status_code}")
            return None

    except Exception as e:
        print(f"Error uploading image: {str(e)}")
        return None

def extract_article_content(url):
    """Extract main content and image from an article URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for elem in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            elem.decompose()
        
        # Try multiple content extraction strategies
        content = None
        
        # Strategy 1: Look for article tag
        if not content:
            article = soup.find('article')
            if article:
                content = ' '.join([p.text.strip() for p in article.find_all('p')])
        
        # Strategy 2: Look for common content class names
        if not content:
            content_classes = ['content', 'article-content', 'post-content', 'entry-content']
            for class_name in content_classes:
                content_div = soup.find(class_=class_name)
                if content_div:
                    content = ' '.join([p.text.strip() for p in content_div.find_all('p')])
                    break
        
        # Strategy 3: Fall back to meta description
        if not content:
            meta_desc = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
            if meta_desc:
                content = meta_desc.get('content', '')
        
        # Image extraction (existing code)
        image_url = None
        image_candidates = [
            soup.find('meta', property='og:image'),
            soup.find('meta', property='twitter:image'),
            soup.find('meta', property='image'),
            soup.find('article').find('img') if soup.find('article') else None,
            soup.find(class_=['featured-image', 'article-image', 'post-image'])
        ]
        
        for candidate in image_candidates:
            if candidate:
                image_url = (candidate.get('content') or candidate.get('src'))
                if image_url:
                    if not image_url.startswith(('http://', 'https://')):
                        base_url = '/'.join(url.split('/')[:3])
                        image_url = f"{base_url}{image_url if image_url.startswith('/') else f'/{image_url}'}"
                    break
        
        if not content and not image_url:
            print(f"Failed to extract any content or image from {url}")
            return None, None
            
        return content, image_url
        
    except Exception as e:
        print(f"Error extracting article content: {str(e)}")
        return None, None

def post_thread(token: str, bot_did: str, thread_posts: list, embed_url: Optional[str] = None, image_url: Optional[str] = None) -> bool:
    """Post a series of connected posts as a thread on Bluesky."""
    url = "https://bsky.social/xrpc/com.atproto.repo.createRecord"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Handle image upload if provided
        image_blob = None
        if image_url:
            print(f"Uploading image from: {image_url}")
            image_blob = upload_image_to_bsky(token, image_url)
            if not image_blob:
                print("Failed to upload image, continuing with link-only embed")

        root_uri = None
        root_cid = None
        parent_uri = None
        parent_cid = None
        
        for i, post_text in enumerate(thread_posts):
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                data = {
                    "repo": bot_did,
                    "collection": "app.bsky.feed.post",
                    "record": {
                        "text": post_text,
                        "$type": "app.bsky.feed.post",
                        "createdAt": datetime.now(pytz.UTC).isoformat().replace('+00:00', 'Z'),
                    }
                }
                
                # Add embed for first post if embed_url is provided
                if i == 0 and embed_url:
                    embed_data = {
                        "$type": "app.bsky.embed.external",
                        "external": {
                            "uri": embed_url,
                            "title": thread_posts[0],
                            "description": ""
                        }
                    }
                    
                    # Add image to embed if available
                    if image_blob:
                        embed_data["external"]["thumb"] = image_blob
                    
                    data["record"]["embed"] = embed_data
                    print(f"Adding link preview with image for URL: {embed_url}")
                
                # Add thread reply data if not first post
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
                
                # Wait before posting first post to ensure proper embed
                if i == 0:
                    print("Waiting for link preview to generate...")
                    time.sleep(10)
                
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code == 200:
                    print(f"Posted thread part {i+1}/{len(thread_posts)}")
                    
                    if i == 0:  # First post becomes the root
                        root_uri = response.json()['uri']
                        root_cid = response.json()['cid']
                    
                    parent_uri = response.json()['uri']
                    parent_cid = response.json()['cid']
                    
                    time.sleep(2)  # Small delay between posts
                    break  # Success, exit retry loop
                    
                elif response.status_code == 502:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"Got 502 error, retrying... (attempt {retry_count + 1}/{max_retries})")
                        time.sleep(5)
                    else:
                        print(f"Failed to post thread part {i+1} after {max_retries} attempts")
                        return False
                else:
                    print(f"Failed to post thread part {i+1}: {response.status_code} - {response.text}")
                    return False
        
        print("Successfully posted complete thread!")
        return True
        
    except Exception as e:
        print(f"Error in post_thread: {str(e)}")
        return False

def post_trending_content(access_token, bot_did, used_posts, used_topics, client, keywords, bot_memory):
    """Post trending content with force stop check."""
    try:
        # Initial check
        if bot_memory.should_force_stop():
            print(f"\n🛑 FORCE STOP: Memory update time - Thread posting cancelled")
            return False

        # Get viral posts
        print("Finding viral posts...")
        viral_posts = get_viral_posts(access_token, used_posts, keywords)
        
        if not viral_posts:
            print("No new viral posts found")
            return False
        
        # Generate thread content
        print("Generating thread content...")
        thread_posts = generate_thread_content(viral_posts, used_topics, client)
        
        if not thread_posts:
            print("Failed to generate thread content")
            return False
            
        print(f"Generated thread with {len(thread_posts)} posts")
        for i, post in enumerate(thread_posts, 1):
            print(f"Post {i}: {post}\n")
        
        # Post the thread
        print("Posting thread...")
        success = post_thread(access_token, bot_did, thread_posts)
        
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
                
            print("Successfully posted unique content")
            return True
        else:
            print("Failed to post thread")
            return False
            
    except Exception as e:
        print(f"Error in post_trending_content: {str(e)}")
        return False

def get_full_thread_context(token, post_uri, client_atproto):
    """Get the full context of a thread for better response generation."""
    try:
        thread_data, _ = get_post_thread(token, post_uri)
        if not thread_data:
            return None
            
        thread_context = []
        
        # Extract root post if it exists
        root = thread_data.get('post', {})
        if root:
            thread_context.append({
                'text': root.get('record', {}).get('text', ''),
                'author': root.get('author', {}).get('handle', ''),
                'is_root': True,
                'depth': 0
            })
            
        # Extract replies
        replies = thread_data.get('replies', [])
        for depth, reply in enumerate(replies, 1):
            thread_context.append({
                'text': reply.get('post', {}).get('record', {}).get('text', ''),
                'author': reply.get('post', {}).get('author', {}).get('handle', ''),
                'is_root': False,
                'depth': depth
            })
            
        return thread_context
        
    except Exception as e:
        print(f"Error getting thread context: {str(e)}")
        return None

def get_reply_details(notification):
    """Extract URI and CID from a reply notification."""
    try:
        uri = notification.get('uri')
        cid = notification.get('cid')
        author = notification.get('author', {}).get('handle', 'unknown')
        print(f"Reply from @{author}:")
        print(f"URI: {uri}")
        print(f"CID: {cid}")
        return uri, cid
    except Exception as e:
        print(f"Error getting reply details: {str(e)}")
        return None, None

def check_notifications(token, client, client_atproto, bot_memory):
    """Check notifications with force stop check."""
    try:
        # Initial check
        if bot_memory.should_force_stop():
            print(f"\n🛑 FORCE STOP: Memory update time - Notifications check cancelled")
            return

        url = "https://bsky.social/xrpc/app.bsky.notification.listNotifications"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # Calculate timestamp for 1 minute ago
        one_minute_ago = datetime.now(pytz.UTC) - timedelta(minutes=1)
        
        # Get notifications
        params = {
            "limit": 20  # Reasonable limit for 1-minute window
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Failed to get notifications: {response.status_code}")
            return
            
        notifications = response.json().get('notifications', [])
        if not notifications:
            print("No notifications found")
            return
            
        # Filter notifications from the last minute
        recent_notifications = []
        for notif in notifications:
            notif_time = datetime.fromisoformat(notif.get('indexedAt').replace('Z', '+00:00'))
            if notif_time >= one_minute_ago:
                recent_notifications.append(notif)
        
        if not recent_notifications:
            print("No new notifications in the last minute")
            return
            
        print(f"\nFound {len(recent_notifications)} new notifications in the last minute:")
        
        # Process recent notifications
        processed_any = False
        for notif in recent_notifications:
            reason = notif.get('reason')
            print(f"\nProcessing notification type: {reason}")
            
            # Handle both mentions and replies
            if reason in ['mention', 'reply']:
                author = notif.get('author', {}).get('handle')
                text = notif.get('record', {}).get('text', '')
                
                # Debug prints
                print(f"\nNotification details:")
                print(f"Author: {author}")
                print(f"Text: {text}")
                print(f"Time: {notif.get('indexedAt')}")
                
                # Get reply details
                uri = notif.get('uri')
                cid = notif.get('cid')
                
                if not uri or not cid:
                    print(f"Missing URI or CID for {reason}")
                    continue
                
                print(f"{reason.capitalize()} from @{author}:")
                print(f"URI: {uri}")
                print(f"CID: {cid}")
                
                # Get the complete thread context
                thread_context = get_full_thread_context(token, uri, client_atproto)
                
                if thread_context:
                    # Format the thread context for the AI
                    thread_conversation = "\n".join([
                        f"@{post['author']} ({'ROOT' if post['is_root'] else f'REPLY at depth {post['depth']}'}):\n{post['text']}" 
                        for post in thread_context
                    ])
                    
                    print("\nGenerating response based on full thread context...")
                    
                    try:
                        # First attempt without memory
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are a helpful AI assistant engaging in Bluesky conversations. Keep responses concise, relevant, and friendly."},
                                {"role": "user", "content": f"""You are responding to a conversation thread on Bluesky. Here's the complete thread:

                                {thread_conversation}

                                The latest {reason} is from @{author}: "{text}"

                                Please generate a response that:
                                1. Shows understanding of the entire conversation
                                2. Directly addresses the latest message
                                3. Is concise (under 280 characters)
                                4. Is relevant and helpful

                                Generate response:"""}
                            ],
                            max_tokens=100,
                            temperature=0.7
                        )
                        
                        ai_response = response.choices[0].message.content.strip()
                        
                        # If the response seems generic or uncertain (you can customize these conditions)
                        if any(phrase in ai_response.lower() for phrase in [
                            "i'm not sure", "i cannot", "i don't know", "unclear",
                            "could you clarify", "please provide more context"
                        ]):
                            print("\nInitial response seems uncertain, searching memory for context...")
                            
                            # Search memory using the entire thread context
                            memories = bot_memory.search_relevant_memory(
                                query_text=f"{thread_conversation}\n\nLatest message: {text}",
                                limit=5
                            )
                            
                            if memories:
                                # Format memories for context
                                memory_context = "\n\n".join([
                                    f"Previous interaction ({mem['position']}):\n{mem['text']}"
                                    for mem in memories
                                ])
                                
                                # Try again with memory context
                                response = client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    messages=[
                                        {"role": "system", "content": "You are a helpful AI assistant engaging in Bluesky conversations. Use the provided memory of past interactions to give more informed and contextual responses. Keep responses concise and relevant."},
                                        {"role": "user", "content": f"""You are responding to a conversation thread on Bluesky. Here's the complete thread:

                                        {thread_conversation}

                                        The latest {reason} is from @{author}: "{text}"

                                        Here are relevant memories from past interactions:
                                        {memory_context}

                                        Please generate a response that:
                                        1. Shows understanding of the entire conversation
                                        2. Uses relevant context from past interactions
                                        3. Directly addresses the latest message
                                        4. Is concise (under 280 characters)
                                        5. Is relevant and helpful

                                        Generate response:"""}
                                    ],
                                    max_tokens=100,
                                    temperature=0.7
                                )
                                
                                ai_response = response.choices[0].message.content.strip()
                                print("\nGenerated new response using memory context")
                        
                        # Continue with the existing code to post the response
                        if ai_response:
                            if len(ai_response) > 280:
                                ai_response = ai_response[:277] + "..."
                            
                            print(f"\nFinal response: {ai_response}")
                            
                            success = post_reply(
                                token=token,
                                author_handle=author,
                                post_content=text,
                                post_uri=uri,
                                bot_did=get_bot_did(token, os.getenv('BSKY_IDENTIFIER')),
                                client=client,
                                ai_response=ai_response,
                                bot_memory=bot_memory
                            )
                            if success:
                                processed_any = True
                                print(f"Successfully responded to @{author}'s {reason}")
                            else:
                                print(f"Failed to post response to @{author}'s {reason}")
                    
                    except Exception as e:
                        print(f"Error generating/posting AI response: {str(e)}")
                
                time.sleep(2)  # Small delay between processing notifications
        
        # Mark notifications as seen if we processed any
        if processed_any:
            try:
                seen_url = "https://bsky.social/xrpc/app.bsky.notification.updateSeen"
                seen_data = {
                    "seenAt": datetime.now(pytz.UTC).isoformat().replace('+00:00', 'Z')
                }
                seen_response = requests.post(seen_url, headers=headers, json=seen_data)
                if seen_response.status_code == 200:
                    print("\nSuccessfully marked notifications as seen")
                else:
                    print(f"\nFailed to mark notifications as seen: {seen_response.status_code}")
            
            except Exception as e:
                print(f"Error marking notifications as seen: {str(e)}")
            
    except Exception as e:
        print(f"Error checking notifications: {str(e)}")

# def generate_ai_response(client, thread_context, author, text, reason, bot_memory):
#     """Generate AI response with force stop checks."""
#     try:
#         # Check before starting
#         if bot_memory.should_force_stop():
#             return None

#         # First attempt without memory
#         if bot_memory.should_force_stop():
#             return None
            
#         response = client.chat.completions.create(...)
        
#         # Check before memory search
#         if bot_memory.should_force_stop():
#             return None
            
#         memories = bot_memory.search_relevant_memory(...)
        
#         # Check before second attempt
#         if bot_memory.should_force_stop():
#             return None
            
#         # ... rest of function ...
#         return response  # or whatever the function should return
        
#     except Exception as e:
#         print(f"Error generating AI response: {str(e)}")
#         return None

def fetch_ai_news():
    """Fetch AI news from multiple reliable sources."""
    news_sources = {
        'MIT Technology Review': {
            'url': 'https://www.technologyreview.com/topic/artificial-intelligence/feed',
            'type': 'rss'
        },
        'TechCrunch AI': {
            'url': 'https://techcrunch.com/category/artificial-intelligence/feed',
            'type': 'rss'
        },
        'VentureBeat AI': {
            'url': 'https://venturebeat.com/category/ai/feed/',
            'type': 'rss'
        },
        'Wired AI': {
            'url': 'https://www.wired.com/tag/artificial-intelligence/feed',
            'type': 'rss'
        }
    }
    
    news_items = []
    
    for source_name, source_info in news_sources.items():
        try:
            if source_info['type'] == 'rss':
                feed = feedparser.parse(source_info['url'])
                for entry in feed.entries[:5]:  # Get 5 most recent entries
                    # Create unique ID for deduplication
                    content_hash = hashlib.md5(
                        f"{entry.title}{entry.link}".encode()
                    ).hexdigest()
                    
                    # Extract main image if available
                    image_url = None
                    if hasattr(entry, 'content') and entry.content:
                        soup = BeautifulSoup(entry.content[0].value, 'html.parser')
                        img = soup.find('img')
                        if img and img.get('src'):
                            image_url = img['src']
                    
                    news_items.append({
                        'id': content_hash,
                        'title': entry.title,
                        'link': entry.link,
                        'summary': entry.summary,
                        'published': entry.published,
                        'source': source_name,
                        'image_url': image_url
                    })
                    
        except Exception as e:
            print(f"Error fetching from {source_name}: {str(e)}")
    
    return sorted(news_items, key=lambda x: x['published'], reverse=True)

def generate_news_thread(news_item, article_content, client):
    """Generate an engaging thread about an AI news article."""
    try:
        thread_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are an AI expert creating engaging threads about AI news.
                Create 3-5 posts that break down the news article (choose the number based on content complexity).
                
                Required format:
                1. First post: Attention-grabbing headline that includes specific details (NO link - it will be auto-embedded)
                2. Second post: SPECIFIC key details or main impact (never use generic phrases like "Here's what makes this significant")
                3. Third post: CONCRETE implications or analysis (never use generic phrases like "The implications are")
                [4-5]. Additional posts only if needed for important details
                Final post: Clear conclusion with 2-3 relevant hashtags
                
                STRICT REQUIREMENTS:
                - Generate 3-5 posts depending on content complexity
                - Each post MUST contain SPECIFIC details, never generic statements
                - Each post MUST be under 280 characters
                - Include 1-2 relevant emojis per post
                - DO NOT include URLs or links
                - Last post MUST end with hashtags
                
                BAD examples (DO NOT USE):
                ❌ "Here's what makes this significant..."
                ❌ "The implications are..."
                ❌ "This could be important..."
                
                GOOD examples:
                ✅ "Google's new AI model achieves 98% accuracy in medical diagnosis, reducing error rates by 50% compared to human doctors 🏥"
                ✅ "The model processes 1M patient records in seconds, using advanced neural networks to detect patterns humans might miss 🔍"
                ✅ "This breakthrough could save $2B annually in healthcare costs and reduce misdiagnosis rates by 60% in rural areas 📊"
                """},
                {"role": "user", "content": f"""Create a thread (3-5 posts) about this AI news:
                
                Title: {news_item['title']}
                
                Summary: {news_item['summary']}
                
                Additional Content: {article_content[:1500] if article_content else ''}
                
                Remember: 
                - Each post MUST contain SPECIFIC details and numbers when possible
                - NO generic statements like "Here's what makes this significant"
                - Each post must be under 280 characters
                - Use 3-5 posts based on content complexity"""}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        # Process and validate the generated posts
        content = thread_response.choices[0].message.content.strip()
        thread_posts = []
        
        # Split content by numbered markers and clean
        for line in content.split('\n'):
            line = line.strip()
            if line and any(line.startswith(f"{i}.") for i in range(1, 6)):  # Changed to 6 to allow 5 posts
                post = line[2:].strip()
                if len(post) > 280:
                    post = post[:277] + "..."
                    
                # Check for generic phrases
                generic_phrases = [
                    "here's what makes this significant",
                    "the implications are",
                    "this could be important",
                    "what makes this interesting",
                    "this is significant because",
                    "here's why this matters"
                ]
                
                if any(phrase in post.lower() for phrase in generic_phrases):
                    print(f"Detected generic phrase in post: {post}")
                    continue  # Skip this post and try regenerating
                    
                thread_posts.append(post)
        
        # Validate number of posts
        if len(thread_posts) < 3 or len(thread_posts) > 5:
            print(f"Generated {len(thread_posts)} posts, which is outside the allowed range (3-5). Regenerating...")
            return generate_news_thread(news_item, article_content, client)
            
        # Final validation of post content
        for post in thread_posts:
            if len(post.split()) < 5:  # Check if post is too short
                print("Post too short, regenerating...")
                return generate_news_thread(news_item, article_content, client)
        
        return thread_posts
        
    except Exception as e:
        print(f"Error generating news thread: {str(e)}")
        print("Full error details:", str(e))
        return None

def post_ai_news(access_token, bot_did, used_posts, client, bot_memory):
    """Post AI news content with duplicate checking."""
    try:
        # Check for force stop
        if bot_memory.should_force_stop():
            print(f"\n🛑 FORCE STOP: Memory update time - News posting cancelled")
            return False
        
        # Fetch recent AI news
        print("\nFetching recent AI news...")
        news_items = fetch_ai_news()
        
        if not news_items:
            print("No news items found")
            return False
        
        # Find first unposted news item
        for news_item in news_items:
            # Add debug print for article ID
            print(f"\nChecking news item ID: {news_item['id']}")
            print(f"Is article already used? {news_item['id'] in used_posts}")
            
            if news_item['id'] not in used_posts:
                print(f"\nProcessing news: {news_item['title']}")
                
                # Extract full article content and image
                article_content, article_image = extract_article_content(news_item['link'])
                if not article_content:
                    print("Failed to extract article content")
                
                # Generate thread content
                thread_posts = generate_news_thread(news_item, article_content, client)
                
                if thread_posts:
                    print(f"\nGenerated {len(thread_posts)} posts for news thread:")
                    for i, post in enumerate(thread_posts, 1):
                        print(f"\nPost {i}:")
                        print(post)
                    
                    # Post the thread with link preview and image
                    success = post_thread(
                        access_token, 
                        bot_did, 
                        thread_posts, 
                        embed_url=news_item['link'],
                        image_url=article_image
                    )
                    
                    if success:
                        used_posts.add(news_item['id'])
                        print(f"\n✅ Successfully posted news thread about: {news_item['title']}")
                        return True
                    else:
                        print("\n❌ Failed to post news thread")
                else:
                    print("Failed to generate thread posts")
                
                break
        
        print("\nNo new AI news items to post")
        return False
        
    except Exception as e:
        print(f"Error posting AI news: {str(e)}")
        return False

def save_used_content(used_posts, used_topics, filename='used_content.json'):
    """Save used content to prevent duplicates across restarts."""
    try:
        content = {
            'posts': list(used_posts),
            'topics': list(used_topics)
        }
        with open(filename, 'w') as f:
            json.dump(content, f)
        print(f"Saved {len(used_posts)} used posts and {len(used_topics)} used topics")
    except Exception as e:
        print(f"Error saving used content: {str(e)}")

def load_used_content(filename='used_content.json'):
    """Load previously used content."""
    try:
        with open(filename, 'r') as f:
            content = json.load(f)
        return set(content.get('posts', [])), set(content.get('topics', []))
    except FileNotFoundError:
        return set(), set()
    except Exception as e:
        print(f"Error loading used content: {str(e)}")
        return set(), set()

def generate_meme_response(post_content, thread_context, client):
    """Generate witty text-meme responses that are contextually relevant and professional."""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """You are a witty AI expert who creates clever, contextual responses 
                to AI discussions. Your responses should demonstrate deep understanding of AI/ML while being 
                entertaining and professional.

                Response Style Guide:
                1. Industry Insights with Wit:
                "When you realize your AI model's 99.9% accuracy was just memorizing the training data 📊"

                2. Technical Humor:
                "Nobody:
                Transformer attention heads: 'Everything is important!' 🎯"

                3. Development Reality:
                "Me when the model finally converges:
                *GPU immediately runs out of memory* 💰"

                4. Research vs Reality:
                "That moment when your 'simple 3-layer architecture' needs 
                17 callbacks and a prayer to the CUDA gods ⚡"

                5. AI Community Inside Jokes:
                "Everyone: Just increase the batch size
                My GPU: We don't do that here 🎮"

                Key Requirements:
                - Show deep understanding of AI/ML concepts
                - Reference specific technical details from the thread
                - Use industry-specific terminology accurately
                - Keep it professional yet entertaining
                - Make it relatable to AI/ML practitioners
                - Include exactly one relevant emoji
                - Stay under 240 characters
                - Use meme formats like 'Nobody:', 'When you realize', etc.
                
                Advanced Techniques:
                - Use technical parallels
                - Reference real ML workflows
                - Include specific ML metrics/parameters
                - Play on common ML debugging scenarios
                - Reference current AI trends/tools
                - Use popular meme formats with AI twists"""},
                {"role": "user", "content": f"""Create a witty, technically-accurate response to this AI discussion:
                
                Full Thread Context: {thread_context}
                Latest Post: {post_content}
                
                Requirements:
                - Reference specific technical elements from the discussion
                - Show understanding of the context
                - Be clever but professional
                - Include relevant AI/ML terminology
                - Use one of these formats:
                  * "Nobody: ..."
                  * "When you realize..."
                  * "That moment when..."
                  * "Me when..."
                  * "Everyone: ..."
                """}
            ],
            max_tokens=100,
            temperature=0.85  # Balanced between creativity and coherence
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Clean up and validate response
        if len(ai_response) > 240:
            ai_response = ai_response[:237] + "..."
            
        # Ensure response has technical merit
        technical_terms = ['model', 'training', 'neural', 'layer', 'data', 
                         'accuracy', 'loss', 'GPU', 'inference', 'parameters',
                         'batch', 'epoch', 'gradient', 'optimizer', 'transformer',
                         'attention', 'fine-tune', 'dataset', 'validation']
        has_technical_content = any(term in ai_response.lower() for term in technical_terms)
        
        # Ensure response uses a meme format
        meme_patterns = [
            "when you realize",
            "that moment when",
            "me when",
            "nobody:",
            "everyone:"
        ]
        has_meme_format = any(pattern in ai_response.lower() for pattern in meme_patterns)
        
        if not has_technical_content or not has_meme_format:
            # Try again if response lacks either technical substance or meme format
            return generate_meme_response(post_content, thread_context, client)
            
        return ai_response
        
    except Exception as e:
        print(f"Error generating meme response: {str(e)}")
        return None

def find_popular_ai_discussions(token, client_atproto, used_meme_responses, min_engagement=5):
    """Find popular AI-related discussions to engage with."""
    try:
        popular_posts = []
        ai_keywords = [
            "artificial intelligence", "machine learning", "AI", 
            "neural networks", "deep learning", "GPT", "LLM",
            "chatgpt", "claude", "gemini"
        ]
        
        # Common English words to check for language detection
        english_markers = [
            'the', 'is', 'are', 'and', 'or', 'but', 'in', 'on', 'at',
            'with', 'for', 'to', 'of', 'this', 'that', 'these', 'those'
        ]
        
        for keyword in ai_keywords:
            url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
            headers = {"Authorization": f"Bearer {token}"}
            params = {"q": keyword, "limit": 20}
            
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                posts = response.json().get('posts', [])
                
                for post in posts:
                    post_uri = post.get('uri')
                    if post_uri in used_meme_responses:
                        continue
                        
                    post_text = post.get('record', {}).get('text', '').lower()
                    
                    # Check if post is in English
                    english_word_count = sum(1 for marker in english_markers if f" {marker} " in f" {post_text} ")
                    if english_word_count < 2:  # Require at least 2 English markers
                        continue
                    
                    engagement = (
                        post.get('likeCount', 0) + 
                        post.get('replyCount', 0) * 1.5 +
                        post.get('repostCount', 0) * 2
                    )
                    
                    if engagement >= min_engagement:
                        post_details = {
                            'uri': post.get('uri'),
                            'text': post.get('record', {}).get('text', ''),
                            'author': post.get('author', {}).get('handle'),
                            'engagement': engagement,
                            'created_at': post.get('record', {}).get('createdAt')
                        }
                        
                        if not any(p['uri'] == post_details['uri'] for p in popular_posts):
                            popular_posts.append(post_details)
            
            time.sleep(1)  # Rate limiting
        
        sorted_posts = sorted(popular_posts, key=lambda x: x['engagement'], reverse=True)
        print(f"Found {len(sorted_posts)} popular English AI discussions")
        
        # More detailed logging
        if len(sorted_posts) == 0:
            print("\nDebug: No English posts met the minimum engagement threshold of", min_engagement)
        else:
            for idx, post in enumerate(sorted_posts[:5], 1):
                print(f"\n{idx}. @{post['author']} (engagement: {post['engagement']:.1f}):")
                print(f"Text: {post['text'][:100]}...")
        
        return sorted_posts
        
    except Exception as e:
        print(f"Error finding popular discussions: {str(e)}")
        return []

def save_used_meme_responses(used_meme_responses, filename='used_meme_responses.json'):
    """Save URIs of posts we've already responded to with memes."""
    try:
        with open(filename, 'w') as f:
            json.dump(list(used_meme_responses), f)
        print(f"Saved {len(used_meme_responses)} used meme responses")
    except Exception as e:
        print(f"Error saving used meme responses: {str(e)}")

def load_used_meme_responses(filename='used_meme_responses.json'):
    """Load previously used meme response URIs."""
    try:
        with open(filename, 'r') as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()
    except Exception as e:
        print(f"Error loading used meme responses: {str(e)}")
        return set()