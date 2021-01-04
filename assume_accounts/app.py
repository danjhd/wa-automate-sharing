import json
import boto3
import os
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

sts = boto3.client('sts')
sqs = boto3.client('sqs')

def lambda_handler(event, context):
    accounts = GetAccounts()
    # Loop all accounts in the AWS Organization
    for account in accounts:
        logger.info(f'Account id: {account}...')
        # Wrap in try catch to handle scenario of role not being assumable
        try:
            assume_role = sts.assume_role(
                RoleArn = f"arn:aws:iam::{account}:role/{os.environ['ROLE_NAME']}",
                RoleSessionName = context.function_name,
                DurationSeconds = 900
            )
            # Put assume role details into each SQS queue supplied. This functionality is present to allown this Lambda function to be re-used for additional scenarios beyond sharing Well-Architected workloads.
            for queue in event['Queues']:
                logger.info(f'Queue Url: {queue}...')
                sqs.send_message(
                    QueueUrl = queue,
                    MessageBody = json.dumps(assume_role, default=str)
                )
        except ClientError as e:
            logger.error(f"{e.response['Error']['Code']}\t{account}")

def GetAccounts():
    org = boto3.client('organizations')
    list_accounts = org.list_accounts()
    accounts = [a['Id'] for a in list_accounts['Accounts'] if a['Status'] == 'ACTIVE']
    # Check next token to ensure all accounts are returned
    while 'NextToken' in list_accounts:
        list_accounts = org.list_accounts(NextToken = list_accounts['NextToken'])
        accounts.extend([a['Id'] for a in list_accounts['Accounts'] if a['Status'] == 'ACTIVE'])
    return accounts
