"""Local optional model converts verified data into prose; SQL stays governed."""
import json
import os
import requests
from .query import interpret_question,Spec

BASE='http://localhost:11434/api/generate'

_status={'checked':0.0,'up':False}

def installed():
    # Remember the answer for a minute so pages don't wait on the connection check repeatedly.
    import time
    if time.time()-_status['checked']>60:
        try:_status['up']=requests.get('http://127.0.0.1:11434/api/tags',timeout=1).ok
        except requests.RequestException:_status['up']=False
        _status['checked']=time.time()
    return _status['up']

def route(question,model='llama3.2:3b'):
    """Return a Spec from a strict JSON model route, or deterministic fallback."""
    fallback,warning=interpret_question(question)
    if warning or not installed(): return fallback,warning
    prompt=('Classify a grocery analytics question. Return ONLY JSON with keys dimension and measure. '
      'dimension in [department,aisle,product,hour,day,order_number]; '
      'measure in [items,orders,customers,reorder_rate,avg_cart_position]. '
      'Never generate SQL. Question: '+question)
    try:
        data=requests.post(BASE,json={'model':model,'prompt':prompt,'stream':False,'format':'json','options':{'temperature':0}},timeout=60).json()
        result=json.loads(data['response'])
        return Spec(dimension=result['dimension'],measure=result['measure'],descending=fallback.descending),None
    except Exception:return fallback,None

def explain(question,df,description,model='llama3.2:3b'):
    if df.empty:return 'No rows matched these filters. Broaden your selection.'
    if not installed():
        hi=df.loc[df['metric'].astype(float).idxmax()];lo=df.loc[df['metric'].astype(float).idxmin()]
        fmt=lambda v:f'{float(v):,.2f}'.rstrip('0').rstrip('.')
        spread=f" Lowest shown: {lo.iloc[0]} ({fmt(lo['metric'])})." if len(df)>1 else ''
        return (f"Highest {description.lower()}: {hi.iloc[0]} ({fmt(hi['metric'])}).{spread} "
                f"Based on {int(df['supporting_items'].sum()):,} purchase lines. This is descriptive, not proof of causation.")
    rows=df.head(15).to_dict('records')
    prompt=('Explain the supplied verified query result to a manager in at most 100 words. '
      'Use ONLY values provided. No causation, no revenue or fabricated comparisons. '
      'Say when limitations apply. Question: '+question+'\nMetric: '+description+'\nRows: '+json.dumps(rows,default=str))
    try:
        r=requests.post(BASE,json={'model':model,'prompt':prompt,'stream':False,'options':{'temperature':0}},timeout=90)
        r.raise_for_status();return r.json()['response'].strip()
    except Exception:return f'Actual query results shown below. {description} Local AI unavailable.'
