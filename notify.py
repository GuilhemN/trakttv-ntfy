#!/usr/bin/env python

from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json
import time
from datetime import date
import os.path
import requests

TOKEN_FILE = os.getenv('TRAKT_TOKENFILE', 't_token')
NTFY_CHANNEL = os.getenv("NTFY_CHANNEL", "trakttv_shows")
NTFY_URL = "https://ntfy.sh/"+NTFY_CHANNEL

class TraktImporter(object):
    """ Trakt Importer """

    def __init__(self):
        self.api_root = 'https://api.trakt.tv'
        self.api_clid = os.getenv('TRAKT_CLIENTID')
        self.api_clsc = os.getenv('TRAKT_CLIENTSECRET')
        self.api_token = None
        self.api_headers = { 'Content-Type': 'application/json' }


    def authenticate(self):
        """ Authenticates the user and grabs an API access token if none is available. """

        if self.__decache_token():
            return True
        
        requests.post(NTFY_URL, data=b"Trakt TV API authentication is necessary.")

        dev_code_details = self.__generate_device_code()

        self.__show_auth_instructions(dev_code_details)

        got_token = self.__poll_for_auth(dev_code_details['device_code'],
                                         dev_code_details['interval'],
                                         dev_code_details['expires_in'] + time.time())

        if got_token:
            self.__encache_token()
            return True

        return False

    def __decache_token(self):
        if not os.path.isfile(TOKEN_FILE):
            return False

        token_file = open(TOKEN_FILE, 'r')
        self.api_token = token_file.read()
        token_file.close()
        return True

    def __encache_token(self):
        token_file = open(TOKEN_FILE, 'w')
        token_file.write(self.api_token)
        token_file.close()

    @staticmethod
    def __delete_token_cache():
        os.remove(TOKEN_FILE)

    def __generate_device_code(self):
        """ Generates a device code for authentication within Trakt. """

        url = self.api_root + '/oauth/device/code'
        data = """{{"client_id": "{0}"}}""".format(self.api_clid).encode('utf8')

        request = Request(url, data, self.api_headers)

        response_body = urlopen(request).read()
        return json.loads(response_body)

    @staticmethod
    def __show_auth_instructions(details):
        message = ("\nGo to {0} on your web browser and enter the below user code there:\n\n"
                   "{1}\n\nAfter you have authenticated and given permission;"
                   "come back here to continue.\n"
                  ).format(details['verification_url'], details['user_code'])
        print(message)

    def __poll_for_auth(self, device_code, interval, expiry):
        """ Polls for authorization token """
        url = self.api_root + '/oauth/device/token'
        data = """{{ "code":          "{0}",
                     "client_id":     "{1}",
                     "client_secret": "{2}" }}
                       """.format(device_code, self.api_clid, self.api_clsc).encode('utf8')

        request = Request(url, data, self.api_headers)

        response_body = ""
        should_stop = False

        print("Waiting for authorization.", end=' ')

        while not should_stop:
            time.sleep(interval)

            try:
                response_body = urlopen(request).read()
                should_stop = True
            except HTTPError as err:
                if err.code == 400:
                    print(".", end=' ')
                else:
                    print("\n{0} : Authorization failed, please try again. Script will now quit.".format(err.code))
                    should_stop = True

            should_stop = should_stop or (time.time() > expiry)

        if response_body:
            response_dict = json.loads(response_body)
            if response_dict and 'access_token' in response_dict:
                print("Authenticated!")
                self.api_token = response_dict['access_token']
                print("Token:" + self.api_token)
                return True

        # Errored.
        return False

    def get_calendar(self, date, numberdays=1):
        """ Get movie list of the user. """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.api_token,
            'trakt-api-version': '2',
            'trakt-api-key': self.api_clid
        }

        request = Request(self.api_root + '/calendars/my/shows/'+str(date)+'/'+str(numberdays), headers=headers)
        try:
            response = urlopen(request)

            response_body = response.read()
            return self.__extract_fields(json.loads(response_body))
        except HTTPError as err:
            if err.code == 401 or err.code == 403:
                print("Auth Token has expired.")
                self.__delete_token_cache() # This will regenerate token on next run.
            print("{0} An error occured. Please re-run the script".format(err.code))
            quit()

    @staticmethod
    def __extract_fields(calendar):
        return [{
            'show': x['show']['title'],
            'season': x['episode']['season'],
            'number': x['episode']['number'],
        } for x in calendar]

def notify(calendar):
    for entry in calendar:
        requests.post(NTFY_URL, data=f"New Ep - {entry['show']}: S{entry['season']} E{entry['number']}!".encode(encoding='utf-8'))

def run():
    """Get set go!"""

    print("Initializing...")
    print(f"Updates will be sent to channel: {NTFY_CHANNEL}")

    importer = TraktImporter()
    if importer.authenticate():
        today = date.today()
        print(f"Importing today's calendar ({str(today)})...")
        calendar = importer.get_calendar(date.today(), 1)

        print(f"Send notifications for {len(calendar)} entries...")
        notify(calendar)

if __name__ == '__main__':
    run()
