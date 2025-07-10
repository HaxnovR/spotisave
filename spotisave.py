import re
import sys
import spotipy
import pandas as pd
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import os
import string

# Load environment variables from .env
load_dotenv()

CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
))

def get_playlist_tracks(playlist_id):
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    tracks.extend(results['items'])

    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    
    return tracks

def extract_track_info(track_item):
    try:
        track = track_item.get('track') or {}
        return {
            "Track Name": track.get('name'),
            "Artists": ', '.join(artist['name'] for artist in track.get('artists', [])) if track.get('artists') else None,
            "Album": track.get('album', {}).get('name') if track.get('album') else None,
            "Duration (ms)": track.get('duration_ms'),
            "Popularity": track.get('popularity'),
            "Track URL": track.get('external_urls', {}).get('spotify') if track.get('external_urls') else None
        }
    except Exception as e:
        print(f"Error extracting track info: {e}")
        return {
            "Track Name": None,
            "Artists": None,
            "Album": None,
            "Duration (ms)": None,
            "Popularity": None,
            "Track URL": None
        }

def parse_playlist_id(url):
    match = re.search(r'playlist/([a-zA-Z0-9]+)', url)
    return match.group(1) if match else None

def parse_user_id(url):
    match = re.search(r'user/([a-zA-Z0-9]+)', url)
    return match.group(1) if match else None

def get_user_playlists(user_id):
    playlists = []
    results = sp.user_playlists(user_id)
    playlists.extend(results['items'])

    while results['next']:
        results = sp.next(results)
        playlists.extend(results['items'])
    
    return playlists

def sanitize_filename(name):
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    return ''.join(c for c in name if c in valid_chars).strip().replace(' ', '_')

def save_to_file(data, filename, save_xls=False):
    filename = sanitize_filename(filename)
    df = pd.DataFrame(data)
    df.to_csv(filename + '.csv', index=False, encoding='utf-8-sig')
    print(f"Saved to {filename}.csv")
    if save_xls:
        df.to_excel(filename + '.xlsx', index=False)
        print(f"Saved to {filename}.xlsx")

def main():
    if len(sys.argv) < 2:
        print("Usage: python spotisave.py <spotify_playlist_or_user_url> [-xls]")
        return

    url = sys.argv[1]
    save_xls = '-xls' in sys.argv

    if 'playlist' in url:
        playlist_id = parse_playlist_id(url)
        if not playlist_id:
            print("Invalid playlist URL.")
            return
        playlist = sp.playlist(playlist_id)
        playlist_name = playlist['name']
        print(f"Fetching playlist: {playlist_name}")
        tracks = get_playlist_tracks(playlist_id)
        data = [extract_track_info(t) for t in tracks]
        save_to_file(data, playlist_name, save_xls)

    elif 'user' in url:
        user_id = parse_user_id(url)
        if not user_id:
            print("Invalid user URL.")
            return
        print(f"Fetching playlists for user: {user_id}")
        playlists = get_user_playlists(user_id)

        folder_name = sanitize_filename(f"{user_id}'s spotify playlist data")
        os.makedirs(folder_name, exist_ok=True)
        os.chdir(folder_name)

        for pl in playlists:
            playlist_name = pl['name']
            print(f"Fetching: {playlist_name}")
            tracks = get_playlist_tracks(pl['id'])
            data = [extract_track_info(t) for t in tracks]
            filename = f"{playlist_name}"
            save_to_file(data, filename, save_xls)

    else:
        print("Unsupported URL type. Use a Spotify playlist or user link.")

if __name__ == "__main__":
    main()
