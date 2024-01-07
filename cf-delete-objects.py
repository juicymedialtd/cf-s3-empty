import subprocess
import re
import boto3

# Function to run a shell command and return its output
def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()
    if error:
        raise Exception(f"Error running command '{command}': {error.decode()}")
    return output.decode()

# Run 'cf apps' and extract the first application's name
cf_apps_output = run_command("cf apps")
app_lines = cf_apps_output.splitlines()

# Find the line with the first app's name, assuming it's after the 'routes' line
#first_app_line_index = next(i for i, line in enumerate(app_lines) if 'routes' in line) + 1
#first_app_name = app_lines[first_app_line_index].split()[0]

# Find the first line with either "wordpress" or "wp"
matching_apps = [line for line in app_lines if "wordpress" in line.lower() or "wp" in line.lower()]
if not matching_apps:
    raise Exception("No applications with 'wordpress' or 'wp' found.")

first_app_name = matching_apps[0].split()[0]

# Run 'cf env <app_name>' to get the environment variables
cf_env_output = run_command(f"cf env {first_app_name}")
#print("App name: ", first_app_name)

# Define a function to search for environment variables
def search_env_var(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE |  re.MULTILINE)
    return match.group(1) if match else None

# Attempt to extract S3 credentials from the environment variables
s3_access_key = search_env_var(r'"aws_access_key_id":\s*"([^"]+)"', cf_env_output)
s3_secret_key = search_env_var(r'"aws_secret_access_key":\s*"([^"]+)"', cf_env_output)
s3_bucket_name = search_env_var(r'"bucket_name":\s*"([^"]+)"', cf_env_output)
s3_region = search_env_var(r'"aws_region":\s*"([^"]+)"', cf_env_output)

s3_bucket_name = "intranet-media-staged"

#print("1: ",s3_access_key)
#print("2: ",s3_secret_key)
#print("3: ",s3_bucket_name)
#print("4: ",s3_region)


# Check if any of the required credentials are missing
if not s3_access_key or not s3_secret_key or not s3_bucket_name or not s3_region:
    raise Exception("Required S3 credentials not found in the environment variables.")

# Initialize a session using the extracted credentials
session = boto3.Session(
    aws_access_key_id=s3_access_key,
    aws_secret_access_key=s3_secret_key,
    region_name=s3_region
)

# Create an S3 client
s3_client = session.client('s3')

# Function to list all objects in the bucket
def list_objects(bucket_name):
    # Initialize an empty list to hold all the objects
    all_objects = []

    # Start with no continuation token
    continuation_token = None

    # Loop until there are no more objects
    while True:
        # If this isn't the first page, set the continuation token
        list_kwargs = dict(Bucket=bucket_name)
        if continuation_token:
            list_kwargs['ContinuationToken'] = continuation_token

        # Fetch the next page of objects
        response = s3_client.list_objects_v2(**list_kwargs)

        # Add the contents of this page to our list
        all_objects.extend(response.get('Contents', []))

        # If there's no continuation token, we're done; otherwise, keep going
        if 'NextContinuationToken' in response:
            continuation_token = response['NextContinuationToken']
        else:
            break

    return all_objects

# Function to delete an object from the bucket
def delete_object(bucket_name, object_key):
    s3_client.delete_object(Bucket=bucket_name, Key=object_key)

# Function to delete all objects in the bucket, including all versions if versioning is enabled
def delete_all_objects(bucket_name):
    # Check if versioning is enabled
    versioning = s3_client.get_bucket_versioning(Bucket=bucket_name)
    if versioning.get('Status') == 'Enabled':
        # Delete all versions and delete markers
        object_versions = s3_client.list_object_versions(Bucket=bucket_name)
        for version in object_versions.get('Versions', []) + object_versions.get('DeleteMarkers', []):
            s3_client.delete_object(Bucket=bucket_name, Key=version['Key'], VersionId=version['VersionId'])
    else:
        # Delete all objects
        objects = s3_client.list_objects_v2(Bucket=bucket_name)
        for obj in objects.get('Contents', []):
            s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])


# Delete all objects and versions in the bucket
delete_all_objects(s3_bucket_name)

# Delete all objects in the bucket
#objects = list_objects(s3_bucket_name)
#for obj in objects:
#    delete_object(s3_bucket_name, obj['Key'])
#    print(f"Deleted {obj['Key']} from {s3_bucket_name}")

print("All objects deleted from the bucket.")

# Delete the bucket
#s3_client.delete_bucket(Bucket=s3_bucket_name)
#print(f"Bucket '{s3_bucket_name}' deleted.")

