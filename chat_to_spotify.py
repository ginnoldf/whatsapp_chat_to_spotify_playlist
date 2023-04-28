import string
import random
import webbrowser
import requests
import base64
import re
import urllib.parse
from flask import Flask, redirect, request

CHATFILE = 'chat.txt'

CLIENT_ID = 'c37753bcd6de4be1897691442fcd6759'
CLIENT_SECRET = '78409fb891784743bf772d0413b3295e'
REDIRECT_URI = 'http://localhost:8080/callback'

SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'

PLAYLIST_ID = '6NNR1NKce5swTeO5BYmHeT'

state = ''


app = Flask(__name__)


def get_random_string(length):
    letters = string.ascii_letters
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


def b64(message):
    message_bytes = message.encode('ascii')
    base64_bytes = base64.b64encode(message_bytes)
    base64_message = base64_bytes.decode('ascii')
    return base64_message


def start_auth_flow():
    global state
    state = get_random_string(16)
    url = 'https://accounts.spotify.com/authorize?'
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'scope': 'user-read-private user-read-email',
        'redirect_uri': REDIRECT_URI,
        'state': state
    }
    webbrowser.open(url + urllib.parse.urlencode(params))


@app.route('/callback')
def chat_to_spotify():

    # spotify authorization
    global state
    code = request.args.get('code')
    request_state = request.args.get("state")

    # check state
    if request_state != state:
        print("state mismatch")
        return "<html>State mismatch</html>"

    # get auth token
    params = {
        'client_id': CLIENT_ID,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }

    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + b64(CLIENT_ID + ':' + CLIENT_SECRET)
    }
    token_response = requests.post(SPOTIFY_TOKEN_URL, params=params, headers=headers)
    spotify_auth_header = 'Bearer ' + token_response.json()['access_token']

    # open file
    chat_file = open(CHATFILE, 'r')
    chat_lines = chat_file.readlines()

    # get all urls
    urls = []
    for line in chat_lines:
        line_urls = re.findall(r'(https?://[^\s]+)', line)
        for url in line_urls:
            urls.append(url)

    # get all spotify urls
    spotify_urls = []
    other_urls = []
    for url in urls:
        if 'spotify' in url:
            spotify_urls.append(url)
        else:
            other_urls.append(url)

    # get tracks currently in the playlist
    playlist_url = 'https://api.spotify.com/v1/playlists/' + PLAYLIST_ID + '/tracks'
    params = {'playlist_id': PLAYLIST_ID}
    headers = {'Authorization': spotify_auth_header}
    response = requests.get(playlist_url, params=params, headers=headers)
    playlist_tracks = [x['track']['id'] for x in response.json()['items']]

    # add songs to playlist
    for spotify_url in spotify_urls:
        # handle short links
        if 'spotify.link' in spotify_url:
            spotify_url = requests.Session().head(spotify_url, allow_redirects=True).url

        # get trackid
        track_prefix = 'https://open.spotify.com/track/'
        track_id = spotify_url.strip(track_prefix).split('?')[0]
        spotify_uri = 'spotify:track:' + track_id



    return "<html>Done</html>"


if __name__ == '__main__':
    start_auth_flow()
    app.run(port=8080)
