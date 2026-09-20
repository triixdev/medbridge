# MedBridge — Custodian-Mediated Medicine Redistribution

AI-verified, NGO/hospital-mediated matching of unused medicines to patients in need.
Built for WeMakeDevs Bharat Builds Tour — Ship It track.

## Architecture
```
Donor uploads photo → browser runs Tesseract.js OCR (client-side, free, no AWS AI service)
                                     ↓
                    Extracted text sent to Lambda (verify_medicine) → pure Python parsing
                                     ↓
                            DynamoDB: MedicineListing
                                     ↓
                        Lambda (match_engine) → DynamoDB: NeedRequest
                                     ↓
                        Lambda (safety_check) → rule-based safety logic
                                     ↓
                            Custodian (NGO/Hospital) confirms handoff
```

Frontend: single HTML page (with Tesseract.js loaded from CDN) → API Gateway → Lambdas
Everything sits behind a **Custodian** entity (verified NGO/hospital) — no direct
donor-to-stranger handoff, mirroring the real, legal SMS Hospital Jaipur Drug Bank model.

**Note on AI/ML service choice:** this build intentionally avoids Bedrock, Textract, and
Rekognition, since new AWS accounts often hit an account-verification hold on these
managed AI services that can take hours to clear. Using Tesseract.js (client-side OCR)
and rule-based safety logic keeps the whole flow working reliably on any AWS account
from the moment it's created — a deliberate, documented engineering trade-off for a
time-boxed hackathon, not an oversight.

## Prerequisites (Day 1 — do this first)
1. Sign up at AWS Builder Center (free, no card): https://builder.aws.com
2. Create an AWS account if you don't have one: https://aws.amazon.com/free
3. Install AWS CLI: `pip install awscli --break-system-packages` (or use the official installer)
4. Install AWS SAM CLI (makes deploying Lambda+API Gateway+DynamoDB one command):
   https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
5. Configure your CLI: `aws configure` (paste your Access Key + Secret Key + region `us-east-1`)
6. **Enable Bedrock model access**: AWS Console → Bedrock → Model access → Request access to
   `Anthropic Claude 3.5 Sonnet` (has vision). Takes a few minutes to approve, do this FIRST.

## What's in this folder
- `template.yaml` — SAM template: defines your S3 bucket, DynamoDB tables, Lambdas, and API Gateway in one file
- `lambda/verify_medicine.py` — takes an uploaded photo, calls Bedrock to extract drug name/expiry, marks it `pending_review` if valid
- `lambda/custodian.py` — lets a custodian (NGO/hospital) list pending listings and approve them, flipping status to `available`
- `lambda/match_engine.py` — matches an approved listing to an open need request by drug + location, and confirms handoffs
- `lambda/safety_check.py` — calls Bedrock again to flag whether a match is safe for the requester's stated condition/age
- `frontend/index.html` — bare-bones upload + browse UI, no build tools needed

## Day 1: Deploy the skeleton
```bash
cd medbridge
sam build
sam deploy --guided
```
Answer the prompts (stack name: `medbridge`, region: `us-east-1`, allow SAM to create IAM roles: yes).
This creates your DynamoDB tables, S3 bucket, Lambda functions, and API Gateway.
**Copy the API Gateway URL from the output** — you'll paste it into `frontend/index.html`.

## Day 2: Wire and test
1. Open `frontend/index.html`, replace `API_URL_HERE` with your API Gateway URL
2. Test uploading a medicine photo — check CloudWatch Logs if it fails (Console → Lambda → your function → Monitor → View logs)
3. Manually insert a test NeedRequest row in DynamoDB console to test matching

## Day 3: Deploy frontend + polish
```bash
# Amplify Hosting - easiest way to get a public URL for your frontend
npm install -g @aws-amplify/cli
amplify init
amplify add hosting
amplify publish
```

## Day 4: Record demo, submit
Show: upload → auto-verify → match → safety flag → custodian confirm. Mention the
SMS Hospital Jaipur precedent explicitly — it shows judges you designed around the
real-world constraint instead of ignoring it.

## Common beginner issues
- **Bedrock "AccessDenied"**: you forgot to request model access in the console, or you're in the wrong region — Bedrock isn't available in every region, stick to `us-east-1`
- **Lambda timeout**: Bedrock calls can take a few seconds — set Lambda timeout to at least 30s in `template.yaml`
- **CORS errors in browser**: make sure API Gateway has CORS enabled (already configured in `template.yaml`)
