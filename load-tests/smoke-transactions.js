// k6 smoke test — Transactions (create → list → summary)
// Usage: k6 run --env BASE_URL=http://localhost:5000 load-tests/smoke-transactions.js

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";

export const options = {
  stages: [{ duration: "30s", target: 5 }],
  thresholds: {
    http_req_duration: ["p(95)<500", "p(99)<1000"],
    http_req_failed: ["rate<0.01"],
  },
};

function setupUser() {
  const seed = `${Date.now()}-${__VU}`;
  const email = `k6txn+${seed}@example.com`;
  const password = "K6Test@123456";
  const headers = {
    "Content-Type": "application/json",
    "X-API-Contract": "v2",
  };

  http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ name: `k6txn_${seed}`, email, password }),
    { headers },
  );

  const loginRes = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email, password }),
    { headers },
  );

  const body = loginRes.json();
  return body.data ? body.data.access_token : "";
}

export default function () {
  const token = setupUser();
  if (!token) return;

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    "X-API-Contract": "v2",
  };

  // Create transaction
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const createRes = http.post(
    `${BASE_URL}/transactions`,
    JSON.stringify({
      description: `k6 smoke txn`,
      value: 42.5,
      type: "expense",
      due_date: tomorrow,
    }),
    { headers, tags: { name: "POST /transactions" } },
  );
  check(createRes, { "create txn 201": (r) => r.status === 201 });

  // List transactions
  const listRes = http.get(`${BASE_URL}/transactions`, {
    headers,
    tags: { name: "GET /transactions" },
  });
  check(listRes, { "list txn 200": (r) => r.status === 200 });

  // Summary
  const month = new Date().toISOString().slice(0, 7);
  const summaryRes = http.get(
    `${BASE_URL}/transactions/summary?month=${month}`,
    { headers, tags: { name: "GET /transactions/summary" } },
  );
  check(summaryRes, { "summary 200": (r) => r.status === 200 });

  sleep(1);
}
