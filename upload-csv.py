import argparse
import csv
from datetime import datetime
import os
import sqlite3

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

    # Note: Keep standard columns without rigid UNIQUE constraints
    # so we can intentionally insert valid duplicates.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL
        )
    """)

    imported_count = 0

    for row in rows:
        date, description, category, amount = row

        # Check if an identical entry already exists
        cursor.execute(
            """
            SELECT COUNT(*) FROM expenses
            WHERE date = ? AND description = ? AND amount = ?
        """,
            (date, description, amount),
        )
        exists = cursor.fetchone()[0]

        if exists > 0:
            print("\n" + "!" * 50)
            print(f"⚠️  POSSIBLE DUPLICATE FOUND IN DATABASE:")
            print(f"  Date:        {date}")
            print(f"  Description: {description}")
            print(f"  Category:    {category}")
            print(f"  Amount:      ${abs(amount):.2f}")
            print("!" * 50)

            # Interactive Yes/No prompt
            choice = input("Is this a separate/legitimate charge? (y/n): ").strip().lower()
            if choice != 'y':
                print("Skipping entry.")
                continue

        # Insert entry if it's unique OR explicitly approved by user
        cursor.execute(
            """
            INSERT INTO expenses (date, description, category, amount)
            VALUES (?, ?, ?, ?)
        """,
            row,
        )
        imported_count += 1

    conn.commit()
    conn.close()
    return imported_count


def parse_csv_file(filepath):
    header_mappings = [
        {  # Format 1
            "DATE": "DATE",
            "DESCR": "DESCR",
            "MEMO": "MEMO",
            "CATEGORY": "CATEGORY",
            "AMOUNT": "AMOUNT",
        },
        {  # Format 2
            "DATE": "Transaction Date",
            "DESCR": "Description",
            "MEMO": "Memo",
            "CATEGORY": "Category",
            "AMOUNT": "Amount",
        },
    ]
    with open(filepath, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = set(reader.fieldnames or [])

        mapping = None
        # Core columns required to identify header format
        required_keys = ["DATE", "DESCR", "CATEGORY", "AMOUNT"]

        for candidate in header_mappings:
            required_headers = {candidate[k] for k in required_keys}
            if required_headers.issubset(fieldnames):
                mapping = candidate
                break

        if mapping is None:
            raise ValueError(f"Unrecognized header format. Found: {reader.fieldnames}")

        parsed_rows = []
        memo_col = mapping["MEMO"]

        for line in reader:
            try:
                date = parse_date(line[mapping["DATE"]])
                description = line[mapping["DESCR"]].strip()

                # Retrieve and format Memo if present in row
                memo = line.get(memo_col, "").strip() if memo_col in fieldnames else ""

                if memo:
                    # Append period if description doesn't already end with terminal punctuation
                    if not description.endswith(('.', '!', '?')):
                        description += "."
                    description = f"{description} {memo}"

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
        # Reverse list so older entries are prompted/inserted first
        expenses.reverse()

        count = insert_expenses(expenses)
        print(f"\nSuccessfully processed and added {count} expense records into {db_file}!")
    except Exception as e:
        print(f"Error processing file: {e}")


if __name__ == "__main__":
    main()
