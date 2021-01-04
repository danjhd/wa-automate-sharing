# Mutli-region, multi-account Well-Architected Review sharing

This article describes how to set up automated sharing of all [Well-Architected reviews](https://aws.amazon.com/architecture/well-architected) from all regions in all accounts in a single [AWS Organization](https://aws.amazon.com/organizations/) to a specified AWS account. This is useful if you have a central team within your organization that is involved in all AWS Well-Architected reviews and wish to simplify their access to these reviews.

This solution automates the [sharing capability](https://docs.aws.amazon.com/wellarchitected/latest/userguide/workloads-sharing.html) that the Well-Architected Tool provides. Before we go any further we should define some important terms that will be used so that we can avoid confusion:

- ## Management Account

  This is the root account of your AWS Organization also sometimes referred to as the *Payer Account*.

- ## Member Account

  These are all the other accounts in your AWS Organization. i.e. Any account that is not the Management Account. They are also sometimes referred to as *Linked Accounts*.

- ## Automation Account

  This a [Member Account](#member-account) that has nominated to carry out the automation tasks in this solution.

  *Whilst it is possible to use the [Management Account](#management-account) for this, it is considered best practice to use a dedicated account instead of the [Management Account](#management-account).*

- ## Reviews Account

  This is an account that will receive the Well-Architected Workload shares. It can be a [Member Account](#member-account) or it can be any other AWS Account, even one that is a [Member Account](#member-account) in another AWS Organization.

The below diagram shows the high-level logic for this solution. The [Automation Account](#automation-account) will contain a [Amazon CloudWatch](https://docs.aws.amazon.com/cloudwatch) Scheduled Event. This Scheduled Event will trigger once a day and at that time it will loop through all [Member Accounts](#member-account) in the AWS Organization. For each [Member Account](#member-account) it will then loop through all supported AWS Regions for the [AWS Well-Architected Tool](https://docs.aws.amazon.com/wellarchitected) in each region it will search for any Well-Architected Workloads that have not already been shared with the [Reviews Account](#reviews-account) and create a share for them.

In order to give scalability and resiliency to this solution we will be using 2 [AWS Lambda](https://aws.amazon.com/lambda/) functions. The first will be triggered by the Scheduled Event and perform the loop on the [Member Accounts](#member-account) and populate an [AWS SQS](https://aws.amazon.com/sqs/) queue with temporary access credentials for each [Member Account](#member-account). The second Lambda Function will be triggered by the SQS queue and will use the temporary credentials to loop all supported regions and create the Well-Architected Workload shares.

![High Level Diagram](./images/image1.png)

## Pre-requisites

1. All the AWS accounts need to exist in advance.
2. The [Automation Account](#automation-account) needs to have the ability to list all the [Member Accounts](#member-account) using the `ListAccounts` AWS API call, this operation can be called only from the organization’s [Management Account](#management-account) or by a [Member Account](#member-account) that is a [delegated administrator](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_integrate_services_list.html) for an AWS service. In this article we are using an account that has been delegated administrator for the `AWS Audit Manager` service, however you can use any service you wish or may already have delegated.
3. An IAM role in every [Member Account](#member-account) that can be assumed by the Automation Account

Since the first 2 pre-requisites can vary depending on use case we will leave these parts to complete on your own. The third one we will walk through next. If you already have a role like this in place you can skip this part, but please check you have the required permssions.

### Creating the required IAM role in all member accounts

We will be using [AWS CloudFormation](https://aws.amazon.com/cloudformation/) [StackSets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-concepts.html) to deploy this role to all existing [Member Accounts](#member-account). To use the ability of StackSets to deploy to all [Member Accounts](#member-account) we need to deploy the StackSet from the [Management Account](#management-account).

Start of by first creating a new text file called iam-role.yaml. Paste the following into the content of that file and save it:

```yaml
AWSTemplateFormatVersion: '2010-09-09'

Description: IAM Role to be assumed by automation account to share Well-Architected workloads automatically

Parameters:

  RoleName:
    Type: String
    Description: The RoleName to assume in all linked accounts.
    Default: WellArchitectedShares

  AutomationAccountId:
    Type: String
    Description: The AWS Account Id that will perform the automation

Resources:

  IamRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Ref RoleName
      AssumeRolePolicyDocument:
        Version: 2012-10-17
        Statement:
          - Effect: Allow
            Principal:
              AWS:
              - !Ref AutomationAccountId
            Action:
              - 'sts:AssumeRole'
      Policies:
        - PolicyName: Well-Architected
          PolicyDocument:
            Version: 2012-10-17
            Statement:
              - Effect: Allow
                Action:
                  - wellarchitected:ListWorkloads
                  - wellarchitected:ListWorkloadShares
                  - wellarchitected:CreateWorkloadShare
                Resource: '*'
```

Then open the CloudFormation StackSets Console in your [Management Account](#management-account) in your region of choice.

- Choose the option to `Create StackSet` select `Template is ready` and `Upload a template file` to upload the text file you just created
- Click `Next`
- Enter `WellArchitectedSharesRole` as the `StackSet Name`. In the `AutomationAccountId` parameter enter the 12 digit account id for your specified [Automation Account](#automation-account). You can leave the `RoleName` parameter as default unless you know that this IAM Role Name already exists in your accounts and therefore might cause a problem. *If you do change this RoleName parameter please make a note of what you used as this will be required later on*.
- Click `Next`
- No tags are required on this next page so you can leave it or add tags of your preference. Ensure that the `Permissions` options is highlighted as `Service-managed permissions`.
- Click `Next`
- In the `Deployment targets` section you can leave all the default values. It should have `Deploy to organization`, `Enabled` and `Delete stacks` selected. In the `Specify regions` section choose your preferred region from the drop-down. *Please ensure you only choose 1 region. Since this is a IAM resource we are creating it is a global resource anyway and the region chosen is not important.*
- If you wish to speed up deployment you can change the `Maximum concurrent accounts` property to `Percent /  100` instead of the default `Number / 1` but this is not a required step.
- Click `Next`
- On the final page, review your chosen settings and then click the `I acknowledge that AWS CloudFormation might create IAM resources with custom names.` check box at the bottom of the page.
- Click `Submit`

The StackSet will now take a couple of minutes to deploy the single CloudFormation stack across all your [Member Accounts](#member-account). You will know when it is complete by reviewing the `Status` column on the `Operations` tab of your StackSet. Once complete the required IAM role will exist in all the [Member Accounts](#member-account).

## Deploying the Solution

Then rest of this solution is most easily deployed using the [AWS Serverless Application Model](https://aws.amazon.com/serverless/sam/). To use this you will need to install the [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html).

Once you have this installed you next need to clone the repository for this solution at: 