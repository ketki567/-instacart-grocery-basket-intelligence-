import pytest
from src.sql_lab import validate


def test_allows_select_and_with():
    assert validate('SELECT * FROM orders LIMIT 5;') == 'SELECT * FROM orders LIMIT 5'
    assert validate('-- comment\nWITH x AS (SELECT 1 AS a) SELECT a FROM x').startswith('WITH')


def test_allows_keywords_inside_strings_and_identifiers():
    assert validate("SELECT eval_set FROM orders WHERE eval_set = 'drop; delete'")


@pytest.mark.parametrize('sql', [
    'DROP TABLE orders',
    'UPDATE orders SET user_id = 1',
    'SELECT 1; SELECT 2',
    "SELECT pg_read_file('postgresql.conf')",
    "SELECT set_config('x', 'y', false)",
    'WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x',
    '',
])
def test_blocks_unsafe_sql(sql):
    with pytest.raises(ValueError):
        validate(sql)
