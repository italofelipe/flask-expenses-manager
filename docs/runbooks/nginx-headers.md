# Nginx security headers — unified baseline

Canonical reference for the security headers emitted by every nginx variant
in this repo. Use this document as the source of truth when auditing drift
between the three `deploy/nginx/*.conf` files.

> Last applied: 2026-04-22 — SEC-AUD-10 (#626).

## Scope

Three nginx variants live in `deploy/nginx/`:

| File | Deployment |
|---|---|
| `default.conf` | ALB → nginx (plain HTTP, TLS terminated at ALB) |
| `default.tls.conf` | Legacy EC2 with Let's Encrypt cert on the box |
| `default.alb_dual.conf` | Dual-listen variant for the EC2-behind-ALB transition |

`default.http.conf` and `default.alb.conf` are HTTP-only redirects to
HTTPS and do not emit security headers — traffic is terminated by one of
the variants above before reaching the app.

All three variants that proxy traffic to `http://web:8000` MUST emit the
same security-header set. Divergence is the bug.

## Canonical header set

```nginx
# Server identity
server_tokens off;
proxy_hide_header Server;
proxy_hide_header X-Powered-By;

# HSTS — canonical source is nginx; strip Flask's HSTS to avoid duplicates.
proxy_hide_header Strict-Transport-Security;
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

# Core security baseline
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=(), usb=(), accelerometer=()" always;
add_header Content-Security-Policy "default-src 'none'; frame-ancestors 'none'" always;
```

### Per-header rationale

- **HSTS 2y + preload**: matches the CloudFront policy for the web app and
  prepares for a future hstspreload.org submission (SEC-AUD-02).
- **`proxy_hide_header Strict-Transport-Security`**: Flask's
  `app/middleware/security_headers.py` also emits HSTS. Without this
  directive ZAP reports `10035 Strict-Transport-Security Multiple Header
  Entries`.
- **X-Frame-Options: DENY**: the API never serves a page intended to be
  framed. `SAMEORIGIN` was historical and matched nothing real.
- **Permissions-Policy**: value is byte-identical to the CloudFront
  response-headers policy on `app.auraxis.com.br` (SEC-AUD-05) so the
  web and API report the same capabilities baseline.
- **CSP `default-src 'none'; frame-ancestors 'none'`**: the API returns
  JSON; no scripts, no styles, no frames. The strictest possible policy.
- **X-XSS-Protection**: intentionally NOT emitted. Deprecated and ignored
  by modern browsers; the header only risks misbehavior in legacy UAs.

## Drift audit

After a deploy, confirm the live response matches the baseline:

```bash
curl -sI https://api.auraxis.com.br/healthz | \
  grep -Ei '^(strict-transport-security|x-frame-options|x-content-type-options|referrer-policy|permissions-policy|content-security-policy|server|x-powered-by):'
```

Expected output:

```
strict-transport-security: max-age=63072000; includeSubDomains; preload
x-frame-options: DENY
x-content-type-options: nosniff
referrer-policy: strict-origin-when-cross-origin
permissions-policy: geolocation=(), microphone=(), camera=(), payment=(), usb=(), accelerometer=()
content-security-policy: default-src 'none'; frame-ancestors 'none'
```

`server` and `x-powered-by` MUST be absent.

## Changing the baseline

1. Update all three variants in the same commit — grep first to confirm:
   ```bash
   grep -l 'Strict-Transport-Security\|Permissions-Policy\|Content-Security-Policy' deploy/nginx/default*.conf
   ```
2. Update this document.
3. If the change affects the web app's posture, mirror it in:
   - `infra/web/main.tf` (`aws_cloudfront_response_headers_policy.web_security`)
   - `repos/auraxis-web/app/core/security/csp.ts`
   - `app/middleware/security_headers.py`

## References

- Audit that produced this change: `.context/reports/historical/security_audit_2026-04-22.md`
- Issue: [#626 SEC-AUD-10](https://github.com/italofelipe/auraxis-api/issues/626)
- CloudFront parity: SEC-AUD-05 / `infra/web/main.tf`
- Flask middleware: `app/middleware/security_headers.py`
