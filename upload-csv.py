import argparse
import csv
import sqlite3
from datetime import datetime
import os

home_path = os.path.expanduser("~")
db_file = "chase-expenses.db"
db_path = os.path.join(home_path, "Documents", "finances", "chase", db_file)


def parse_date(date_str):
    date_formats = ["%m/%d/%Y", "%Y-%m-%d"]
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unknown date format: {date_str}")


def normalize_amount(amount_str):
    amount = float(amount_str.strip())
    return -abs(amount)  # Always negative


def insert_expenses(rows):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL
        )
    """)

    for row in rows:
        cursor.execute(
            """
            INSERT INTO expenses (date, description, category, amount)
            VALUES (?, ?, ?, ?)
        """,
            row,
        )

    conn.commit()
    conn.close()


def parse_csv_file(filepath):
    header_mappings = [
        {  # Format 1
            "DATE": "DATE",
            "DESCR": "DESCR",
            "CATEGORY": "CATEGORY",
            "AMOUNT": "AMOUNT",
        },
        {  # Format 2
            "DATE": "Transaction Date",
            "DESCR": "Description",
            "CATEGORY": "Category",
            "AMOUNT": "Amount",
        },
    ]
    with open(filepath, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = set(reader.fieldnames or [])

        mapping = None
        for candidate in header_mappings:
            if set(candidate.values()).issubset(fieldnames):
                mapping = candidate
                break

        if mapping is None:
            raise ValueError(f"Unrecognized header format. Found: {reader.fieldnames}")

        parsed_rows = []
        for line in reader:
            try:
                date = parse_date(line[mapping["DATE"]])
                description = line[mapping["DESCR"]].strip()
                category = line[mapping["CATEGORY"]].strip()
                amount = normalize_amount(line[mapping["AMOUNT"]])
                parsed_rows.append((date, description, category, amount))
            except Exception as e:
                print(f"Skipping line due to error: {e}\nLine: {line}")
        return parsed_rows


def main():
    parser = argparse.ArgumentParser(
        description="Import Chase expense CSV into SQLite database."
    )
    parser.add_argument("csv_file", help="Path to the CSV file")
    args = parser.parse_args()

    if not os.path.isfile(args.csv_file):
        print(f"File not found: {args.csv_file}")
        return

    try:
        expenses = parse_csv_file(args.csv_file)
        insert_expenses(expenses)
        print(f"Imported {len(expenses)} expenses into {db_file}")
    except Exception as e:
        print(f"Error processing file: {e}")


if __name__ == "__main__":
    main()
