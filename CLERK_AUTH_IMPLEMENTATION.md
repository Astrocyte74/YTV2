# Clerk Authentication for AI Endpoints

This document describes the Clerk JWT verification implementation for protecting AI endpoints.

## Quick Start

### Environment Variables
```bash
CLERK_SECRET_KEY=sk_test_xxxxx
CLERK_APPROVED_EMAILS=user1@example.com,user2@example.com
```

### Dependencies
```txt
pyjwt>=2.9.0
cryptography>=41.0.0
requests>=2.31.0
```

### Key Implementation Details

1. **JWKS URL**: `https://<issuer>/.well-known/jwks.json`
2. **Backend API**: `https://api.clerk.com/v1/users/{user_id}` (NOT accounts domain!)
3. **Algorithm**: RS256
4. **Token format**: `Bearer <token>`

## Critical Gotchas

### 1. Clerk JWT Structure
Clerk's default JWT does NOT include email. Token only contains:
- `sub` (user ID)
- `iss` (issuer)
- `exp` (expiration)
- Other metadata

**Solution**: Fetch email from Clerk Backend API using user_id.

### 2. PyJWT RS256 Requirement
PyJWT requires `cryptography` library for RS256 verification.

**Error without it**:
```
RS256 requires 'cryptography' to be installed.
```

**Solution**:
```bash
pip install cryptography>=41.0.0
```

### 3. API Domain Confusion
Clerk has two different domains:
- **Accounts domain**: `https://big-stud-70.clerk.accounts.dev` (from `iss` claim)
- **Backend API**: `https://api.clerk.com` (for fetching user data)

**Wrong**:
```python
clerk_api_url = f"{iss}/v1/users/{user_id}"  # 404 error
```

**Right**:
```python
clerk_api_url = f"https://api.clerk.com/v1/users/{user_id}"
```

### 4. JWK vs PEM
PyJWT's `decode()` with RS256 requires a PEM-formatted public key, not JWK.

**Solution**: Use `PyJWKClient` or convert JWK to PEM using cryptography library.

### 5. Bearer Token Format
Frontend must send token with `Bearer ` prefix:

```typescript
headers['Authorization'] = `Bearer ${authToken}`  // Correct
headers['Authorization'] = authToken               // Wrong
```

## Protected Endpoint Pattern

```python
def handle_jeop3_generate(self):
    """Protected AI endpoint"""
    try:
        # 1. Get Authorization header
        auth_header = self.headers.get('Authorization', '')

        # 2. Verify JWT and fetch email
        try:
            user_info = verify_clerk_bearer(auth_header)
            logger.info(f"✅ Auth verified: {user_info['email']}")
        except PermissionError as e:
            logger.warning(f"❌ Auth failed: {e}")
            self.send_response(403)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        # 3. Process request
        # ... existing code ...

    except Exception as e:
        logger.error(f"Error: {e}")
        self.send_response(500)
```

## Token Verification Flow

```
1. Extract token from "Bearer <token>" format
2. Get JWT header to find 'kid' (key ID)
3. Fetch JWKS from Clerk's .well-known endpoint
4. Find matching key by 'kid'
5. Convert JWK to PEM public key
6. Verify token signature with RS256
7. Extract 'sub' (user ID) from verified token
8. Call Clerk Backend API to get user email
9. Check if email is in approved list
10. Allow or deny request
```

## User Data Structure from Clerk API

```json
{
  "id": "user_xxxxx",
  "primary_email_address_id": "idn_xxxxx",
  "email_addresses": [
    {
      "id": "idn_xxxxx",
      "email_address": "user@example.com",
      "verified": true,
      "primary": true
    }
  ]
}
```

Extract primary email:
```python
primary_id = user_data.get('primary_email_address_id')
for addr in user_data['email_addresses']:
    if addr['id'] == primary_id:
        email = addr['email_address']
        break
```

## Performance Tips

1. **Cache user data** - Cache fetched email for 1 hour
2. **Cache JWKS** - Cache public keys from JWKS endpoint
3. **Reuse client** - Reuse HTTP sessions where possible

Example cache key:
```python
cache_key = f"clerk_user_{user_id}"
_TOKEN_CACHE[cache_key] = {
    'email': email,
    'exp': time.time() + 3600  # 1 hour
}
```

## Testing

### Test with valid token:
```bash
# Get token from browser console:
> await window.Clerk.session.getToken()

# Then test:
curl -X POST https://your-api.com/api/ai/generate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"promptType":"test","context":{}}'
```

### Test with invalid token:
```bash
curl -X POST https://your-api.com/api/ai/generate \
  -H "Authorization: Bearer invalid" \
  -H "Content-Type: application/json"
# Should return 403
```

### Test without token:
```bash
curl -X POST https://your-api.com/api/ai/generate \
  -H "Content-Type: application/json"
# Should return 403
```

## Monitoring

Add logging to track:
- Successful authentications
- Failed authentications (with reason)
- User IDs and emails
- Token verification failures

Example:
```python
logger.info(f"✅ Clerk auth verified for {user_info['email']}")
logger.warning(f"❌ Clerk auth failed: {error}")
logger.info(f"📝 JWT claims: {list(decoded.keys())}")
```

## Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing bearer token` | No Authorization header | Check frontend token sending |
| `Invalid token: missing kid` | Malformed JWT | Check Clerk configuration |
| `Token missing sub claim` | Invalid JWT structure | Verify Clerk token template |
| `Failed to verify user email` | Clerk API call failed | Check CLERK_SECRET_KEY |
| `Email not authorized` | Email not in allowlist | Add to CLERK_APPROVED_EMAILS |
| `RS256 requires cryptography` | Missing dependency | `pip install cryptography` |
| `404 from Clerk API` | Wrong API domain | Use `api.clerk.com` |
