# dynamo_setup.py
import boto3
import time

DYNAMO_ENDPOINT = "http://localhost:8000"  # DynamoDB local

def create_tables():
    dynamodb = boto3.resource('dynamodb', endpoint_url=DYNAMO_ENDPOINT, region_name='us-west-2')
    existing = [t.name for t in dynamodb.tables.all()]
    if 'HelpRequests' not in existing:
        print("Creating HelpRequests table...")
        table = dynamodb.create_table(
            TableName='HelpRequests',
            KeySchema=[{'AttributeName': 'request_id','KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'request_id','AttributeType': 'S'},
                                  {'AttributeName': 'status','AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits':5,'WriteCapacityUnits':5},
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'status-index',
                    'KeySchema':[{'AttributeName':'status','KeyType':'HASH'}],
                    'Projection':{'ProjectionType':'ALL'},
                    'ProvisionedThroughput':{'ReadCapacityUnits':5,'WriteCapacityUnits':5}
                }
            ]
        )
        table.wait_until_exists()
        print("HelpRequests table created.")
    else:
        print("HelpRequests table already exists.")

    if 'KnowledgeBase' not in existing:
        print("Creating KnowledgeBase table...")
        table = dynamodb.create_table(
            TableName='KnowledgeBase',
            KeySchema=[{'AttributeName':'kb_key','KeyType':'HASH'}],
            AttributeDefinitions=[{'AttributeName':'kb_key','AttributeType':'S'}],
            ProvisionedThroughput={'ReadCapacityUnits':5,'WriteCapacityUnits':5}
        )
        table.wait_until_exists()
        print("KnowledgeBase table created.")
    else:
        print("KnowledgeBase table already exists.")

if __name__ == "__main__":
    create_tables()
