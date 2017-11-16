import boto3
import requests
import tweepy
import tempfile
import os.path
import logging
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

def handler(event, context):

    print(str(event))

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
        r = requests.get(url, {'q': q, 'per_page': 6}, headers=headers)
        r.raise_for_status()
        results = r.json()
        if results['total_count'] == 0:
            return
        messages = [x['commit']['message'] for x in results['items']]

        queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME)

        for m in messages:
            queue.send_message(MessageBody=m, MessageGroupId=yesterday)
    elif trigger_rule == 'Tweet':
        pass


def tweet(recipe, message):
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.secure = True
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)
    
    if recipe['image_url']:
        # Get the image
        r = requests.get(recipe['image_url'], stream=True)
        filename = recipe['image_url'].split('/')[-1]
        tfile = os.path.join(tempfile.mkdtemp(), filename)
        with open(tfile, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024): 
                if chunk: 
                    f.write(chunk)
                    f.flush()
        api.update_with_media(tfile, status=message)
    else:
        api.update(status=message)                    
    
if __name__ == '__main__':

    (recipe, message) = loop()
    logging.info("Posting message {}".format(message))
    tweet(recipe, message)
