# SP Dhaba — Git Branching & Deploy Workflow

## Branch Strategy

```
main      → Production  (spdhaba-prd.up.railway.app)
staging   → Staging     (spdhaba-stg.up.railway.app)
feature/* → Local dev only, merged to staging first
```

## Day-to-day workflow

### Building a new feature

```bash
# 1. Always start from main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/menu-management

# 3. Build, commit as you go
git add .
git commit -m "feat: menu management backend models and routes"

# 4. Push to staging for testing
git checkout staging
git merge feature/menu-management
git push origin staging
# → Railway staging auto-deploys, test it

# 5. Once confirmed working → merge to main (production)
git checkout main
git merge staging
git push origin main
# → Railway production auto-deploys
```

### Hotfix directly to production

```bash
# 1. Branch from main
git checkout main
git checkout -b hotfix/void-dialog-fix

# 2. Fix, commit
git add .
git commit -m "fix: void dialog closes correctly"

# 3. Merge to both
git checkout main
git merge hotfix/void-dialog-fix
git push origin main

git checkout staging
git merge hotfix/void-dialog-fix
git push origin staging
```

## Railway Configuration

| Service              | Branch    | Root Dir   |
|----------------------|-----------|------------|
| spdhaba-production   | `main`    | `backend`  |
| spdhaba-prd          | `main`    | `frontend` |
| spdhaba-staging-api  | `staging` | `backend`  |
| spdhaba-stg          | `staging` | `frontend` |

## Environment Variables

| Variable               | Production                          | Staging                              |
|------------------------|-------------------------------------|--------------------------------------|
| `DB_NAME`              | `sp_dhaba_prod`                     | `sp_dhaba_staging`                   |
| `JWT_SECRET`           | (secret, unique)                    | (different secret, unique)           |
| `ENVIRONMENT`          | `production`                        | `staging`                            |
| `CORS_ORIGINS`         | `https://spdhaba-prd.up.railway.app`| `https://spdhaba-stg.up.railway.app` |
| `REACT_APP_BACKEND_URL`| `https://spdhaba-production...`     | `https://spdhaba-staging-api...`     |
| `REACT_APP_ENV`        | `production`                        | `staging`                            |

## Rules

1. **Never push directly to main** unless it's a hotfix
2. **Always test on staging first** — staging DB is isolated
3. **staging branch always stays ahead of or equal to main**
4. **Feature branches are deleted after merge**
