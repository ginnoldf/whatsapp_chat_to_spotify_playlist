import requests

from server import app


# get userinfo for current user
def get_userinfo(access_token):
    userinfo_url = 'https://api.spotify.com/v1/me'
    headers = {'Authorization': 'Bearer ' + access_token}
    user_response = requests.get(userinfo_url, headers=headers)
    return user_response.json()['display_name'], user_response.json()['id']


# get all playlists from a user
def get_playlists(access_token, spotify_user_id):
    # get total number of playlists
    my_playlists_api_url = 'https://api.spotify.com/v1/users/' + spotify_user_id + '/playlists'
    headers = {'Authorization': 'Bearer ' + access_token}
    num_playlists_response = requests.get(my_playlists_api_url + '?limit=0', headers=headers)
    num_playlists = num_playlists_response.json()['total']

    # get all playlists
    playlists = []
    playlists_per_request = 20

    # batchwise request playlists and check if the current user owns them
    for batch_start in range(0, num_playlists, playlists_per_request):
        playlists_response = requests.get(my_playlists_api_url + '?limit=' + str(playlists_per_request) +
                                          '&offset=' + str(batch_start),
                                          headers=headers)
        for received_playlist in playlists_response.json()['items']:
            if received_playlist['owner']['id'] == spotify_user_id or \
                    received_playlist['collaborative'] is True:
                playlists.append({'id': received_playlist['id'], 'name': received_playlist['name']})
    return playlists


# create a playlist
def create_playlist(access_token, spotify_user_id, playlist_name):
    create_playlist_url = 'https://api.spotify.com/v1/users/' + spotify_user_id + '/playlists'
    create_playlist_headers = {'Authorization': 'Bearer ' + access_token}
    create_playlist_data = {
        "name": playlist_name,
        "description": "Created by chat2playlist",
        "public": False
    }
    add_tracks_response = requests.post(create_playlist_url,
                                        json=create_playlist_data,
                                        headers=create_playlist_headers)

    return add_tracks_response.json()['id']


# get ids for all tracks currently in a playlist
def get_playlist_track_ids(access_token, playlist_id):
    get_playlist_url = 'https://api.spotify.com/v1/playlists/' + playlist_id + '/tracks'
    get_playlist_params = {'playlist_id': playlist_id}
    get_playlist_headers = {'Authorization': 'Bearer ' + access_token}
    get_playlist_response = requests.get(get_playlist_url,
                                         params=get_playlist_params,
                                         headers=get_playlist_headers)
    return [x['track']['id'] for x in get_playlist_response.json()['items']]


# add tracks to a playlist
def add_tracks_to_playlist(access_token, playlist_id, track_uris):
    # add 100 tracks at a time
    batch_size = 100
    while len(track_uris) > 0:
        add_tracks_url = 'https://api.spotify.com/v1/playlists/' + playlist_id + '/tracks'
        add_tracks_data = {'uris': track_uris[:batch_size]}
        add_tracks_headers = {'Authorization': 'Bearer ' + access_token}
        add_tracks_response = requests.post(add_tracks_url, json=add_tracks_data, headers=add_tracks_headers)

        # remove tracks that were added from the list
        del track_uris[:batch_size]
