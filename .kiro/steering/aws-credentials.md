---
inclusion: fileMatch
fileMatchPattern: ["agent/**", "**/.env*", "scripts/**"]
---
# AWS credential handling

- Load credentials with `python-dotenv` from `agent/.env`. Never hard-code them, print them or log them.
- When Bedrock returns `ExpiredTokenException`, `UnrecognizedClientException` or `ExpiredToken`, raise `CredentialsExpired`, which the API maps to HTTP 503 with the body `{"error": "AWS credentials expired. Refresh agent/.env from Workshop Studio."}`. The frontend shows this as a banner, not a crash.
- After the user updates `.env`, the API must pick up new credentials **without a restart**. Re-read env vars and recreate the boto3 session on each request, or on failure.
- Provide `scripts/check_aws.py`, which prints whether Bedrock Nova Pro and the Titan embeddings model are callable and how long the session token has left, if known.
- `.env`, `*.pem` and `credentials` files must be in `.gitignore`.
