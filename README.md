# gitwishes

Tweets at https://twitter.com/gitwishes.

## Setup

* developed w/ python 3.6
* AWS account w/ permissions to create
    * CloudFormation stacks
    * DynamoDB tables
    * Lambda functions
    * IAM roles
    
## Usage

1. Clone the repo, virtualenv, yada yada
1. Install the "dev" requirements: `pip install -r requirements_dev.txt`
    1. note: you don't need to install the Lambda function requirements (`requirements.txt`)
    unless you're testing the function locally
1. create/determine an s3 bucket to use. The packaged Lambda function and dependencies will
    be uploaded here
1. copy `example.env` to `.env` and populate with your settings
1. assemble the Lambda function code: `invoke build-deps`
1. process the CloudFormation template and upload the code: `invoke package`
1. deploy the CloudFormation stack: `invoke deploy`
1. `invoke clean` will clean up the locally packaged dependencies and the stuff on s3
    (to save $$)

Those last three steps can be combined: `invoke build-deps package deploy`

You can wipe everything and start clean with: `invoke clean delete build-deps package deploy`

## Resource details

You can see the list of created AWS resources by viewing the CloudFormation stack at
https://console.aws.amazon.com/cloudformation/home

The "workflow" starts with two Cloudwatch Event Rules: one that triggers once a day,
the other every four hours (would be trivial to parameterize those intervals).

The once-a-day event triggers an AWS Lambda function to search github commits for messages
from the previous day matching variations of *"I wish"*, *"I really hope"*, etc. Results are filtered a bit, e.g. by search result score and @dariusk's [wordfilter](https://github.com/dariusk/wordfilter). 
Messages are then stored in DynamoDB with a 1-day expiration.

The every-4-hours event triggers the same Lambda function to pull off the highest scoring
message from the DynamoDB table and tweet it.

There's also an IAM::Role that gets created to allow the Lambda function to execute
and access DynamoDB.
