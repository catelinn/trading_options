from bs4 import BeautifulSoup as bs
from matplotlib.collections import EventCollection

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


for row in table.findAll('tr'):
    cells = row.findAll('td')
    print([extractText(cell) for cell in cells], '\n')