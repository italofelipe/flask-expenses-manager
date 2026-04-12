// k6 smoke test — Dashboard aggregates (overview + trends)
// Usage: k6 run --env BASE_URL=http://localhost:5000 load-tests/smoke-dashboard.js

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
  const email = `k6dash+${seed}@example.com`;
  const password = "K6Test@123456";
  const headers = {
    "Content-Type": "application/json",
    "X-API-Contract": "v2",
  };

  http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ name: `k6dash_${seed}`, email, password }),
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
    Authorization: `Bearer ${token}`,
    "X-API-Contract": "v2",
  };

  const month = new Date().toISOString().slice(0, 7);

  // Dashboard overview
  const overviewRes = http.get(
    `${BASE_URL}/dashboard/overview?month=${month}`,
    { headers, tags: { name: "GET /dashboard/overview" } },
  );
  check(overviewRes, { "overview 200": (r) => r.status === 200 });

  // Dashboard trends
  const trendsRes = http.get(`${BASE_URL}/dashboard/trends`, {
    headers,
    tags: { name: "GET /dashboard/trends" },
  });
  check(trendsRes, { "trends 200": (r) => r.status === 200 });

  // Bootstrap
  const bootstrapRes = http.get(`${BASE_URL}/user/bootstrap`, {
    headers,
    tags: { name: "GET /user/bootstrap" },
  });
  check(bootstrapRes, { "bootstrap 200": (r) => r.status === 200 });

  sleep(1);
}
