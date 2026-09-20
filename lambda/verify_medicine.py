import json
import os
import re
import uuid
from datetime import datetime
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["LISTINGS_TABLE"])

# OCR now happens client-side in the browser (Tesseract.js), so this Lambda
# only receives already-extracted text and does pure Python parsing — no
# AWS AI/ML service call at all. This sidesteps the new-account verification
# gate that blocks Bedrock, Textract, and Rekognition on brand-new accounts.

EXPIRY_PATTERNS = [
    r"(EXP|Exp|exp)[.:]?\s*(\d{1,2})[/\-](\d{2,4})",   # EXP: 05/2027
    r"(EXP|Exp|exp)[.:]?\s*(\d{2,4})[/\-](\d{1,2})",   # EXP: 2027/05
    r"(\d{1,2})[/\-](\d{4})",                           # 05/2027 standalone
]


def handler(event, context):
    try:
        body = json.loads(event["body"])
        extracted_text = body.get("extracted_text", "")
        donor_location = body.get("location", "unknown")
        custodian_id = body.get("custodian_id")

        if not custodian_id:
            return _response(400, {"error": "custodian_id is required — no direct donor-to-stranger listings allowed"})

        lines = [l.strip() for l in extracted_text.splitlines() if l.strip()]

        if not lines:
            return _response(200, {
                "status": "rejected",
                "reason": "Could not read any text on the label — please retake the photo with better lighting",
                "details": {"raw_lines": lines}
            })

        expiry_date, is_expired = _extract_expiry(extracted_text)
        drug_name = _guess_drug_name(lines)

        if is_expired:
            return _response(200, {
                "status": "rejected",
                "reason": f"Medicine appears expired ({expiry_date})",
                "details": {"raw_lines": lines}
            })

        listing_id = str(uuid.uuid4())
        table.put_item(Item={
            "listingId": listing_id,
            "drugName": drug_name,
            "expiryDate": expiry_date or "unknown",
            "location": donor_location,
            "custodianId": custodian_id,
            "status": "pending_review"  # a custodian must approve before it can be matched
        })

        return _response(200, {
            "status": "verified",
            "listingId": listing_id,
            "details": {"drug_name": drug_name, "expiry_date": expiry_date, "raw_lines": lines}
        })

    except Exception as e:
        return _response(500, {"error": str(e)})


def _extract_expiry(text):
    """Look for an EXP date pattern in the OCR'd text, return (date_str, is_expired)."""
    for pattern in EXPIRY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            nums = [g for g in groups if g and g.isdigit()]
            if len(nums) >= 2:
                month, year = nums[-2], nums[-1]
                if len(month) == 4:  # order was year/month, swap
                    month, year = year, month
                year = year if len(year) == 4 else f"20{year}"
                try:
                    month_i = int(month)
                    year_i = int(year)
                    if 1 <= month_i <= 12:
                        expiry_str = f"{year_i}-{month_i:02d}"
                        now = datetime.utcnow()
                        is_expired = (year_i, month_i) < (now.year, now.month)
                        return expiry_str, is_expired
                except ValueError:
                    continue
    return None, False  # couldn't find a date — don't auto-reject, let a custodian eyeball it


DRUG_NAME_PATTERN = re.compile(r'[A-Za-z]{3,}-\d{2,4}')  # e.g. PARACIP-500, Paracemeter-500
DRUG_SIGNAL_WORDS = re.compile(r'(tablet|capsule|mg|paracetamol|ibuprofen|syrup)', re.IGNORECASE)


def _guess_drug_name(lines):
    """Three-pass heuristic, most confident first:
    1. A 'Brand-Dose' pattern like PARACIP-500 — very common on Indian medicine strips
    2. A line mentioning a drug-related word (tablet, mg, paracetamol, etc)
    3. The line with the highest ratio of real letters (avoids OCR noise/symbols)
    A custodian reviews every listing before approval, so this only needs to be
    a good guess, not perfect — humans catch what OCR gets wrong."""
    for line in lines:
        match = DRUG_NAME_PATTERN.search(line)
        if match:
            return match.group()

    for line in lines:
        if DRUG_SIGNAL_WORDS.search(line):
            cleaned = re.sub(r'[^A-Za-z0-9 .%-]', '', line).strip()
            if 3 <= len(cleaned) <= 40:
                return cleaned

    def alpha_ratio(l):
        return sum(c.isalpha() for c in l) / len(l) if l else 0

    candidates = [l.strip() for l in lines if 3 <= len(l.strip()) <= 40]
    if candidates:
        best = max(candidates, key=alpha_ratio)
        if alpha_ratio(best) > 0.6:
            return best

    return lines[0] if lines else "Unknown"


def _response(code, body):
    return {
        "statusCode": code,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body)
    }