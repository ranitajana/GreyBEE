import tweepy
import tweepy.client
from datetime import datetime, timedelta

# api_key = 'DdfuSO9ASZ9fY5IdyADS1tZvp'
# api_secret = '9GDuNAhaDmfwaxf5IpzQMhY2UeaH1anUhvHO2nw00CRpYAbB64'
# bearer_token = r'AAAAAAAAAAAAAAAAAAAAAF2HxAEAAAAAOP%2B6B58tHAf4xRcs2s4KzVv%2FIMk%3DTtNQq2cK6ELae1WF3pKkNMoB0J7YrprtHZK96aHkyxhJ2Z64LG'
# access_token = '4104591192-TzpOFI3dcWLmNVb8MyD8e0EDFILrQ1S4C6ybwpS'
# access_token_secret = 'wrbxFFxPY5UJwHyYaL7twBo1OJEtO9MBd6zTHAKVWl4dV'

api_key = '9c2oetuL39Wg1mjMOe1cteT0W'
api_secret = 'y2fHSDYQJmLLK33TRtmSmo2uJiDvJGAMVVePhwJlnAsk69WzxR'
bearer_token = r'AAAAAAAAAAAAAAAAAAAAAI%2BKxAEAAAAAbu35mKGK7wO8uIS2JeTdd5mnJDw%3DOwuRde7C3jaZHGzw6TgpfRZgpB4OrQrMInIODzUk3gCG2FgWQl'
access_token = '1859984090881277952-6FyH1IqD7OdTU6zAoAGUig2j5frkyz'
access_token_secret = 'jqFX11JjXv2X6b5DKWcDguHDTMa8xI7Qfjjn0iLtneXZq'

client = tweepy.Client(bearer_token, api_key, api_secret, access_token, access_token_secret)
auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
api = tweepy.API(auth)

client.create_tweet(text = "Hello World!!")

# class MyStream(tweepy.StreamingClient):
#     def on_tweet(self, tweet):
#         print(tweet.text)
        
#         try:
#             client.retweet(tweet.id)
#         except Exception as error:
#             print(error)
        
        
# stream = MyStream(bearer_token = bearer_token)
# rule = tweepy.StreamRule("(Sam Altman)(-is:retweet -is:reply)")

# stream.add_rules(rule)
# stream.filter()


# Check if the tweet was created in the last 15 minutes
        # tweet_time = tweet.created_at
        # if tweet_time is not None:
        #     time_difference = datetime.utcnow() - tweet_time.replace(tzinfo=None)
        #     if time_difference <= timedelta(minutes=15):
        #         print(tweet.text)
        #         try:
        #             client.retweet(tweet.id)
        #         except Exception as error:
        #             print(error)
