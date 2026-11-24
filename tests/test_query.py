import pytest
from src.query import Spec,compile_query,interpret_question,validate

def test_bound_filters():
 sql,values=compile_query(Spec(dimension='product',measure='reorder_rate',department="Men's",limit=10))
 assert "Men's" not in sql
 assert "Men's" in values
 assert 'GROUP BY product_name' in sql

def test_reject_unknown_fields():
 with pytest.raises(ValueError): compile_query(Spec(dimension=';DROP TABLE orders'))
 with pytest.raises(ValueError): compile_query(Spec(measure='sum(price)'))

def test_range_guardrails():
 with pytest.raises(ValueError):validate(Spec(hour_start=20,hour_end=8))
 with pytest.raises(ValueError):validate(Spec(limit=1000))

def test_question_interpreter():
 spec,err=interpret_question('Which product has the highest reorder rate?')
 assert err is None and spec.dimension=='product' and spec.measure=='reorder_rate'
 assert interpret_question('Which products generate most revenue?')[0] is None

def test_least_questions_sort_ascending():
 spec,err=interpret_question('least bought item?')
 assert err is None and spec.dimension=='product' and spec.measure=='items' and spec.descending is False
 assert interpret_question('Which aisle has the lowest reorder rate?')[0].descending is False
 assert interpret_question('What are the most popular products?')[0].descending is True
