import time
import urllib
import os
import requests
import datetime
from datetime import date
from splinter import Browser
from selenium import webdriver
from config import accounts
import getpass # manual input of encrypted password (only required to get initial access code)



class TdAuthClient:
    '''tda authentication - retrieve access_token for authorized access to TDA endpoints'''

    # initiate
    def __init__(self, acc_type='margin'):

        self.access_token = None
        self.refresh_token = None
        self.client_id = accounts[acc_type]['clientId']
        self.account_id = accounts[acc_type]['accountNumber']

        # import existing and unexpired refresh_token
        if os.path.exists('refresh_token.py'):
            from refresh_token import expiry
            if datetime.datetime.strptime(expiry, '%m%d%Y').date() > date.today():
                from refresh_token import refresh_token
                self.refresh_token = refresh_token     
                

        if refresh_token is None:
            print('refresh token does not exist or has expired, new authentication that follows login flow is required.')
            self.username = accounts[acc_type]['username']
            self.password = getpass.getpass(f'Enter password for user "{self.username}":')
            self.callback_url = accounts[acc_type]['callbackUrl']
                

    # complete authentication: get a valid access token
    # - If refresh token unexpired, use it to refresh access token
    # - If refresh token expired or non exists, get an initial access token and a new refresh token
    def authenticate(self):
        if self.refresh_token:
            self.refresh_access_token()
        else:
            self.get_first_access_token()
    
    # to get initial access token, use browser to visit authentication url
    # 2 factor authentication required - enter sms code in console
    def new_authentication(self):
    
        """prepare authentication url"""
        # Define all components of the URL
        url = f'https://auth.tdameritrade.com/auth?'
        method = 'GET'
        client_code = self.client_id + '@AMER.OAUTHAP'
        payload = {'response_type': 'code', 'redirect_uri': self.callback_url, 'client_id': client_code}

        # build the url
        built_url = requests.Request(method, url, params=payload).prepare()
        self.built_url = built_url.url

        """Invoke browser"""
        # path to chrome driver
        executable_path = {'executable_path': '/Users/catelinn/drivers_for_dev/chromedriver'}

        # Set default behaviors as Chrome Browser
        options = webdriver.ChromeOptions()

        # make sure the window is maximized
        options.add_argument('--start-maximized')

        # make sure notification are off
        options.add_argument('--disable-notifications')

        # create a new browser object, which
        # 1. by default is Firefox, here, I use 'chrome';
        # 2. connect to my chrome webdriver path
        # 3. set `headless` to `False` to see the activities in browser, `True` not to see
        # 4. pass in `options` to customize browser
        browser = Browser('chrome', **executable_path, headless = False, options = options)
        
        """Now, we can visit the user authentication page"""
        browser.visit(self.built_url)

        # === Inspect the page and find the following ===
        # ===============================================
        # userID box
        username_box = browser.find_by_id('username0')

        # password box
        password_box = browser.find_by_id('password1')

        # === Automatic Authentication   ====
        # ===================================
        # fill in username and password at login page
        username_box.fill(self.username)
        password_box.fill(self.password)
        browser.find_by_id('accept').first.click()

        # continue to receive sms code
        time.sleep(1) #give it a second to load
        browser.find_by_id('accept').click()

        # enter sms code
        time.sleep(1)
        smscode = input('Enter sms code: ')
        browser.find_by_id('smscode0').type(smscode)
        browser.find_by_id('accept').first.click()

        # confirm trust device
        time.sleep(1)
        browser.find_by_xpath('/html/body/form/main/fieldset/div/div[1]').click()
        browser.find_by_id('accept').first.click()

        # confirm authorization
        time.sleep(1)
        browser.find_by_id('accept').first.click()

        """ the final url that shall contains the access token """
        new_url = browser.url

        """ close the browser """
        browser.quit()

        # parse the url to retrieve autheorization code
        return urllib.parse.unquote(new_url.split('code=')[1])
        print('New authentication code retrieved. ')

    
    # Get the intial access token and a new refresh token
    def get_first_access_token(self):
        
        # define the endpoint
        url = 'https://api.tdameritrade.com/v1/oauth2/token'

        # define the headers
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        # define the payload
        auth_code = self.new_authentication()
        payload = {'grant_type': 'authorization_code',
                'access_type': 'offline',
                'code': auth_code,
                'client_id': self.client_id,
                'redirect_uri': self.callback_url}

        # post the data to get the token
        r = requests.post(url, headers=headers, data=payload)
        self.access_token = r.json()['access_token']
        self.refresh_token = r.json()['refresh_token']
        print('New access_token and refresh_token retrieved')

        # save the new refresh token and expiry date (refresh token expires in 90 days)
        expiry = (date.today() + datetime.timedelta(days=90*2)).strftime("%m%d%Y")
        f = open('refresh_token.py', 'w')
        f.write('refresh_token='+repr(self.refresh_token))
        f.write('\nexpiry='+repr(expiry))
        f.close()
        print('Refresh_token saved to refresh_token.py')


    # use unexpired refresh token to refresh access token (skip 2 factor authorization)   
    def refresh_access_token(self):
        # define the endpoint
        url = 'https://api.tdameritrade.com/v1/oauth2/token'

        # define the headers
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        # define the payload
        payload = {'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'refresh_token': self.refresh_token}

        # post the data to get the token
        r = requests.post(url, headers=headers, data=payload)
        self.access_token = r.json()['access_token']
        print("New access token retrieved with unexpired refresh token.")


class StreamClient:
    
    pass
