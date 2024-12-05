import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
import os
from typing import Optional



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

def generate_response(post_content: str, client) -> Optional[str]:
    """Generate an AI-powered response to a Bluesky post using OpenAI's API.
    Ensures responses are concise (under 300 characters) and contextually relevant."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are Greybot, a helpful AI enthusiast on Bluesky. 
                CRITICAL: Your response MUST be under 250 characters total (including spaces).
                Be concise, friendly, and relevant. Do not use hashtags or emojis."""},
                {"role": "user", "content": f"""Generate a very concise response (under 250 characters) to: {post_content}
                
                IMPORTANT: Response MUST be under 250 characters to allow for mentions."""}
            ],
            max_tokens=100,
            temperature=0.7,
            presence_penalty=0.6,  # Encourage more concise responses
            frequency_penalty=0.6
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Safety check: truncate if still too long
        if len(ai_response) > 250:
            ai_response = ai_response[:247] + "..."
            
        return ai_response
        
    except Exception as e:
        print(f"Error generating OpenAI response: {str(e)}")
        return None

def post_reply(token, author_handle, post_content, post_uri, bot_did, client):
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
    ai_response = generate_response(post_content, client)
    if not ai_response:
        return False
    
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
    """Post a series of connected posts as a thread on Bluesky.
    Maintains proper thread structure by linking posts using root and parent references.
    Returns True if all posts in the thread were successfully posted."""
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

def post_trending_content(token, bot_did, used_posts, used_topics, client, keywords):
    """Orchestrates the process of finding viral posts, generating thread content, and posting it to Bluesky.
    Manages tracking of used posts and topics to avoid duplicates.
    Returns True if the entire process completes successfully."""
    try:
        # Get viral posts
        print("Finding viral posts...")
        viral_posts = get_viral_posts(token, used_posts, keywords)
        
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
                
            print("Successfully posted unique content")
            return True
        else:
            print(f"Failed to post thread: {str(e)}")
            return False
            
    except Exception as e:
        print(f"Error in post_trending_content: {str(e)}")
        return False

def get_full_thread_context(token, post_uri):
    """Get the complete thread context by traversing up to the root post and collecting all relevant posts."""
    thread_context = []
    current_uri = post_uri
    visited_uris = set()  # To prevent infinite loops
    
    while current_uri and current_uri not in visited_uris:
        visited_uris.add(current_uri)
        url = "https://bsky.social/xrpc/app.bsky.feed.getPostThread"
        params = {
            "uri": current_uri,
            "depth": 10
        }
        
        try:
            response = requests.get(
                url, 
                headers={"Authorization": f"Bearer {token}"}, 
                params=params
            )
            
            if response.status_code == 200:
                thread_data = response.json().get('thread', {})
                
                # Get the current post's data
                post = thread_data.get('post', {})
                post_text = post.get('record', {}).get('text', '')
                post_author = post.get('author', {}).get('handle', '')
                created_at = post.get('record', {}).get('createdAt', '')
                
                # Add to context list with timestamp for ordering
                thread_context.append({
                    'author': post_author,
                    'text': post_text,
                    'created_at': created_at,
                    'uri': current_uri
                })
                
                # Check if this post is a reply
                reply_parent = post.get('record', {}).get('reply', {}).get('parent', {}).get('uri')
                if reply_parent:
                    current_uri = reply_parent
                else:
                    break  # We've reached the root post
                    
            else:
                print(f"Error retrieving thread: {response.status_code}")
                break
                
        except Exception as e:
            print(f"Error in get_full_thread_context: {str(e)}")
            break
    
    # Sort posts by timestamp to get chronological order
    thread_context.sort(key=lambda x: x['created_at'])
    
    return thread_context

def check_notifications(token, client):
    """Check for new notifications, analyze replies, and respond appropriately."""
    url = "https://bsky.social/xrpc/app.bsky.notification.listNotifications"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {
        "limit": 20,
        "seenAt": None
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Failed to get notifications: {response.status_code} - {response.text}")
            return False
            
        notifications = response.json().get('notifications', [])
        unseen = [n for n in notifications if not n.get('isRead', False)]
        
        if unseen:
            print(f"\nFound {len(unseen)} new notifications:")
            for notif in unseen:
                reason = notif.get('reason', 'notification')
                author = notif.get('author', {}).get('handle', 'unknown')
                text = notif.get('record', {}).get('text', '')
                
                # Only process reply notifications
                if reason == 'reply':
                    print(f"Processing reply from @{author}: {text[:100]}...")
                    
                    # Get the complete thread context
                    thread_context = get_full_thread_context(token, notif.get('uri'))
                    
                    if thread_context:
                        # Format the thread context for the AI
                        thread_conversation = "\n".join([
                            f"@{post['author']}: {post['text']}" 
                            for post in thread_context
                        ])
                        
                        # Analyze the reply and generate response using OpenAI
                        analysis_prompt = f"""Analyze this conversation thread and generate an appropriate response:

                        Full conversation thread (in chronological order):
                        {thread_conversation}

                        Latest reply from @{author}: {text}

                        Consider:
                        1. The complete context of the conversation from start to finish
                        2. The tone and content of all previous messages
                        3. The specific points or questions raised in the latest reply
                        4. Any recurring themes or topics in the thread
                        
                        Generate a friendly, relevant response under 280 characters that shows understanding of the full conversation context."""
                        
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4",
                                messages=[
                                    {"role": "system", "content": "You are a helpful AI assistant engaging in Bluesky conversations. Keep responses concise, relevant, and friendly."},
                                    {"role": "user", "content": analysis_prompt}
                                ],
                                max_tokens=100,
                                temperature=0.7
                            )
                            
                            ai_response = response.choices[0].message.content.strip()
                            if ai_response:
                                # Post the response
                                reply_uri = notif.get('uri')
                                success = post_reply(
                                    token=token,
                                    author_handle=author,
                                    post_content=text,
                                    post_uri=reply_uri,
                                    bot_did=get_bot_did(token, os.getenv('BSKY_IDENTIFIER')),
                                    client=client
                                )
                                if success:
                                    print(f"Successfully responded to @{author}'s reply")
                                else:
                                    print(f"Failed to post response to @{author}'s reply")
                            
                        except Exception as e:
                            print(f"Error generating AI response: {str(e)}")
                else:
                    print(f"- {reason} from @{author}: {text[:100]}...")
            
            # Mark notifications as seen
            seen_url = "https://bsky.social/xrpc/app.bsky.notification.updateSeen"
            seen_data = {
                "seenAt": datetime.now(pytz.UTC).isoformat().replace('+00:00', 'Z')
            }
            
            seen_response = requests.post(seen_url, headers=headers, json=seen_data)
            if seen_response.status_code == 200:
                print("Successfully marked notifications as seen")
                return True
            else:
                print(f"Failed to mark notifications as seen: {seen_response.status_code}")
                return False
                
        return True
        
    except Exception as e:
        print(f"Error checking notifications: {str(e)}")
        return False