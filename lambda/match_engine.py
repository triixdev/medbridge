import json
import os
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
listings_table = dynamodb.Table(os.environ["LISTINGS_TABLE"])
requests_table = dynamodb.Table(os.environ["REQUESTS_TABLE"])


def handler(event, context):
    """
    Two modes, based on body.action:
      - "create_request": add a new NeedRequest (drug_name, location, age, condition, custodian_id)
      - "find_matches": given a listingId, find open requests for the same drug at the same custodian
    """
    try:
        body = json.loads(event["body"])
        action = body.get("action")

        if action == "create_request":
            item = {
                "requestId": body["requestId"],
                "drugName": body["drug_name"],
                "location": body.get("location", "unknown"),
                "age": body.get("age"),
                "condition": body.get("condition", ""),
                "custodianId": body["custodian_id"],
                "status": "open"
            }
            requests_table.put_item(Item=item)
            return _response(200, {"status": "created", "requestId": item["requestId"]})

        elif action == "find_matches":
            listing = listings_table.get_item(Key={"listingId": body["listingId"]}).get("Item")
            if not listing:
                return _response(404, {"error": "listing not found"})
            if listing.get("status") != "available":
                return _response(400, {"error": "listing is not approved/available yet"})

            # match: same drug name, same custodian, same location (city string), still open
            scan = requests_table.scan(
                FilterExpression=Attr("drugName").eq(listing["drugName"])
                & Attr("custodianId").eq(listing["custodianId"])
                & Attr("location").eq(listing["location"])
                & Attr("status").eq("open")
            )
            matches = scan.get("Items", [])
            return _response(200, {"listing": listing, "matches": matches})

        elif action == "confirm":
            listing_id = body["listingId"]
            request_id = body["requestId"]

            listings_table.update_item(
                Key={"listingId": listing_id},
                UpdateExpression="SET #s = :val",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":val": "completed"}
            )
            requests_table.update_item(
                Key={"requestId": request_id},
                UpdateExpression="SET #s = :val",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":val": "fulfilled"}
            )
            return _response(200, {"status": "handoff_confirmed"})

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
