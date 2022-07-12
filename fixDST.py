import pandas as pd
from datetime import datetime, timedelta

# fix time error due to day time saving
f = 'outputs/signals_marketclose.csv'
df = pd.read_csv(f)

isDST = df['date'].str.contains('-07:00')
df.loc[isDST, 'date'] = pd.to_datetime(df.loc[isDST,'date'])-pd.DateOffset(hours=1)

print(df.loc[isDST, 'date'])
df.to_csv(f)
