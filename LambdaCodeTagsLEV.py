################################################################################################################################################
## Description: Sample lambda function to list ec2 instances with tags in all regions for Multiple AWS accounts stored in SSM Paremeter Store.
## Author: Leo Makhubele
## Email: leomakhubele@gmail.com
## GitHub Repository: https://github.com/Leo123xxx/aws-lambda-list-instance-sample.git
################################################################################################################################################

import boto3
import os
import sys

stsclient = boto3.client('sts')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    instance_tags, rolearnlist = grab_variables()
    for rolearn in rolearnlist:
        find_store(rolearn, instance_tags)

def grab_variables():
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
    else:   
      print("No comma delimetered tags defined in Lambda Environment Variable 'INSTANCE_TAGS', exiting")
      sys.exit(1)
    
    if ARNS:
      if ',' in ARNS:
        role_arns = ARNS.split(",")
      else:
        role_arns = [ARNS]
    else: 
      print("No ARN's defined in Lambda Environment Variable 'ROLE_ARNS', exiting")
      sys.exit(1)
    
    print(f"Found INSTANCE_TAGS: {instance_tags}")
    print(f"Found ROLE_ARNS: {role_arns}")
    return instance_tags, role_arns
    
def find_store(rolearn, tags):
    awsaccount = stsclient.assume_role(
        RoleArn=rolearn,
        RoleSessionName='awsaccount_session'
    )
    ACCESS_KEY = awsaccount['Credentials']['AccessKeyId']
    SECRET_KEY = awsaccount['Credentials']['SecretAccessKey']
    SESSION_TOKEN = awsaccount['Credentials']['SessionToken']

    ec2 = boto3.client('ec2', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY, aws_session_token=SESSION_TOKEN)

    final_awsregionslist = []
    awsregions = ec2.describe_regions()
    awsregions_list = awsregions['Regions']
    for region in awsregions_list:
        final_awsregionslist.append(region['RegionName'])

    start = '::'
    end = ':'
    awsaccountid = rolearn[rolearn.find(start)+len(start):rolearn.rfind(end)] 

    for awsregion in final_awsregionslist:

      ec2client = boto3.client('ec2', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY, aws_session_token=SESSION_TOKEN, region_name=awsregion)

      found_list = []
      response = ec2client.describe_instances()
      for r in response['Reservations']:
          for i in r['Instances']:
              for t in i['Tags']:
                if t["Value"] in tags:
                  found_list.append(i)     

      SOURCE_FILENAME = f'/tmp/{awsaccountid}-instances.txt'  
      DEST_FILENAME = f'{awsaccountid}-instances.txt'    
      BUCKET_NAME = 'lambda-output-list-instances'   
      f = open(SOURCE_FILENAME, "a")
      
      for found_item in found_list:  
        f.write(f"Region: {awsregion}, Instance ID: {found_item['InstanceId']}, State:: {found_item['State']}, Tags:: {found_item['Tags']}\n")
      
      f.close()
      s3.upload_file(SOURCE_FILENAME, BUCKET_NAME, DEST_FILENAME)



