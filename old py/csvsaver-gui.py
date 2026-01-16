import re
import os
import string
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk


import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

import logging
logging.getLogger("spotipy").setLevel(logging.CRITICAL)

# ------------------ Spotify setup ------------------

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set")

sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        cache_handler=None
    )
)

# ------------------ Helpers ------------------

def parse_playlist_id(url):
    match = re.search(r"playlist/([a-zA-Z0-9]+)", url)
    return match.group(1) if match else None

def sanitize_filename(name):
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    return "".join(c for c in name if c in valid_chars).strip().replace(" ", "_")

def get_playlist_tracks(playlist_id):
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    tracks.extend(results["items"])

    while results["next"]:
        results = sp.next(results)
        tracks.extend(results["items"])

    return tracks

def extract_track_info(track_item):
    track = track_item.get("track") or {}
    if not track:
        return {}

    album = track.get("album", {})
    artists = track.get("artists", [])

    # Genres (merged from all artists)
    genres = set()
    for artist in artists:
        artist_data = sp.artist(artist["id"])
        genres.update(artist_data.get("genres", []))

    return {
        "Track URI": track.get("uri"),
        "Track Name": track.get("name"),
        "Album Name": album.get("name"),
        "Artist Name(s)": ", ".join(a["name"] for a in artists),
        "Release Date": album.get("release_date"),
        "Duration (ms)": track.get("duration_ms"),
        "Popularity": track.get("popularity"),
        "Explicit": track.get("explicit"),
        "Added By": track_item.get("added_by", {}).get("id"),
        "Added At": track_item.get("added_at"),
        "Genres": ", ".join(genres),
        "Record Label": album.get("label"),

        # Spotify audio-features are blocked → force zero
        "Danceability": 0,
        "Energy": 0,
        "Key": 0,
        "Loudness": 0,
        "Mode": 0,
        "Speechiness": 0,
        "Acousticness": 0,
        "Instrumentalness": 0,
        "Liveness": 0,
        "Valence": 0,
        "Tempo": 0,
        "Time Signature": 0,
    }

def save_csv(data, playlist_name, folder):
    filename = sanitize_filename(playlist_name) + ".csv"
    path = os.path.join(folder, filename)
    df = pd.DataFrame(data)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path

# ------------------ GUI logic ------------------

def run_export():
    url = entry.get().strip()
    if not url:
        messagebox.showerror("Error", "Please enter a Spotify playlist URL")
        return

    playlist_id = parse_playlist_id(url)
    if not playlist_id:
        messagebox.showerror("Error", "Invalid Spotify playlist URL")
        return

    output_dir = filedialog.askdirectory(title="Select output folder")
    if not output_dir:
        return

    status.set("Fetching playlist…")
    export_button.config(state="disabled")

    def task():
        try:
            playlist = sp.playlist(playlist_id)
            playlist_name = playlist["name"]

            tracks = get_playlist_tracks(playlist_id)
            total = len(tracks)

            progress["maximum"] = total
            progress["value"] = 0

            data = []

            for i, t in enumerate(tracks, start=1):
                data.append(extract_track_info(t))
                progress["value"] = i
                status.set(f"Processing tracks: {i}/{total}")

            csv_path = save_csv(data, playlist_name, output_dir)



            status.set("Done")
            messagebox.showinfo(
                "Success",
                f"Playlist exported successfully:\n\n{csv_path}"
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
            status.set("Error")
        finally:
            export_button.config(state="normal")
            progress["value"] = 0


    threading.Thread(target=task, daemon=True).start()

# ------------------ GUI ------------------

root = tk.Tk()
root.title("SpotiSave – Playlist to CSV")
root.geometry("520x180")
root.resizable(False, False)

frame = tk.Frame(root, padx=12, pady=12)
frame.pack(fill="both", expand=True)

tk.Label(frame, text="Spotify Playlist URL").pack(anchor="w")
entry = tk.Entry(frame, width=70)
entry.pack(pady=6)

export_button = tk.Button(
    frame,
    text="Export to CSV",
    command=run_export,
    height=2
)
export_button.pack(pady=8)

progress = ttk.Progressbar(
    frame,
    orient="horizontal",
    length=480,
    mode="determinate"
)
progress.pack(pady=6)


status = tk.StringVar(value="Idle")
tk.Label(frame, textvariable=status, fg="gray").pack(anchor="w")

root.mainloop()
