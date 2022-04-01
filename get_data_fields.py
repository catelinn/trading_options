from bs4 import BeautifulSoup as bs
from matplotlib.collections import EventCollection
import pandas as pd

with open('fields.html') as f:

    html = f.read()

soup = bs(html)
table = soup.find('table')


def extractText(cell):
    '''
    Extract text from tag p or ul
    as some cell contains list of items instead of text
    '''
    try:
        return cell.find('p').text
    except:
        pass

    try:
        list = cell.find('ul')
        items = list.findAll('li')
        return (items)
    except:
        pass

data = []
for row in table.findAll('tr'):
    cells = row.findAll('td')
    data.append([extractText(cell) for cell in cells])

df = pd.DataFrame(columns=data[0], data=data[1:])
df.to_csv('QUOTE_fields.csv')