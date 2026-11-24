'''SQL Lab guardrails: one read-only SELECT/WITH statement, no system functions, a time limit and a row cap.'''
import re
import time
from .data import connect
from .query import query_dataframe

MAX_ROWS = 1000
TIMEOUT_MS = 20000
BLOCKED = re.compile(r'\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|copy|call|do|vacuum|analyze|'
                     r'cluster|reindex|listen|notify|lock|set|reset|prepare|execute|deallocate|discard|checkpoint|'
                     r'pg_\w+|lo_\w+|dblink\w*|set_config|current_setting|query_to_xml\w*|pg_catalog)\b', re.I)


def strip_comments(sql):
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.S)
    return re.sub(r'--[^\n]*', ' ', sql)


def validate(sql):
    '''Return a cleaned single statement or raise ValueError explaining what is not allowed.'''
    body = strip_comments(sql).strip().rstrip(';').strip()
    if not body: raise ValueError('Write a query first.')
    without_strings = re.sub(r"'(?:[^']|'')*'", "''", body)
    if ';' in without_strings: raise ValueError('Only one statement at a time. Remove the extra semicolon.')
    if not re.match(r'^(select|with)\b', without_strings, re.I): raise ValueError('Only SELECT (or WITH … SELECT) queries are allowed.')
    hit = BLOCKED.search(without_strings)
    if hit: raise ValueError(f'“{hit.group(0)}” is not allowed in the SQL Lab (read only analysis only).')
    return body


def execute(sql):
    body = validate(sql)
    with connect(read_only=True) as conn:
        conn.execute(f'SET statement_timeout = {TIMEOUT_MS}')
        started = time.perf_counter()
        df = query_dataframe(conn, f'SELECT * FROM ({body}) AS lab_query LIMIT {MAX_ROWS + 1}')
        elapsed = time.perf_counter() - started
    truncated = len(df) > MAX_ROWS
    return df.head(MAX_ROWS), elapsed, truncated


def schema():
    with connect(read_only=True) as conn:
        return query_dataframe(conn, '''SELECT table_name, column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'public' ORDER BY table_name, ordinal_position''')
