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
1. Create an AWS account if you don't have one: https://aws.amazon.com/free
2. Install AWS CLI: `pip install awscli --break-system-packages` (or use the official installer)
3. Install AWS SAM CLI (makes deploying Lambda+API Gateway+DynamoDB one command):
   https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
4. Configure your CLI: `aws configure` (paste your Access Key + Secret Key + region `us-east-1`)
5. No AI/ML service setup needed — OCR runs client-side via Tesseract.js, loaded automatically from a CDN in `frontend/index.html`

## What's in this folder
- `template.yaml` — SAM template: defines your S3 bucket, DynamoDB tables, Lambdas, and API Gateway in one file
- `lambda/verify_medicine.py` — receives OCR-extracted text from the browser, parses drug name/expiry with pure Python, marks it `pending_review` if valid
- `lambda/custodian.py` — lets a custodian (NGO/hospital) list pending listings and approve them, flipping status to `available`
- `lambda/match_engine.py` — matches an approved listing to an open need request by drug + location, and confirms handoffs
- `lambda/safety_check.py` — rule-based logic that flags whether a match may need pharmacist review, based on age/condition
- `frontend/index.html` — upload + custodian dashboard + matching UI, with Tesseract.js loaded from CDN for client-side OCR

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
- **OCR reads garbled text**: use a clear, well-lit, front-facing photo — Tesseract.js struggles with angled, blurry, or stylized images
- **Lambda timeout**: increase Lambda timeout in `template.yaml` if OCR text parsing takes longer than expected on large inputs
- **CORS errors in browser**: make sure API Gateway has CORS enabled (already configured in `template.yaml`)
- **"Failed to fetch" errors**: run the frontend through a local server (e.g. VS Code's Live Server extension) rather than opening `index.html` directly as a `file://` URL — some browser security restrictions block Tesseract.js's worker scripts under `file://`
