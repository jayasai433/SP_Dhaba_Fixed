# Deployment — Railway + Custom Domain (GoDaddy)

## Recap of changes

- Backend unified on `main:app`. Procfile already uses it.
- Scope reduced to Expenses, Sales, Purchases, Item Master (multi-unit).
- Atlas databases `sp_dhaba` and `sp_dhaba_staging` wiped and empty at time of writing (01-Jul-2026).
- First backend boot will re-seed users, items, expense categories, and business profile.

## 1. Railway environment variables (backend service)

Set these on Railway (Project → Backend service → Variables). Existing values can be kept if already set correctly.

| Variable            | Required | Recommended value                                                              |
|---------------------|----------|--------------------------------------------------------------------------------|
| `MONGO_URL`         | Yes      | Your Atlas `mongodb+srv://...` string                                          |
| `DB_NAME`           | Yes      | `sp_dhaba` (production)                                                        |
| `JWT_SECRET`        | Yes      | Long random string (min 32 chars). Rotate to invalidate existing sessions.     |
| `CORS_ORIGINS`      | Yes      | `https://ops.your-domain.com,https://your-app.up.railway.app` (comma-separated). Set once your custom domain is decided. |
| `ENVIRONMENT`       | No       | `production`                                                                   |
| `ADMIN_PASSWORD` etc| No       | Only set to override the default seed passwords. Existing users are untouched. |

Notes:
- Do NOT set `CORS_ORIGINS` to `*` in production. It disables credentialed requests and reduces security.
- `PORT` is auto-injected by Railway; the Procfile uses it.

## 2. Railway environment variables (frontend service, if separate)

If the frontend is deployed as a separate Railway static site:

| Variable                 | Value                                       |
|--------------------------|---------------------------------------------|
| `REACT_APP_BACKEND_URL`  | `https://api.your-domain.com` OR the backend Railway public URL |

Rebuild the frontend after changing this variable.

## 3. Custom domain setup (GoDaddy DNS → Railway)

For each service that needs a domain (backend and/or frontend):

**On Railway:**
1. Open the service. Settings → Networking → Add Domain.
2. Enter the desired custom domain, for example:
   - `ops.your-domain.com` for frontend
   - `api.your-domain.com` for backend
3. Railway will display DNS records to add (usually a CNAME).

**On GoDaddy:**
1. Log in to GoDaddy. Domain Manager → DNS.
2. Add the CNAME record Railway showed you. For a subdomain like `ops`, add:
   - Type: `CNAME`
   - Name: `ops`
   - Value: `xxxxx.up.railway.app` (what Railway showed)
   - TTL: 600 (default fine)
3. Save. DNS propagation is usually 5–30 minutes.
4. Return to Railway. Once verified, Railway auto-provisions the SSL certificate.
5. Repeat for `api` subdomain if backend is separate.

## 4. First boot after deploy

Backend `startup` event will:
1. Run `services/seed.py::seed()`.
2. Create the three users (admin/staff/viewer) from `test_credentials.md` unless overridden by env vars.
3. Create the seed items (Egg, Chicken, Milk, ...).
4. Create the six expense categories.
5. Create the business profile stub.

Verify by hitting `https://api.your-domain.com/api/health` — should return `{"status":"ok","db":"connected","db_name":"sp_dhaba",...}`.

Log in at `https://ops.your-domain.com/login` with `admin@spdhaba.com / Admin@123`.

## 5. Post-deploy checklist

- [ ] Change the seed admin password from the UI (or set `ADMIN_PASSWORD` env var before first boot).
- [ ] Update `Business Profile` name, phone, and logo from the admin UI (endpoint: PATCH /api/business-profile).
- [ ] Verify `/api/health` returns `environment: production`.
- [ ] Test login from mobile browser on the custom domain.
- [ ] Add a real purchase and confirm it shows in the History list.

## 6. Rollback plan

If anything goes wrong:
1. Railway → Deployments → click the previous deploy → Redeploy.
2. To restore removed features, follow the checklist in `/app/docs/archived-features.md`.

## 7. Custom domain not resolving? Check:

- CNAME propagation: `nslookup ops.your-domain.com` should return the Railway target.
- Railway domain status shows green "Custom Domain: Verified".
- `CORS_ORIGINS` includes the exact custom domain with scheme (https://).
- Browser console for CORS errors on the login POST.
