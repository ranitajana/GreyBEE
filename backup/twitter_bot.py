import tweepy
import time
import config

# Authenticate to Twitter using Bearer Token for v2
client = tweepy.Client(bearer_token='AAAAAAAAAAAAAAAAAAAAAF2HxAEAAAAAOP%2B6B58tHAf4xRcs2s4KzVv%2FIMk%3DTtNQq2cK6ELae1WF3pKkNMoB0J7YrprtHZK96aHkyxhJ2Z64LG', 
                       consumer_key=config.API_KEY,
                       consumer_secret=config.API_SECRET_KEY,
                       access_token=config.ACCESS_TOKEN,
                       access_token_secret=config.ACCESS_TOKEN_SECRET)

def reply_to_mentions():
    print("Retrieving mentions...")
    
    user_id = 'Ranita_Jana'  # Replace with your actual user ID
    
    try:
        print("Before call")
        # Fetch the latest 10 mentions
        mentions = client.get_users_mentions(id=user_id, max_results=10)  
        print("after call")
        if mentions.data:  # Check if there are any mentions
            for mention in mentions.data:
                print(f"Replying to {mention.author_id}")
                try:
                    # Create a reply tweet
                    client.create_tweet(text=f"@{mention.author_id} Hi, Thank you for the mention!", in_reply_to_tweet_id=mention.id)
                    print("Replied successfully!")
                except Exception as e:
                    print(f"Error replying: {e}")
        else:
            print("No new mentions found.")
    
    except tweepy.errors.TooManyRequests as e:
        print("Rate limit exceeded. Waiting for reset...")
        time.sleep(15 * 60)  # Wait for 15 minutes before retrying
    except Exception as e:
        print(f"An error occurred: {e}")

# Main loop to keep the bot running
while True:
    reply_to_mentions()
    time.sleep(60)  # Wait for 60 seconds before checking again