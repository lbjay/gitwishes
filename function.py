import boto3
import requests
import tweepy
from os import getenv as env
from datetime import datetime, timedelta

queries = [
    "i wish",
    "i really wish",
    "i just wish",
    "i seriously wish"
]

TWITTER_CONSUMER_KEY = env('TWITTER_CONSUMER_KEY')
TWITTER_CONSUMER_SECRET = env('TWITTER_CONSUMER_SECRET')
TWITTER_ACCESS_TOKEN = env('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = env('TWITTER_ACCESS_TOKEN_SECRET')
QUEUE_NAME = env('QUEUE_NAME')

sqs = boto3.resource('sqs')
queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME)

def handler(event, context):

    if "TriggerRule" in event:
        trigger_rule = event["TriggerRule"]
    else:
        trigger_rule = event['resources'][0].split('/')[-1]

    if trigger_rule == 'CommitSearch':

        # find some wishes
        headers = {'Accept': 'application/vnd.github.cloak-preview'}
        url = 'https://api.github.com/search/commits'
        yesterday = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
        q = '("{}") author-date:>{}'.format(
            '" OR "'.join(queries),
            yesterday
        )

        # this will get 30 results by default which should be more than enough
        r = requests.get(url, {'q': q}, headers=headers)
        r.raise_for_status()
        results = r.json()

        if results['total_count'] == 0:
            return
        print("found {} messages".format(results['total_count']))

        messages = [x['commit']['message'] for x in results['items']]

        for m in messages:
            queue.send_message(MessageBody=m, MessageGroupId=yesterday)

    elif trigger_rule == 'Tweet':

        while True:
            try:
                msg = queue.receive_messages()[0]
                msg.delete() # deletes from the queue
                tweet(msg.body)
                break
            except IndexError:
                pass


def tweet(message):
    auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
    auth.secure = True
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    api.update_status(message)

