/**
 * Smoke test — verify the API is reachable and auth + core endpoints work.
 *
 * Run: k6 run tests/load/smoke.js -e BASE_URL=http://localhost:5000 -e TOKEN=<jwt>
 */

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 1,
  duration: "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";
const TOKEN = __ENV.TOKEN || "";

const headers = {
  Authorization: `Bearer ${TOKEN}`,
  "Content-Type": "application/json",
};

export default function () {
  // Health check
  const health = http.get(`${BASE_URL}/health`);
  check(health, { "health 200": (r) => r.status === 200 });

  // List transactions
  const txns = http.get(`${BASE_URL}/transactions`, { headers });
  check(txns, { "transactions 200": (r) => r.status === 200 });

  // Budgets list
  const budgets = http.get(`${BASE_URL}/budgets`, { headers });
  check(budgets, { "budgets 200 or 401": (r) => r.status === 200 || r.status === 401 });

  // Subscription plans (public, no auth)
  const plans = http.get(`${BASE_URL}/subscriptions/plans`);
  check(plans, { "plans 200": (r) => r.status === 200 });

  // GraphQL introspection (should return 200 with schema)
  const gql = http.post(
    `${BASE_URL}/graphql`,
    JSON.stringify({ query: "{ __typename }" }),
    { headers }
  );
  check(gql, { "graphql 200": (r) => r.status === 200 });

  sleep(1);
}
