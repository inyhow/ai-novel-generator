# Commercial Readiness Checklist

## Done in this repo
- [x] Multi-provider model support (OpenRouter + NewAPI)
- [x] Model health check endpoint
- [x] Request rate limit (in-memory)
- [x] Generation concurrency guard
- [x] API key gate (optional via SERVICE_API_KEY)
- [x] Health endpoints (`/healthz`, `/readyz`)
- [x] Security headers + request id
- [x] Env-driven configuration
- [x] Dockerfile + .dockerignore
- [x] Basic validation script (`scripts/check.ps1`)

## Required before real commercial launch
- [ ] Replace in-memory limiter with Redis-based distributed limiter
- [ ] Add user accounts + tenant isolation + quota
- [ ] Add billing and usage metering
- [ ] Add persistent storage for generations and audit logs
- [ ] Add centralized monitoring/alerting (Sentry + metrics + dashboards)
- [ ] Add moderation pipeline (input/output content safety)
- [ ] Add legal/compliance docs (privacy policy, terms, copyright policy)
- [ ] Add CI pipeline with tests + security scan + image scan
- [ ] Add staging environment and canary release process

## Suggested order
1. Redis rate limit + persistent store
2. Auth + quota + billing
3. Monitoring + alerting
4. Moderation/compliance
5. CI/CD and staged release
