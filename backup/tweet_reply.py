import tweepy
import time

# Authentication credentials
api_key = '9c2oetuL39Wg1mjMOe1cteT0W'
api_secret = 'y2fHSDYQJmLLK33TRtmSmo2uJiDvJGAMVVePhwJlnAsk69WzxR'
bearer_token = r'AAAAAAAAAAAAAAAAAAAAAI%2BKxAEAAAAAbu35mKGK7wO8uIS2JeTdd5mnJDw%3DOwuRde7C3jaZHGzw6TgpfRZgpB4OrQrMInIODzUk3gCG2FgWQl'
access_token = '1859984090881277952-6FyH1IqD7OdTU6zAoAGUig2j5frkyz'
access_token_secret = 'jqFX11JjXv2X6b5DKWcDguHDTMa8xI7Qfjjn0iLtneXZq'

client = tweepy.Client(bearer_token, api_key, api_secret, access_token, access_token_secret)
auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
api = tweepy.API(auth)

# Function to reply to mentions
def reply_to_mentions():
    # Get the most recent mentions
    mentions = api.mentions_timeline(count=10)  # Adjust count as needed
    for mention in mentions:
        print(f"Replying to {mention.user.screen_name}...")
        # Check if the bot has already replied to this mention
        if not mention.favorited:  # Avoid replying multiple times
            try:
                api.update_status(
                    status=f"@{mention.user.screen_name} Thank you for mentioning me!",
                    in_reply_to_status_id=mention.id,
                    auto_populate_reply_metadata=True
                )
                mention.favorite()  # Like the mention after replying
            except Exception as e:
                print(f"Error replying to {mention.id}: {e}")

# Continuously check for mentions every 60 seconds
while True:
    reply_to_mentions()
    time.sleep(60)  # Wait for 1 minute before checking again