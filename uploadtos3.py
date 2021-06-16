from botocore.exceptions import ClientError
import logging
import boto3


def upload_to_s3(filename, object_name=None):
    bucket = "vetshot-ocr-ejfnoancoa"
    if object_name is None:
        object_name = filename
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(filename, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True