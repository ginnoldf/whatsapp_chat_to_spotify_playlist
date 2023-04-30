import os
import logging
import requests
from flask import Flask, redirect, request, session, render_template
from urllib.parse import urlencode
import re
from requests.exceptions import HTTPError

import util

CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'

# create flask app
app = Flask(__name__)
app.secret_key = os.getenv('APP_SECRET_SESSION_KEY')
app.logger.setLevel(logging.DEBUG)


# root
@app.route('/')
def root():
    return app.send_static_file('index.html')


# do the login flow
@app.route('/login', methods=['POST'])
def login():
    session['state'] = util.get_random_string(16)
    url = 'https://accounts.spotify.com/authorize?'
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'scope': 'user-read-private user-read-email playlist-modify-private playlist-modify-public',
        'redirect_uri': REDIRECT_URI,
        'state': session['state']
    }
    return redirect(url + urlencode(params))


@app.route('/callback')
def callback():
    session['code'] = request.args.get('code')
    received_state = request.args.get("state")

    # check state
    if received_state != session['state']:
        return render_template('error.html', message='states do not match')

    # get auth token and save it in session
    params = {
        'client_id': CLIENT_ID,
        'grant_type': 'authorization_code',
        'code': session['code'],
        'redirect_uri': REDIRECT_URI
    }
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + util.b64(CLIENT_ID + ':' + CLIENT_SECRET)
    }
    token_response = requests.post(SPOTIFY_TOKEN_URL, params=params, headers=headers)
    session['access_token'] = token_response.json()['access_token']

    # get users name to welcome them
    playlist_url = 'https://api.spotify.com/v1/me'
    headers = {'Authorization': 'Bearer ' + session['access_token']}
    user_response = requests.get(playlist_url, params=params, headers=headers)
    session['display_name'] = user_response.json()['display_name']
    app.logger.info(session['display_name'] + ' logged in')

    # redirect to playlist page
    return redirect('/form')


@app.route('/form', methods=['GET', 'POST'])
def form():
    # verify session
    if not util.session_valid(session):
        return redirect('/login')
    return render_template('form.html', display_name=session['display_name'])


@app.route('/chat-to-playlist', methods=['POST'])
def chat_to_playlist():
    # verify session
    if not util.session_valid(session):
        return redirect('/login')

    # read request
    received_file = request.files['chat_export']
    playlist_id = request.form['playlist_id']

    # read chat file
    chat_path = '/tmp/' + util.get_random_string(16) + '.txt'
    received_file.save(chat_path)
    chat_file = open(chat_path, 'r')
    chat_lines = chat_file.readlines()

    # get all urls
    urls = []
    for line in chat_lines:
        line_urls = re.findall(r'(https?://[^\s]+)', line)
        for url in line_urls:
            urls.append(url)

    # get all spotify track ids from the chat
    chat_track_ids = []
    track_prefix = 'https://open.spotify.com/track/'
    for url in urls:
        # find spotify links
        if 'spotify' in url:
            # handle short links
            if 'spotify.link' in url:
                url = requests.Session().head(url, allow_redirects=True).url
            # check, if it is a track url
            if url.startswith(track_prefix):
                chat_track_ids.append(url.strip(track_prefix).split('?')[0])

    # get tracks currently in the playlist
    playlist_api_url = 'https://api.spotify.com/v1/playlists/' + playlist_id + '/tracks'
    params = {'playlist_id': playlist_id}
    headers = {'Authorization': 'Bearer ' + session['access_token']}
    response = requests.get(playlist_api_url, params=params, headers=headers)

    # handle unsuccessful playlist request
    if response.status_code != 200:
        return render_template('error.html', message='could not get playlist')

    # get track ids
    playlist_track_ids = [x['track']['id'] for x in response.json()['items']]
    playlist_url = 'https://open.spotify.com/playlist/' + playlist_id

    # create requests to add tracks
    uris_to_add = []
    for track_id in chat_track_ids:

        # continue only if the track is not in the playlist already
        if track_id not in playlist_track_ids:
            uris_to_add.append('spotify:track:' + track_id)

    # add 100 tracks at a time
    while len(uris_to_add) > 0:
        add_tracks_url = 'https://api.spotify.com/v1/playlists/' + playlist_id + '/tracks'
        add_tracks_data = {'uris': uris_to_add[:100]}
        add_tracks_headers = {'Authorization': 'Bearer ' + session['access_token']}

        try:
            add_tracks_response = requests.post(add_tracks_url, json=add_tracks_data, headers=add_tracks_headers)
        except HTTPError as e:
            app.logger.debug(e.response.text)
            return render_template('error.html', message='could not add tracks')

        # somehow not all requests throw exceptions
        if add_tracks_response.status_code not in [200, 201]:
            app.logger.debug('response status: ' + str(add_tracks_response.status_code))
            app.logger.debug(add_tracks_response.reason)
            return render_template('error.html', message='Spotify said '
                                                         + str(add_tracks_response.status_code)
                                                         + ' ' + add_tracks_response.reason)

        # remove tracks that were added from the list
        del uris_to_add[:100]

    return render_template("done.html", display_name=session['display_name'], playlist_url=playlist_url)


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
