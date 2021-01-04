import json
import boto3
import os
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    for record in event['Records']:
        # Read the Assumed Role credentials from the SQS body
        assume_role = json.loads(record['body'])
        logger.info(f"Account id: {assume_role['AssumedRoleUser']['Arn'].split(':')[4]}...")
        # Loop through supported regions for the Well Architected Service
        for region in GetRegions('wellarchitectedtool'):
            logger.info(f'Region id: {region}...')
            # Create boto3 client using the assued role credentials and region
            wat = boto3.client(
                'wellarchitected',
                aws_access_key_id = assume_role['Credentials']['AccessKeyId'],
                aws_secret_access_key = assume_role['Credentials']['SecretAccessKey'],
                aws_session_token = assume_role['Credentials']['SessionToken'],
                region_name = region
            )
            # Get all workloads in the region
            workloads = GetWorkloads(wat)
            # Loop workloads
            for workload_id in workloads:
                logger.info(f'Workload id: {workload_id}...')
                # Get any existing shares for the workload and the defined central account
                workload_shares = wat.list_workload_shares(
                    WorkloadId = workload_id,
                    SharedWithPrefix = os.environ['ACCOUNT_ID']
                )
                if len(workload_shares['WorkloadShareSummaries']) == 0:
                    # Create share if no shares currently exist
                    logger.info('Sharing workload...')
                    wat.create_workload_share(
                        WorkloadId = workload_id,
                        SharedWith = os.environ['ACCOUNT_ID'],
                        PermissionType = os.environ['PERMISSION_TYPE']
                    )
                else:
                    logger.info('Workload already shared.')

def GetWorkloads(client):
    # Wrap in try catch to handle unsupported regions or non-enabled regions
    try:
        list_workloads = client.list_workloads()
        workloads = [w['WorkloadId'] for w in list_workloads['WorkloadSummaries']]
        # Check next token to ensure all workloads are returned
        while 'NextToken' in list_workloads:
            list_workloads = client.list_workloads(
                NextToken = list_workloads['NextToken']
            )
            workloads.extend([w['WorkloadId'] for w in list_workloads['WorkloadSummaries']])
        return workloads
    except ClientError as e:
        print(e)
        return []

def GetRegions(ServiceName):
    ssm = boto3.client('ssm')
    get_parameters = ssm.get_parameters_by_path(
        Path = f'/aws/service/global-infrastructure/services/{ServiceName}/regions',
    )
    regions = [p['Value'] for p in get_parameters['Parameters']]
    # Check next token to ensure all parameters are returned
    while 'NextToken' in get_parameters:
        get_parameters = ssm.get_parameters_by_path(
            Path = f'/aws/service/global-infrastructure/services/{ServiceName}/regions',
            NextToken = get_parameters['NextToken']
        )
        regions.extend([p['Value'] for p in get_parameters['Parameters']])
    return regions

