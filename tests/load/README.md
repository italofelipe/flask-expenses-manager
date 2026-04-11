# Load Tests

k6 load test scripts for auraxis-api.

## Prerequisites

Install k6: https://k6.io/docs/get-started/installation/

## Environment variables

| Variable   | Description                          | Default                 |
|------------|--------------------------------------|-------------------------|
| `BASE_URL` | API base URL                         | `http://localhost:5000` |
| `TOKEN`    | JWT bearer token for authenticated endpoints | `` (empty) |

## Scripts

### smoke.js — Smoke test

Verifies the API is up and core endpoints are reachable. 1 VU, 30 seconds.

```bash
k6 run tests/load/smoke.js \
  -e BASE_URL=http://localhost:5000 \
  -e TOKEN=<your_jwt>
```

### load.js — Load test

Sustained traffic at expected production levels. Ramps to 20 VUs over 2 min,
holds for 5 min, then ramps down.

```bash
k6 run tests/load/load.js \
  -e BASE_URL=http://localhost:5000 \
  -e TOKEN=<your_jwt>
```

Thresholds: `p(95) < 500ms`, `p(99) < 1500ms`, error rate `< 1%`.

### stress.js — Stress test

Pushes beyond normal load to find breaking points. Ramps to 200 VUs in stages.

```bash
k6 run tests/load/stress.js \
  -e BASE_URL=http://localhost:5000 \
  -e TOKEN=<your_jwt>
```

Thresholds: `p(95) < 2000ms`, error rate `< 5%`.

## Getting a JWT token for local testing

```bash
curl -X POST http://localhost:5000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "user@example.com", "password": "yourpassword"}' \
  | jq -r '.access_token'
```
