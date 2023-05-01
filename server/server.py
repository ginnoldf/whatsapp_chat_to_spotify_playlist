import os
import logging
import requests
from flask import Flask, redirect, request, session, render_template
from urllib.parse import urlencode
import re
from requests.exceptions import HTTPError


import spotify
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
    scope = 'user-read-private playlist-modify-private playlist-modify-public playlist-read-private playlist-read-collaborative ugc-image-upload'
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'scope': scope,
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
    session['display_name'], session['spotify_user_id'] = spotify.get_userinfo(access_token=session['access_token'])

    # redirect to form page
    return redirect('/form')


@app.route('/form', methods=['GET', 'POST'])
def form():
    # verify session
    if not util.session_valid(session):
        return redirect('/login')
    playlists = spotify.get_playlists(access_token=session['access_token'], spotify_user_id=session['spotify_user_id'])
    return render_template('form.html', display_name=session['display_name'], playlists=playlists)


@app.route('/chat-to-playlist', methods=['POST'])
def chat_to_playlist():
    # verify session
    if not util.session_valid(session):
        return redirect('/login')

    # read request
    received_file = request.files['chat_export']
    playlist_setting = request.form['playlist_rb']
    new_playlist_name = request.form['new_playlist_name']
    playlist_id = request.form['playlist_existing']


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

    # create a playlist if chosen
    if playlist_setting == 'NEW':
        playlist_id = spotify.create_playlist(access_token=session['access_token'],
                                              spotify_user_id=session['spotify_user_id'],
                                              playlist_name=new_playlist_name)
        spotify.set_cover_image(session['access_token'], playlist_id)

    # get tracks currently in the playlist
    playlist_track_ids = spotify.get_playlist_track_ids(access_token=session['access_token'], playlist_id=playlist_id)

    # create requests to add tracks
    uris_to_add = []
    for track_id in chat_track_ids:
        # continue only if the track is not in the playlist already
        if track_id not in playlist_track_ids:
            uris_to_add.append('spotify:track:' + track_id)

    # add tracks to playlist
    spotify.add_tracks_to_playlist(access_token=session['access_token'],
                                   playlist_id=playlist_id,
                                   track_uris=uris_to_add)

    return render_template("done.html",
                           display_name=session['display_name'],
                           playlist_url='https://open.spotify.com/playlist/' + playlist_id)


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
