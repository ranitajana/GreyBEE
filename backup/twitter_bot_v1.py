import tweepy
import time
import config
from tweepy.errors import TweepyException

# Authenticate to Twitter using OAuth 1.0a
auth = tweepy.OAuthHandler(config.API_KEY, config.API_SECRET_KEY)
auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_TOKEN_SECRET)

# Create API object
api = tweepy.API(auth, wait_on_rate_limit=True)

def reply_to_mentions():
    print("Retrieving mentions...")
    
    user_id = 'Ranita_Jana'  # Replace with your actual user ID or screen name
    
    try:
        print("Before call")
        # Fetch the latest 10 mentions
        mentions = api.mentions_timeline(count=10)  
        print("After call")
        
        if mentions:  # Check if there are any mentions
            for mention in mentions:
                print(f"Replying to {mention.user.screen_name}")
                try:
                    # Create a reply tweet
                    api.update_status(
                        status=f"@{mention.user.screen_name} Hi, Thank you for the mention!",
                        in_reply_to_status_id=mention.id
                    )
                    print("Replied successfully!")
                except Exception as e:
                    print(f"Error replying: {e}")
        else:
            print("No new mentions found.")
    
    # except tweepy.RateLimitError as e:
    #     print("Rate limit exceeded. Waiting for reset...")
    #     time.sleep(15 * 60)  # Wait for 15 minutes before retrying
    # except Exception as e:
    #     print(f"An error occurred: {e}")
        
    # 
    except TweepyException as e:
        print(f"An error occurred: {e}")


# Main loop to keep the bot running
while True:
    reply_to_mentions()
    time.sleep(60)  # Wait for 60 seconds before checking again