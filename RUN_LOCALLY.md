# SP Royal Punjabi Dhaba — Run Locally

## What you need installed
- Python 3.10+
- Node.js 18+
- MongoDB (local)

---

## Step 1 — Install MongoDB (if not already)

### Mac:
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

### Windows:
Download from https://www.mongodb.com/try/download/community
Install and start the MongoDB service.

### Verify it's running:
```bash
mongosh --eval "db.adminCommand('ping')"
# Should print: { ok: 1 }
```

---

## Step 2 — Backend setup

```bash
cd SP_Dhaba_Fixed/backend
```

Create `.env` file (copy this exactly):
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=sp_dhaba
JWT_SECRET=sp_dhaba_super_secret_key_minimum_32_chars_long
ADMIN_EMAIL=admin@spdhaba.com
ADMIN_PASSWORD=Admin@123
STAFF_EMAIL=lokesh@spdhaba.com
STAFF_PASSWORD=Staff@123
VIEWER_EMAIL=display@spdhaba.com
VIEWER_PASSWORD=View@123
ENABLE_SCHEDULER=false
```

Install dependencies:
```bash
pip install fastapi uvicorn motor pymongo bcrypt PyJWT python-dotenv \
            pydantic[email] apscheduler pytz httpx reportlab python-multipart
```

Start the backend:
```bash
uvicorn main:app --reload --port 8001
```

You should see:
```
INFO: Uvicorn running on http://127.0.0.1:8001
INFO: Application startup complete.
```

Open http://127.0.0.1:8001/docs to see all API routes.

---

## Step 3 — Frontend setup

```bash
cd SP_Dhaba_Fixed/frontend
```

Create `.env` file:
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

Install and start:
```bash
npm install --legacy-peer-deps
npm start
```

Browser opens at http://localhost:3000

---

## Step 4 — Login credentials

| Role   | Email                  | Password   |
|--------|------------------------|------------|
| Admin  | admin@spdhaba.com      | Admin@123  |
| Staff  | lokesh@spdhaba.com     | Staff@123  |
| Viewer | display@spdhaba.com    | View@123   |

---

## What gets seeded on first run

- 33 grocery items (Chicken, Rice, Onion, Tomato...)
- 9 categories (Meat, Dairy, Vegetables...)
- 9 units (kg, L, dozen...)
- 6 expense categories (Maintenance, Utilities, Rent...)
- 3 users (admin, staff, viewer)
- Business profile: "SP Royal Punjabi Family Dhaba"

---

## Test checklist

- [ ] Login as admin → see Dashboard
- [ ] Add a purchase (Items → Purchases)
- [ ] Log daily usage (Daily Usage)
- [ ] Record today's sales (Sales)
- [ ] Check Live Stock — numbers should update
- [ ] Add an expense (Expenses)
- [ ] View P&L (P&L tab)
- [ ] Check Alerts — any low stock items?
- [ ] Login as staff → confirm no Dashboard, no Salaries
- [ ] Login as viewer → confirm read-only access
- [ ] Try adding same purchase twice quickly → duplicate warning popup
- [ ] Void an entry → confirm it disappears from list
- [ ] Display Mode → should show business name from profile

---

## Troubleshooting

**Backend won't start:**
```bash
# Check MongoDB is running
mongosh --eval "db.adminCommand('ping')"

# Check port 8001 is free
lsof -i :8001
```

**Frontend shows "Network Error":**
- Make sure backend is running on port 8001
- Check `frontend/.env` has `REACT_APP_BACKEND_URL=http://localhost:8001`

**Login fails:**
- Wait 5 seconds — seed runs on first startup
- Check MongoDB has data: `mongosh sp_dhaba --eval "db.users.find()"`
