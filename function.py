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
EXCLUDE_REPOS = env('EXCLUDE_REPOS', '').split(',')

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

    if trigger_rule == 'CommitSearchEvent':

        # find some wishes
        headers = {'Accept': 'application/vnd.github.cloak-preview'}
        url = 'https://api.github.com/search/commits'
        yesterday = datetime.strftime(
            datetime.now() - timedelta(1),
            '%Y-%m-%d'
        )
        q = '("{}") committer-date:>={}'.format(
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

        # overwrite_by_pkeys should eliminate dupes
        with table.batch_writer(overwrite_by_pkeys=['MessageBody']) as batch:
            for item in results['items']:

                msg = item['commit']['message']

                try:
                    author = item['author']['login']
                except:
                    author = None

                html_url = item['html_url']
                score = item['score']
                repo = item.get('repository', {}).get('name')

                # exclude noisy repos
                if repo is None or repo in EXCLUDE_REPOS:
                    print("exclude item from '{}' repo".format(repo))
                    continue

                # truncate if necessary
                msg = (msg[:277] + '...') if len(msg) > 280 else msg

                # verify an actual query matches as commit search will return
                # matches based on tokenization. .e.g a string like
                # "2017-06-13-i-wish-blah-blah" will get included
                if sum(x.lower() in msg.lower() for x in queries) == 0:
                    print("item {} did not match original query".format(msg))
                    continue

                # be nice
                if bwf.blacklisted(msg):
                    print("blacklisted: '{}', {}".format(msg, html_url))
                    continue

                # arbitrary!
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

    elif trigger_rule == 'TweetEvent':

        # setting a TTL doesn't automatically delete expired items :(
        exp = Attr('TTL').gt(int(time.time())) & Attr('Tweeted').not_exists()
        scan = table.scan(FilterExpression=exp)
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
            # mark item as used
            table.update_item(
                Key={'MessageBody': item['MessageBody']},
                AttributeUpdates={
                    'Tweeted': {'Value': int(time.time()), 'Action': 'PUT'}
                }
            )


def tweet(message):
    auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
    auth.secure = True
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    api.update_status(message)
