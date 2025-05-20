import sys
import sqlparse

contents = sys.stdin.read()

comma_first = False 

result = sqlparse.format(contents
                         , indent_columns=True
                         , keyword_case='upper'
                         , identifier_case='lower'
                         , reindent=True
                         , output_format='sql'
                         , indent_after_first=True
                         , comma_first=comma_first
                         )

print(result.strip())
