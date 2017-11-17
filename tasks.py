
import shutil
from invoke import task
from os import getenv as env
from dotenv import load_dotenv
from os.path import join, dirname, exists

load_dotenv(join(dirname(__file__), '.env'))

STACK_NAME=env('STACK_NAME', 'gitwishes')
PACKAGE_BUCKET_NAME=env('PACKAGE_BUCKET_NAME')
AWS_PROFILE=env('AWS_PROFILE')

@task
def build_deps(ctx):
    build_path = join(dirname(__file__), 'dist')
    function_path = join(dirname(__file__), 'function.py')
    req_file = join(dirname(__file__), 'requirements.txt')
    cmd = "pip install -U -r {} -t {}".format(req_file, build_path)
    ctx.run(cmd)
    ctx.run("ln -s -r -t {} {}".format(build_path, function_path))

@task
def package(ctx):
    profile = ""
    if AWS_PROFILE is not None:
        profile = "--profile {}".format(AWS_PROFILE)
    cmd = ("aws {} cloudformation package --s3-bucket {} "
           "--template-file template.yml --s3-prefix packages "
           "--output-template-file serverless-output.yml"
          ).format(profile, PACKAGE_BUCKET_NAME)
    ctx.run(cmd)

@task
def deploy(ctx):
    profile = ""
    if AWS_PROFILE is not None:
        profile = "--profile {}".format(AWS_PROFILE)

    template_params = {
        'TwitterConsumerKey': env('TWITTER_CONSUMER_KEY'),
        'TwitterConsumerSecret': env('TWITTER_CONSUMER_SECRET'),
        'TwitterAccessToken': env('TWITTER_ACCESS_TOKEN'),
        'TwitterAccessTokenSecret': env('TWITTER_ACCESS_TOKEN_SECRET'),
    }
    param_overrides = " ".join(["{}={}".format(k,v) for k,v in template_params.items()])

    cmd = ("aws {} cloudformation deploy --template-file serverless-output.yml "
           "--capabilities CAPABILITY_NAMED_IAM --stack-name {} "
           "--parameter-overrides {}"
           ).format(profile, STACK_NAME, param_overrides)

    ctx.run(cmd)

@task
def delete(ctx):
    profile = ""
    if AWS_PROFILE is not None:
        profile = "--profile {}".format(AWS_PROFILE)
    cmd = "aws {} cloudformation delete-stack --stack-name {}".format(profile, STACK_NAME)
    ctx.run(cmd)

@task
def clean(ctx):
    profile = ""
    if AWS_PROFILE is not None:
        profile = "--profile {}".format(AWS_PROFILE)
    cmd = "aws {} s3 rm --recursive s3://{}/packages".format(profile, PACKAGE_BUCKET_NAME)
    ctx.run(cmd)
    build_path = join(dirname(__file__), 'dist')
    if exists(build_path):
        shutil.rmtree(build_path)
