/**
 * Stress test — push beyond normal load to find breaking points.
 *
 * Run: k6 run tests/load/stress.js -e BASE_URL=http://localhost:5000 -e TOKEN=<jwt>
 */

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "2m", target: 50 },
    { duration: "5m", target: 50 },
    { duration: "2m", target: 100 },
    { duration: "5m", target: 100 },
    { duration: "2m", target: 200 },
    { duration: "5m", target: 200 },
    { duration: "5m", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<2000"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";
const TOKEN = __ENV.TOKEN || "";

const headers = {
  Authorization: `Bearer ${TOKEN}`,
  "Content-Type": "application/json",
};

export default function () {
  const res = http.get(`${BASE_URL}/transactions`, { headers });
  check(res, {
    "status < 500": (r) => r.status < 500,
  });

  const budgets = http.get(`${BASE_URL}/budgets`, { headers });
  check(budgets, { "budgets < 500": (r) => r.status < 500 });

  const gql = http.post(
    `${BASE_URL}/graphql`,
    JSON.stringify({ query: "{ me { id email } }" }),
    { headers }
  );
  check(gql, { "gql < 500": (r) => r.status < 500 });

  sleep(0.5);
}
