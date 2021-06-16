import boto3

def textract_output(filename):
    s3BucketName = "vetshot-ocr-ejfnoancoa"

    textract = boto3.client('textract')

    response = textract.detect_document_text(
        Document={
            'S3Object': {
                'Bucket': s3BucketName,
                'Name': filename
            }
        })
    output=[]
    for item in response["Blocks"]:
        if item["BlockType"] == "WORD":
            dtext = item["Text"]
            conf = item['Confidence']
            conf = "{:.2f}".format(conf)
            conf = float(conf)/100
            output.append((dtext,conf))
    return output