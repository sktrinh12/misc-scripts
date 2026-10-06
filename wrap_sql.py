import re
import sys


def sql_to_clob_wrapper(sql_text: str) -> str:
    # 1. Clean up trailing semicolons
    cleaned_sql = sql_text.strip().rstrip(";")

    # 2. Extract column names from the SELECT clause
    # Look for SELECT ... FROM
    match = re.search(r"SELECT\s+(.*?)\s+FROM\s+", cleaned_sql, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Could not parse SELECT statement. Ensure it contains a valid 'SELECT ... FROM' block.")

    select_clause = match.group(1)

    # 3. Split columns by commas outside parentheses (to handle functions safely)
    raw_cols = re.split(r",(?![^()]*\))", select_clause)
    columns = []

    for col in raw_cols:
        col = col.strip()
        if not col:
            continue
        
        # Check if the column has an alias (e.g. "table.col AS my_alias" or "col my_alias")
        alias_match = re.search(r'(?:\s+AS\s+|\s+)([\w_]+)$', col, re.IGNORECASE)
        if alias_match:
            column_identifier = alias_match.group(1)
        else:
            # Handle standard table.column or schema.table.column notation
            column_identifier = col.split(".")[-1]

        columns.append(column_identifier.strip())

    if not columns:
        raise ValueError("No valid columns found in SELECT clause.")

    # 4. Construct header string and row concatenation
    header_string = ",".join(c.upper() for c in columns)
    row_string = " || ',' || ".join(columns)

    # 5. Build query with CTE wrapper
    formatted_query = f"""WITH filtered_data AS (
{cleaned_sql}
)
SELECT 
    TO_CLOB('{header_string}' || CHR(10)) ||
    RTRIM(
        XMLCAST(
            XMLAGG(
                XMLELEMENT(E, {row_string} || CHR(10))
            ) AS CLOB
        ),
        CHR(10)
    ) AS csv_dump
FROM filtered_data"""

    return formatted_query


if __name__ == "__main__":
    input_sql = sys.stdin.read() if not sys.stdin.isatty() else ""

    if not input_sql and len(sys.argv) > 1:
        input_sql = sys.argv[1]

    if not input_sql.strip():
        print("Usage: cat query.sql | python wrap_sql.py")
        sys.exit(1)

    print(sql_to_clob_wrapper(input_sql))
