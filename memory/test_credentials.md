# RxFlow — Test Credentials

## Demo accounts

These accounts were seeded during testing. Both can sign in via `/login`.

| Username | Password   | Notes                                   |
|----------|------------|-----------------------------------------|
| `demo`   | `demopass1` | Initial test account                    |
| `maria`  | `demopass1` | Used for seeding sample intakes & audit |
| `ddi_admin_test` | `testpass1` | Created Feb 2026 to smoke-test `/api/admin/ddi-stats` (email `ddi@example.test`, phone `5555550100`) |
| `viewer_two` | `testpass1` | Created Feb 2026 to smoke-test the concurrency viewers indicator (email `v2@example.test`, phone `5555550101`) |

## Demo intakes (after seeding)

| Order | Patient        | Status        | Notes                                         |
|-------|----------------|---------------|------------------------------------------------|
| 1     | Maria Sanchez  | dispensed     | warfarin+aspirin (Major); shows audit history |
| 2     | James OBrien   | dispensed     | Attributed transitions (`by maria`)            |
| 3     | Aisha Patel    | waiting_info  | Sulfa allergy + clarithromycin                |
| 4     | Robert Kim     | new           | Assigned to `alex`                            |
| 5     | Diana Lee      | filled        | Ready for pickup, assigned `maria`            |
| 6     | Elena Vasquez  | new           | No interactions; minimal data                  |

## API endpoints (no auth required for read; cookie required for writes attribution)

- `GET  /intakes`                      list intakes
- `GET  /intakes/stats/summary`        stats tiles
- `GET  /intakes/{id}`                 single intake
- `GET  /intakes/{id}/history`         audit trail
- `POST /intakes`                      create intake
- `POST /intakes/{id}/status`          advance state (records `changed_by` from cookie)
- `POST /intakes/{id}/dispense`        mark dispensed
- `POST /intakes/{id}/assign`          assign
- `POST /intakes/{id}/check-interactions`  re-check
- `POST /api/auth/login`               returns `pharma_auth` cookie
- `POST /api/auth/signup`
- `POST /api/auth/logout`
- `GET  /api/auth/me`

## Shared JWT secret

Set via `/app/backend/.env` and the supervisor `frontend` start script:
`JWT_SECRET=rxflow-dev-only-shared-secret`
