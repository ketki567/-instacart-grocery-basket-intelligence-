from pathlib import Path
from src.data import connect
from src import engine
out=Path('powerbi/exports');out.mkdir(parents=True,exist_ok=True)
with connect(read_only=True) as conn:
 for name,func,args in [('executive',engine.overview,()),('departments',engine.comparison,('department',100,30)),('hourly_orders',engine.trend,('hour','All')),('customer_segments',engine.basket_segments,()),('order_sequence',engine.cohort,())]:
  df=func(conn,*args);df.to_csv(out/f'{name}.csv',index=False);print('Exported',name,len(df))
