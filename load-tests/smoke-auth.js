// k6 smoke test — Auth flow (register → login → refresh → me)
// Usage: k6 run --env BASE_URL=http://localhost:5000 load-tests/smoke-auth.js

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";

export const options = {
  stages: [{ duration: "30s", target: 2 }],
  thresholds: {
    http_req_duration: ["p(95)<500", "p(99)<1000"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const seed = `${Date.now()}-${__VU}-${__ITER}`;
  const email = `k6+${seed}@example.com`;
  const password = "K6Test@123456";
  const headers = {
    "Content-Type": "application/json",
    "X-API-Contract": "v2",
  };

  // Register
  const regRes = http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ name: `k6user_${seed}`, email, password }),
    { headers, tags: { name: "POST /auth/register" } },
  );
  check(regRes, { "register 201": (r) => r.status === 201 });

  // Login
  const loginRes = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email, password }),
    { headers, tags: { name: "POST /auth/login" } },
  );
  check(loginRes, { "login 200": (r) => r.status === 200 });

  const body = loginRes.json();
  const accessToken = body.data ? body.data.access_token : "";
  const refreshToken = body.data ? body.data.refresh_token : "";

  if (!accessToken) {
    sleep(1);
    return;
  }

  const authHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-API-Contract": "v2",
  };

  // Me
  const meRes = http.get(`${BASE_URL}/user/me`, {
    headers: authHeaders,
    tags: { name: "GET /user/me" },
  });
  check(meRes, { "me 200": (r) => r.status === 200 });

  // Refresh
  if (refreshToken) {
    const refreshRes = http.post(
      `${BASE_URL}/auth/refresh`,
      JSON.stringify({ refresh_token: refreshToken }),
      { headers, tags: { name: "POST /auth/refresh" } },
    );
    check(refreshRes, { "refresh 200": (r) => r.status === 200 });
  }

  sleep(1);
}
