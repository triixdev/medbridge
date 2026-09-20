import json
import os
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
listings_table = dynamodb.Table(os.environ["LISTINGS_TABLE"])


def handler(event, context):
    """
    body.action:
      - "pending": list all listings with status pending_review for a custodian
      - "approve": flip a listing from pending_review -> available
    """
    try:
        body = json.loads(event["body"])
        action = body.get("action")

        if action == "pending":
            custodian_id = body["custodian_id"]
            scan = listings_table.scan(
                FilterExpression=Attr("custodianId").eq(custodian_id)
                & Attr("status").eq("pending_review")
            )
            return _response(200, {"pending": scan.get("Items", [])})

        elif action == "approve":
            listing_id = body["listingId"]
            listings_table.update_item(
                Key={"listingId": listing_id},
                UpdateExpression="SET #s = :val",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":val": "available"}
            )
            return _response(200, {"status": "approved", "listingId": listing_id})

        else:
            return _response(400, {"error": "unknown action"})

    except Exception as e:
        return _response(500, {"error": str(e)})


def _response(code, body):
    return {
        "statusCode": code,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body, default=str)
    }
