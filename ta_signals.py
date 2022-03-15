#!/Users/catelinn/miniconda3/envs/quantra/bin/python
'''
Scrape the technical analysis data from www.investing.com
for indices such as SPX and DJA.
'''

import requests
from bs4 import BeautifulSoup as bs
from datetime import datetime, time
import pytz
import re
import pandas as pd
import os



# Asset's pairID and period codes
# can be found in `payload` tab in the network log details    
periodLabels = {'1hr': 3600, '5hr': 18000, 'daily': 86400, 'weekly': 'week'}
pairIDs = {'SPX': 166, 'DJA': 169}
urls = {'SPX':'https://www.investing.com/technical/us-spx-500-technical-analysis', 
        'DJA': 'https://www.investing.com/technical/dj-30-indices-technical-analysis'}


# Save data to file
# as I'd test and compare the performance of the signals downloaded at different time frame 
# I'll seperate the signals data by downlod time: market open, market close and other times
# and save them into different files
def time_in_range(start, end, current):
    return start <= current <= end

def current_f_path():
    current = datetime.now().time()
    data_folder = '/Volumes/ExtremeSSD/github_repos/trading_options/outputs/'
    if time_in_range(time(6,35,0), time(6,37,0), current):
        return data_folder + 'signals_marketopen.csv'

    if time_in_range(time(12,59,0), time(13,2,0), current):
        return data_folder + 'signals_marketclose.csv'

    else:
        return data_folder + 'signals_miscs.csv'

# Simulate post request to have the web server generate TA signal page
# for specified pair and period,
# which shall be returned in the response HTML
def fetch(pair:str='SPX', period:str ='weekly')-> list:
    
    # headers information can be found in Chrome dev tool -> 'network' tab
    headers = { 'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': urls[pair],
                'X-Requested-With': 'XMLHttpRequest'}
    
    body = {'pairID' : pairIDs[pair], 'period': periodLabels[period], 'viewType' : 'normal'}
    
    with requests.Session() as s:
        # send post request
        r = s.post('https://www.investing.com/technical/Service/GetStudiesContent', 
                   data = body, headers = headers)
        # parse the response
        soup = bs(r.content, 'lxml')
        signal = soup.select('#techStudiesInnerWrap .summary')[-1].select('span')[-1].text # the signal
        date = re.sub('M\ \(.*$', 'M', soup.find('div', id='updateTime').text) # when the signal was last updated by the website
        date = est_to_pst(date) 
    return [pair, period, signal, date]
    

# Convert the date from eastern time (used by the website) to pacific time (my time)
def est_to_pst(date:str)-> datetime.date:
    date_time = datetime.strptime(date, '%b %d, %Y %I:%M%p', ) # convert the string to datetime
    date_time = date_time.replace(tzinfo=pytz.timezone('US/Eastern')) # add original timezone  info
    return date_time.astimezone(pytz.timezone("US/Pacific")) # convert to pacific timezone


# Scrape all signals
def process(pairs:list, periods:list)-> list:
    data = []
    for pair in pairs:
        for period in periods:
            data.append(fetch(pair, period))
    return data

# Save signals to csv file
def save(data:list, f_path)-> None:
    
    # append if file already exists
    hdr = False if os.path.isfile(f_path) else True
    pd.DataFrame(data, columns=['pair', 'period', 'signal', 'date']).to_csv(f_path, mode='a', header=hdr, index=False)
    
    # print to log (crontab schedule)
    print(f'new signals downloaded at {datetime.today()} and saved to {f_path}')


# run the script
if __name__ == '__main__':
    periods = ['daily', 'weekly']
    pairs = ['SPX', 'DJA']
    data = process(pairs, periods)
    f_path = current_f_path()
    save(data, f_path)
