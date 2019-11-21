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
stsclient = boto3.client('sts')
s3 = boto3.client('s3')

# Funtion to execute other function calls for Lambda
def lambda_handler(event, context):
    instance_tags, rolearnlist = grab_variables()
    for rolearn in rolearnlist:
        find_store(rolearn, instance_tags)

# Function to get Lambda Environmental Variables(LEV) fo Instance tags and AWS Organisational Accounts IAM Roles.
def grab_variables():
    ## Getting LEV for KEY "INSTANCE_TAGS" and "ROLE_ARNS". ## 
    TAGS = os.getenv('INSTANCE_TAGS', None)
    ARNS = os.getenv('ROLE_ARNS', None)

    if TAGS:
      if ',' in TAGS:
        with_whitespace_instance_tags = TAGS.split(",")
        instance_tags = []
        for instance_tag in with_whitespace_instance_tags:
          instance_tags.append(instance_tag.strip())
      else:
        instance_tags = [TAGS]
    else:     ## Fail and exit if no INSTANCE_TAGS are defined in LEV.
      print("No comma delimetered tags defined in Lambda Environment Variable 'INSTANCE_TAGS', exiting")
      sys.exit(1)
    
    if ARNS:
      if ',' in ARNS:
        role_arns = ARNS.split(",")
      else:
        role_arns = [ARNS]
    else:     ## Fail and exit if no ROLE_ARNS are defined in LEV.
      print("No ARN's defined in Lambda Environment Variable 'ROLE_ARNS', exiting")
      sys.exit(1)
    
    # Printing out results to Lambda CloudWatch Logs.
    print(f"Found INSTANCE_TAGS: {instance_tags}")
    print(f"Found ROLE_ARNS: {role_arns}")
    return instance_tags, role_arns
    
def find_store(rolearn, tags):
    # Initiating a session using ARN of the IAM role for the accounts
    awsaccount = stsclient.assume_role(
        RoleArn=rolearn,
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
    awsaccountid = rolearn[rolearn.find(start)+len(start):rolearn.rfind(end)] 

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



