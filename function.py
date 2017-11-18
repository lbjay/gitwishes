import time
import boto3
import tweepy
import requests
from decimal import Decimal
from os import getenv as env
from wordfilter import Wordfilter as BadWordFilter
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Attr

# six "OR"s is the limit for a single commit search query
# but it gets noisy if you start adding "i hope" or "i want" so whatevs
queries = [
    "i wish",
    "i really wish",
    "i just wish",
    "i seriously wish",
    "i just hope",
    "i really hope"
]

TWITTER_CONSUMER_KEY = env('TWITTER_CONSUMER_KEY')
TWITTER_CONSUMER_SECRET = env('TWITTER_CONSUMER_SECRET')
TWITTER_ACCESS_TOKEN = env('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = env('TWITTER_ACCESS_TOKEN_SECRET')
DB_TABLE_NAME = env('DB_TABLE_NAME')

dynamo = boto3.resource('dynamodb')
table = dynamo.Table(DB_TABLE_NAME)


def handler(event, context):

    if "TriggerRule" in event:
        # for testing
        trigger_rule = event["TriggerRule"]
    else:
        # the arn of the event trigger
        trigger_rule = event['resources'][0].split('/')[-1]

    print("triggered by {}".format(trigger_rule))

    if trigger_rule == 'CommitSearch':

        # find some wishes
        headers = {'Accept': 'application/vnd.github.cloak-preview'}
        url = 'https://api.github.com/search/commits'
        yesterday = datetime.strftime(
            datetime.now() - timedelta(1),
            '%Y-%m-%d'
        )
        q = '("{}") author-date:>{}'.format(
            '" OR "'.join(queries),
            yesterday
        )

        # this will get 30 results by default which should be more than enough
        r = requests.get(url, {'q': q}, headers=headers)
        print("requested url: {}".format(r.request.url))
        r.raise_for_status()
        results = r.json()

        print("found {} messages".format(results['total_count']))
        if results['total_count'] == 0:
            return

        bwf = BadWordFilter()

        with table.batch_writer(overwrite_by_pkeys=['MessageBody']) as batch:
            for item in results['items']:
                msg = item['commit']['message']
                author = item.get('author', {}).get('login', '-')
                html_url = item['html_url']
                score = item['score']

                if bwf.blacklisted(msg):
                    print("blacklisted: '{}', {}".format(msg, html_url))
                    continue

                if score < 1:
                    print("score too low: '{}', {}".format(msg, html_url))
                    continue

                batch.put_item(Item={
                    'MessageBody': msg,
                    'Author': author,
                    'HtmlUrl': html_url,
                    'Score': Decimal(str(score)),
                    'TTL': int(time.time() + 86400)  # expire them after a day
                })

                print("added: '{}', {}".format(msg, html_url))

    elif trigger_rule == 'Tweet':

        # setting a TTL doesn't automatically delete expired items :(
        scan = table.scan(FilterExpression=Attr('TTL').gte(int(time.time())))
        print("found {} items".format(scan['Count']))

        if scan['Count'] == 0:
            print("nothing to tweet!")
            return

        item = sorted(
            scan['Items'],
            key=lambda x: float(x['Score']),
            reverse=True)[0]

        try:
            print("tweeting '{}'".format(item['MessageBody']))
            tweet(item['MessageBody'])
        finally:
            table.delete_item(Key={'MessageBody': item['MessageBody']})


def tweet(message):
    auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
    auth.secure = True
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    api.update_status(message)
