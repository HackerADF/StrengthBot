# **StrengthKits Discord Bot**

A fully-featured Discord bot built for **StrengthKits** — handling **ticketing**, **staff applications**, **bug/user reports**, **verification**, and automated category-based channel routing.

This bot uses:

* `discord.py` (2.3+)
* `aiosqlite`
* `aiohttp`
* Slash commands + UI buttons
* Modals for interactive forms
* Auto-sharded bot instance
* Environment variables for secure tokens

---

## 📌 **Features**

### ✔️ **Ticket System**

* Automatic ticket creation using buttons
* Smart routing based on reason:

  * Applications
  * Bug reports
  * User reports
  * Appeals
  * Support
  * Questions
  * Other
* Custom per-ticket channel with private permissions
* Automatic staff tagging
* SQLite ticket logging (`tickets.db`)
* Ticket closure system with archive category
* Support for form-based tickets (modals):

  * Player reports
  * Staff applications

---

### ✔️ **Verification System**

* Buttons to start verification
* Users receive a **6-digit code** via DM
* Input is validated using a custom Modal
* Auto-assigns the Verified role
* Sends logs to join-log and welcome channels
* Anti-raid check: prevents re-verification attempts

---

### ✔️ **Auto-Categorized Ticket Routing**

Ticket reasons map to categories using:

```py
map_reason(user, reason)
```

Your categories:

| Purpose      | Category ID           |
| ------------ | --------------------- |
| Applications | `1446783417457836117` |
| Bug Reports  | `1446711847339425902` |
| User Reports | `1446711847339425902` |
| Appeals      | `1446711847339425902` |
| Support      | `1446711847339425902` |
| Questions    | `1446711847339425902` |
| Other        | `1446711847339425902` |

Automatically generates names like:

```
application-adf
bug-report-username
user-report-rikki
question-adf
```

---

## 🔧 **Installation**

### 1. Clone the Repository

```bash
git clone https://github.com/your/repo.git
cd repo
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows
```

### 3. Install Requirements

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

Create a `.env` file:

```
DISCORD_TOKEN=your_bot_token_here
```

---

## ▶️ **Running the Bot**

```bash
python bot.py
```

The bot will:

* Load all cogs in `/cogs`
* Open database `tickets.db`
* Register all UI views
* Begin listening for interactions

---

## 📁 **Project Structure**

```
/
├── bot.py                # Main bot file
├── tickets.db            # SQLite ticket storage
├── cogs/
│   └── help.py           # Help command cog
├── .env                  # Stores Discord token
└── README.md             # Documentation (this file)
```

---

## 🛠️ **Core Components**

### **TicketView**

Creates the buttons:

* Become a member
* Ask a question
* Need support
* Report a bug
* Report a user
* Appeal punishment

Also handles creating the text channels.

---

### **Modals You Use**

* `TicketReportModal`
* `TicketMemberModal`
* `VerificationModal`

They collect structured data and pass it back into the ticket system.

---

### **Verification Views**

* `VerificationView` — initial Verify button
* `VerificationChallengeView` — DM button to enter code

---

### **Extension Auto-Loader**

Loads all Python cogs in `/cogs` automatically:

```py
await load_extensions("cogs")
```

---

## 💾 **Database Schema**

The bot auto-creates this table:

```sql
CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    reason TEXT NOT NULL
);
```

---

## 🧩 **Dependencies**

* `discord.py`
* `aiohttp`
* `aiosqlite`
* `python-dotenv`
* `requests`

---

## 📬 **Support**

For bug reports or issues, DM **ADF** or create a ticket in the StrengthKits Discord.
