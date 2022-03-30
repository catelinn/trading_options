import time
import urllib
import os
import requests
import datetime
from datetime import date
from splinter import Browser
from selenium import webdriver
import getpass # manual input of encrypted password (only required to get initial access code)
import re
import json
from dateutil import parser

import websockets
from websockets import client as wsClient
import asyncio


# import config files
# add sys path for Python interpreter to search in
# (the above is required when this file is called as required module in another file in a different directory)
import sys
path_to_files = '/Volumes/ExtremeSSD/github_repos/trading_options/app'
sys.path.insert(1, path_to_files)
from tda.config.config import accounts
try:
    from tda.config.refresh_token import refresh_token, expiry
except ImportError:
    refresh_token = None


class Client:
    '''tda authentication client - retrieve access_token for authorized access to TDA endpoints'''

    # initiate
    def __init__(self, acc_type='margin'):

        self.access_token = None
        self.client_id = accounts[acc_type]['clientId']
        self.account_id = accounts[acc_type]['accountNumber']

        # import existing and unexpired refresh_token
        self.refresh_token = refresh_token
        if self.refresh_token:
            if datetime.datetime.strptime(expiry, '%m%d%Y').date() <= date.today():
                self.refresh_token = None 
            
        if self.refresh_token is None:
            self.username = accounts[acc_type]['username']
            self.password = getpass.getpass(f'Enter password for user "{self.username}":')
            self.callback_url = accounts[acc_type]['callbackUrl']
            print('refresh token does not exist or has expired, new authentication with login flow is required.')
                

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
        options.add_argument('--start-maximized disable-infobars')

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
        r = requests.post(url, headers=headers, data=payload, timeout=5)
        self.access_token = r.json()['access_token']
        self.refresh_token = r.json()['refresh_token']
        print('New access_token and refresh_token retrieved')

        # save the new refresh token and expiry date (refresh token expires in 90 days)
        expiry = (date.today() + datetime.timedelta(days=90*2)).strftime("%m%d%Y")
        f_dir = '/Volumes/ExtremeSSD/github_repos/trading_options/app/tda/config/'
        f = open(f_dir+'refresh_token.py', 'w')
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
        try:
            r = requests.post(url, headers=headers, data=payload, timeout=5)
            self.access_token = r.json()['access_token']
            print("New access token retrieved with unexpired refresh token.")
        except requests.exceptions.ConnectTimeout as e:
            print(e)
            exit()
        


class WebSocketClient():
    """The client """
    
    def __init__(self, uri):
        self.uri = uri
        
    async def connect(self):
        '''
            Connecting to webSocket server
            websockets.client.connect returns a WebSocketClientProtocol, which is used to send and receive messages
        '''
                
        # connect to a websocket
        self.connection = await wsClient.connect(self.uri)
        
        # if all goes well, let the user know
        if self.connection.open:
            print("connection established. client correctly connected")
            return self.connection
        
    async def sendMessage(self, message):
        '''
            Sending message to webSocket server: 
            - send login information
            - subscribe to data
        '''
        await self.connection.send(message)
        
    async def receiveMessage(self, connection):
        '''
            Receiving all server messages and handle them 
            it'd be in infinite loop, won't stop until user interruption
        '''
        while True:   
            try: 
                # grab and decode the message
                message = await connection.recv()
                message_decoded = json.loads(message)
                
                # print the data if the response contains data
                if 'data' in message_decoded.keys():
                    print(message_decoded['data'])
                
                print('-'*20)
                print('Received message from server:'+ str(message))
                
            except websockets.exceptions.ConnectionClosed:
                print("connection with server closed")
                break
                
                
    async def heartbeat(self, connection):
        '''
            Sending heartbeat to server every 5 seconds
            Ping - pong messages to verify connection is alive
        '''
        while True:
            try:
                await connection.send('ping')
                await asyncio.sleep(5)
            except websockets.exceptions.ConnectionClosed:
                print('Connection with server closed')
                break                 


class StreamClient():
    
    def __init__(self, client):
        self.account_id = client.account_id
        self.access_token = client.access_token 

    async def login(self):
        # Get Streamer info from User Principles
        headers = {'Authorization': f'Bearer {self.access_token}'}
        endpoint = 'https://api.tdameritrade.com/v1/userprincipals'
        params = {'fields':'streamerSubscriptionKeys,streamerConnectionInfo'}
        r = requests.get(url=endpoint, params=params, headers=headers)
        userPrinciplesResponse = r.json()

        # Extract streamer information
        streamerInfo = userPrinciplesResponse['streamerInfo']

        # Extract specific account details
        for account in userPrinciplesResponse['accounts']:
            if account['accountId'] == self.account_id:
                account = account
        
        # Grab the token timestamp and convert it to ms since epoch, which is accepted by Streamer
        def unix_time_ms(dt):
            # grab the starting point, so time '0'
            epoch = datetime.datetime.utcfromtimestamp(0)
            
            return (dt-epoch).total_seconds() * 1000.0

        tokentimestamp = streamerInfo['tokenTimestamp']
        tokentimestamp = parser.parse(tokentimestamp, ignoretz=True)
        tokentimestampMs = unix_time_ms(tokentimestamp)

        # Define the credentials required for login command
        credential = {
            'userid': account['accountId'],
            'token': streamerInfo['token'], 
            'company':  account['company'],
            'segment': account['segment'],
            'cddomain': account['accountCdDomainId'],
            'usergroup':streamerInfo['userGroup'],
            'accesslevel': streamerInfo['accessLevel'],
            'authorized': 'Y',
            'acl': streamerInfo['acl'],
            'timestamp': int(tokentimestampMs),
            'appid': streamerInfo['appId']    
            }

        
        # Define a login request
        login_request = {
            'service':'ADMIN',
            'requestid': '0', # login request comes first
            'command': 'LOGIN',
            'account': self.account_id,
            'source': streamerInfo['appId'],
            'parameters': {
                'token': streamerInfo['token'],
                'version': '1.0',
                'credential': urllib.parse.urlencode(credential) # convert json arguments to a query string
            }
        }

        # turn the request into json strings
        login_encoded = json.dumps(login_request)

        # Extract websocket streamer url
        uri = 'wss://'+streamerInfo['streamerSocketUrl']+'/ws'

        # send login request to streamer api
        ws = WebSocketClient(uri)
        self.connection = await ws.connect()


client = Client()
#client.get_first_access_token()
client.authenticate()


async def main():
    stream_client = StreamClient(client)
    await stream_client.login()

asyncio.run(main())

        


#print('OK')