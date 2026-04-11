/**
 * Load test — sustained traffic at expected production levels.
 *
 * Run: k6 run tests/load/load.js -e BASE_URL=http://localhost:5000 -e TOKEN=<jwt>
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

export const options = {
  stages: [
    { duration: "2m", target: 20 },  // ramp up
    { duration: "5m", target: 20 },  // steady state
    { duration: "1m", target: 0 },   // ramp down
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500", "p(99)<1500"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";
const TOKEN = __ENV.TOKEN || "";

const headers = {
  Authorization: `Bearer ${TOKEN}`,
  "Content-Type": "application/json",
};

export default function () {
  // Read-heavy workload mimicking a typical session
  const transactions = http.get(`${BASE_URL}/transactions?page=1&per_page=20`, { headers });
  check(transactions, {
    "GET /transactions 200": (r) => r.status === 200,
    "GET /transactions fast": (r) => r.timings.duration < 500,
  });

  const budgets = http.get(`${BASE_URL}/budgets`, { headers });
  check(budgets, { "GET /budgets 200": (r) => r.status === 200 });

  const summary = http.get(`${BASE_URL}/budgets/summary`, { headers });
  check(summary, { "GET /budgets/summary 200": (r) => r.status === 200 });

  // GraphQL batch query
  const gqlPayload = JSON.stringify({
    query: `{
      budgets { items { id name amount period spent remaining percentageUsed isOverBudget } }
      budgetSummary { totalBudgeted totalSpent totalRemaining percentageUsed budgetCount }
    }`,
  });
  const gql = http.post(`${BASE_URL}/graphql`, gqlPayload, { headers });
  check(gql, {
    "GraphQL budgets 200": (r) => r.status === 200,
    "GraphQL no errors": (r) => {
      try {
        const body = JSON.parse(r.body);
        return !body.errors;
      } catch {
        return false;
      }
    },
  });

  sleep(1);
}
