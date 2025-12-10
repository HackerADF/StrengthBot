import aiosqlite
import asyncio
import os

TICKETS_DB = "data/databases/tickets.db"
TRANSCRIPTS_DB = "data/databases/transcripts.db"

async def table_has_column(db_path: str, table: str, column: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        return any(col[1] == column for col in rows)


async def run_safe_sql(db_path: str, sql: str):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(sql)
            await db.commit()
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

async def reset_tickets_db():
    if os.path.exists(TICKETS_DB):
        os.remove(TICKETS_DB)
        print("[✓] Existing tickets.db deleted.")

    async with aiosqlite.connect(TICKETS_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                channel_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL
            );
        """)
        await db.commit()

    print("[✓] New tickets.db created.\n")


async def reset_transcripts_db():
    if os.path.exists(TRANSCRIPTS_DB):
        os.remove(TRANSCRIPTS_DB)
        print("[✓] Existing transcripts.db deleted.")

    async with aiosqlite.connect(TRANSCRIPTS_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                user_id INTEGER,
                content TEXT,
                timestamp INTEGER
            );
        """)
        await db.commit()

        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_channels (
                channel_id INTEGER PRIMARY KEY
            );
        """)
        await db.commit()

    print("[✓] New transcripts.db created.\n")

async def migrate_transcripts_db():
    print("\n--- Migrating transcripts.db ---")

    # ADD attachments column
    if not await table_has_column(TRANSCRIPTS_DB, "messages", "attachments"):
        ok = await run_safe_sql(
            TRANSCRIPTS_DB,
            "ALTER TABLE messages ADD COLUMN attachments TEXT;"
        )
        if ok:
            print("[✓] Added attachments column.")
    else:
        print("[•] attachments column already exists.")

    # ADD embeds column
    if not await table_has_column(TRANSCRIPTS_DB, "messages", "embeds"):
        ok = await run_safe_sql(
            TRANSCRIPTS_DB,
            "ALTER TABLE messages ADD COLUMN embeds TEXT;"
        )
        if ok:
            print("[✓] Added embeds column.")
    else:
        print("[•] embeds column already exists.")

    print("[✓] transcripts.db migration complete.\n")


async def migrate_tickets_db():
    print("\n--- Migrating tickets.db ---")
    print("[•] No ticket migrations defined yet.")

    print("[✓] tickets.db migration complete.\n")

async def menu():
    while True:
        print("""
===============================
  DATABASE MIGRATION MANAGER
===============================

1) Reset tickets.db
2) Reset transcripts.db
3) Migrate transcripts.db
4) Migrate tickets.db
5) Reset ALL databases
0) Exit
""")

        choice = input("Select an option: ").strip()

        if choice == "1":
            confirm = input("RESET tickets.db? (yes/no): ").lower()
            if confirm == "yes":
                await reset_tickets_db()
            else:
                print("Canceled.\n")

        elif choice == "2":
            confirm = input("RESET transcripts.db? (yes/no): ").lower()
            if confirm == "yes":
                await reset_transcripts_db()
            else:
                print("Canceled.\n")

        elif choice == "3":
            await migrate_transcripts_db()

        elif choice == "4":
            await migrate_tickets_db()

        elif choice == "5":
            confirm = input("RESET ALL databases? (yes/no): ").lower()
            if confirm == "yes":
                await reset_tickets_db()
                await reset_transcripts_db()
            else:
                print("Canceled.\n")

        elif choice == "0":
            print("Exiting...")
            break

        else:
            print("Invalid option.\n")


if __name__ == "__main__":
    asyncio.run(menu())
