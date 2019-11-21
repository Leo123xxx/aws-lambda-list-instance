################################################################################################################################################
## Description: Sample lambda function to list ec2 instances with tags in all regions for Multiple AWS accounts stored in SSM Paremeter Store.
## Author: Leo Makhubele
## Email: leomakhubele@gmail.com
## GitHub Repository: https://github.com/Leo123xxx/aws-lambda-list-instance-sample.git
################################################################################################################################################

# Importing modules for python 3.7 executions.
import boto3
import os
import sys

# Setting Boto3(AWS API) variables
ssm_client = boto3.client('ssm')
stsclient = boto3.client('sts')
s3 = boto3.client('s3')

# Funtion to execute other function calls for Lambda.
def lambda_handler(event, context):
    instance_tags, rolearnlist = grab_variables()
    for rolearn in rolearnlist:
        find_store(rolearn, instance_tags)

# Function to get Lambda Environmental Variables(LEV) Instance tags and AWS Organisational Accounts IAM Roles For execution.
def grab_variables():
    ## Getting LEV for KEY "INSTANCE_TAGS". ## 
    TAGS = os.getenv('INSTANCE_TAGS', None)

    if TAGS:
      if ',' in TAGS:
        with_whitespace_instance_tags = TAGS.split(",")
        instance_tags = []
        for instance_tag in with_whitespace_instance_tags:
          instance_tags.append(instance_tag.strip())
      else:
        instance_tags = [TAGS]
    else:    ## Fail and exit if no tags are defined in LEV.
      print("No comma delimetered tags defined in Lambda Environment Variable 'INSTANCE_TAGS', exiting")
      sys.exit(1)  

    ## Get the list of ARNs of cross-account IAM roles saved in SSM Parameter "rolearnlist" ##
    ## NOTE: Make sure you have set the Role ARNs in SSM Parameter Store or this will faile the whole executions.
    rolearnlist_from_ssm = ssm_client.get_parameter(Name='rolearnlist')
    rolearnlist_from_ssm_list = rolearnlist_from_ssm['Parameter']['Value'].split(",")
    rolearnlist = rolearnlist_from_ssm_list 

    # Printing out results to Lambda CloudWatch Logs.
    print(f"Found INSTANCE_TAGS: {instance_tags}")
    print(f"Found ROLE_ARNS: {rolearnlist}")

    return instance_tags, rolearnlist

def find_store(rolearnlist, tags):
    # Initiating a session using ARN of the IAM role for the accounts.
    awsaccount = stsclient.assume_role(
        RoleArn=rolearnlist,
        RoleSessionName='awsaccount_session'
    )
    ACCESS_KEY = awsaccount['Credentials']['AccessKeyId']
    SECRET_KEY = awsaccount['Credentials']['SecretAccessKey']
    SESSION_TOKEN = awsaccount['Credentials']['SessionToken']

    # Create a list of all currently available aws regions.
    ec2 = boto3.client('ec2', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY, aws_session_token=SESSION_TOKEN)

    final_awsregionslist = []
    awsregions = ec2.describe_regions()
    awsregions_list = awsregions['Regions']
    for region in awsregions_list:
        final_awsregionslist.append(region['RegionName'])

    # Getting awsaccount ID from IAM Role ARN
    start = '::'
    end = ':'
    awsaccountid = rolearnlist[rolearnlist.find(start)+len(start):rolearnlist.rfind(end)] 

    # loop through all exisiting aws regions
    for awsregion in final_awsregionslist:
   
      # Open ec2 API session for current aws account(ARN) and region
      ec2client = boto3.client('ec2', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY, aws_session_token=SESSION_TOKEN, region_name=awsregion)

      # Code script to list all instances with tags from LAV in each AWS region
      found_list = []
      response = ec2client.describe_instances()
      for r in response['Reservations']:
          for i in r['Instances']:
              for t in i['Tags']:
                if t["Value"] in tags:
                  found_list.append(i)                    
      
      #Writing results to S3 as a text file
      SOURCE_FILENAME = f'/tmp/{awsaccountid}-instances.txt'   # File stored locally in Lambda environment
      DEST_FILENAME = f'{awsaccountid}-instances.txt'     # Destination file object in S3
      BUCKET_NAME = 'lambda-output-list-instances'   # Unique S3 bucket to upload file to. NOTE: Make sure you have substituted the Bucket name that is store in the MASTER/INVOKER account
      f = open(SOURCE_FILENAME, "a")
      
      for found_item in found_list:  
        f.write(f"Region: {awsregion}, Instance ID: {found_item['InstanceId']}, State:: {found_item['State']}, Tags:: {found_item['Tags']}\n")
      
      f.close()
      s3.upload_file(SOURCE_FILENAME, BUCKET_NAME, DEST_FILENAME) #S3 multipart upload



