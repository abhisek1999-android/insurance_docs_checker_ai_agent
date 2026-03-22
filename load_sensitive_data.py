import csv
import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "screen_sense"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "10189"),
}

CSV_PATH = r"C:\Users\SENTIENTGEEKS\Downloads\sensitive_vs_nonsensitive_training_data_1.csv"
TABLE_NAME = "sensitive_non_sensitive_data"


def create_table(cursor):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            "id" SERIAL PRIMARY KEY,
            "type" VARCHAR(100),
            "text" TEXT,
            "label" INTEGER
        );
    """)


def load_csv(cursor, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    insert_query = sql.SQL(
        'INSERT INTO {} ("id", "type", "text", "label") VALUES (%s, %s, %s, %s)'
    ).format(sql.Identifier(TABLE_NAME))

    for row in rows:
        cursor.execute(insert_query, (
            int(row["id"]),
            row["type"],
            row["text"],
            int(row["label"]),
        ))

    return len(rows)


def add_updated_at(cursor):
    cursor.execute(f"""
        ALTER TABLE {TABLE_NAME}
        ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMP;
    """)
    cursor.execute(f"""
        UPDATE {TABLE_NAME}
        SET "updated_at" = NOW();
    """)


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        add_updated_at(cursor)
        print("Added 'updated_at' column and set current timestamp on all rows.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
