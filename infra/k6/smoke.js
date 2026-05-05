// k6 smoke load test — `k6 run smoke.js`
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    normal: {
      executor: "constant-arrival-rate",
      rate: 100,
      timeUnit: "1s",
      duration: "1m",
      preAllocatedVUs: 50,
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<300"],
  },
};

const BASE = __ENV.API ?? "http://localhost:8000";

export default function () {
  const r1 = http.get(`${BASE}/health`);
  check(r1, { "health 200": (r) => r.status === 200 });

  const r2 = http.get(`${BASE}/api/v1/areas`);
  check(r2, { "areas 200": (r) => r.status === 200 });

  const r3 = http.get(`${BASE}/api/v1/assets/stats`);
  check(r3, { "stats 200": (r) => r.status === 200 });

  sleep(0.1);
}
