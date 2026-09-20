import json

# Simple, transparent rule-based safety net — avoids depending on Bedrock,
# which is currently blocked by an account-verification hold. This is
# intentionally conservative: anything it's unsure about gets flagged for
# a human pharmacist rather than silently approved.

AGE_SENSITIVE_KEYWORDS = ["aspirin", "ibuprofen", "codeine", "tramadol"]
PREGNANCY_SENSITIVE_KEYWORDS = ["warfarin", "isotretinoin", "methotrexate", "misoprostol"]


def handler(event, context):
    try:
        body = json.loads(event["body"])
        drug_name = (body.get("drug_name") or "").lower()
        age = body.get("age")
        condition = (body.get("condition") or "").lower()

        flag_level = "safe"
        reasons = []

        try:
            age_i = int(age)
        except (TypeError, ValueError):
            age_i = None

        if age_i is not None and age_i < 12:
            if any(k in drug_name for k in AGE_SENSITIVE_KEYWORDS):
                flag_level = "not_recommended"
                reasons.append("this medicine is generally not recommended for children under 12")
            else:
                flag_level = "check_with_pharmacist"
                reasons.append("dosage for children should always be confirmed by a pharmacist")

        if age_i is not None and age_i >= 65 and flag_level == "safe":
            flag_level = "check_with_pharmacist"
            reasons.append("older adults should confirm dosage with a pharmacist")

        if "pregnan" in condition and any(k in drug_name for k in PREGNANCY_SENSITIVE_KEYWORDS):
            flag_level = "not_recommended"
            reasons.append("this medicine may not be safe during pregnancy")

        if not drug_name or drug_name == "unknown":
            flag_level = "check_with_pharmacist"
            reasons.append("drug name could not be confidently identified — please verify before use")

        if not reasons:
            reasons.append("no automatic red flags found — a pharmacist should still do a final check")

        return _response(200, {
            "flag_level": flag_level,
            "message": "; ".join(reasons).capitalize()
        })

    except Exception as e:
        return _response(500, {"error": str(e)})


def _response(code, body):
    return {
        "statusCode": code,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body)
    }
