import os
import re
import string
import threading
import subprocess
import tempfile
import shutil
import logging
import requests
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import queue
import time

import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

# ---------------- Spotify setup ----------------

load_dotenv()
logging.getLogger("spotipy").setLevel(logging.CRITICAL)

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

# ---------------- Helpers ----------------

def parse_playlist_id(url):
    m = re.search(r"playlist/([a-zA-Z0-9]+)", url)
    return m.group(1) if m else None

def sanitize_filename(name):
    valid = f"-_.() {string.ascii_letters}{string.digits}"
    return "".join(c for c in name if c in valid).strip().replace(" ", "_")

def download_spotify_cover(track_uri, tmp):
    track_id = track_uri.split(":")[-1]
    track = sp.track(track_id)
    images = track["album"]["images"]
    if not images:
        return None
    path = os.path.join(tmp, "cover.jpg")
    r = requests.get(images[0]["url"], timeout=15)
    with open(path, "wb") as f:
        f.write(r.content)
    return path

def build_safe_filename(artist, title, ext):
    name = f"{artist} - {title}"
    name = name.replace(":", "_").replace("/", "_")
    name = "_".join(name.split())
    return f"{name}.{ext}"


# ---------------- GUI ----------------

class SpotiSaverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SpotiSaver")
        self.root.geometry("1000x600")
        self.root.resizable(True, True)
        self.log_queue = queue.Queue()
        self.last_exported_csv = None

        self.build_ui()

    # ---------- UI ----------

    def build_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=6)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        main = ttk.Frame(notebook)
        logs = ttk.Frame(notebook)

        notebook.add(main, text="Main")
        notebook.add(logs, text="Logs")

        self.build_logs_panel(logs)

        # Two columns
        self.left = ttk.Labelframe(main, text="Spotify → CSV", padding=10)
        self.right = ttk.Labelframe(main, text="CSV → Audio Downloader", padding=10)

        self.left.pack(side="left", fill="both", expand=True, padx=5)
        self.right.pack(side="right", fill="both", expand=True, padx=5)

        self.build_csv_saver()
        self.build_downloader()

    def build_logs_panel(self, parent):
        self.log_text = tk.Text(
            parent,
            state="disabled",
            wrap="word",
            height=20
        )
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

        scrollbar = ttk.Scrollbar(
            self.log_text,
            command=self.log_text.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

        self.root.after(100, self.flush_logs)
    
    # ---------- CSV SAVER ----------

    def build_csv_saver(self):
        self.playlist_entry = tk.Entry(self.left)
        self.playlist_entry.pack(fill="x", pady=4)

        tk.Button(
            self.left, text="Export Playlist to CSV",
            command=self.export_csv, height=2
        ).pack(pady=6)

        self.csv_status = tk.StringVar(value="Idle")
        tk.Label(self.left, textvariable=self.csv_status).pack(anchor="w")

        self.csv_progress = ttk.Progressbar(self.left, mode="determinate")
        self.csv_progress.pack(fill="x", pady=4)

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def get_default_output_dir(self):
        csv_dir = os.path.dirname(self.csv_path)
        csv_name = os.path.splitext(os.path.basename(self.csv_path))[0]
        default_dir = os.path.join(csv_dir, f"{csv_name}_download")
        os.makedirs(default_dir, exist_ok=True)
        return default_dir

    def flush_logs(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(100, self.flush_logs)


    def export_csv(self):
        url = self.playlist_entry.get().strip()
        pid = parse_playlist_id(url)
        if not pid:
            messagebox.showerror("Error", "Invalid playlist URL")
            return

        out = filedialog.askdirectory()
        if not out:
            return

        def task():
            try:
                playlist = sp.playlist(pid)
                tracks = []
                results = sp.playlist_tracks(pid)
                tracks.extend(results["items"])
                while results["next"]:
                    results = sp.next(results)
                    tracks.extend(results["items"])

                self.csv_progress["maximum"] = len(tracks)
                data = []

                for i, t in enumerate(tracks, 1):
                    tr = t["track"]
                    self.csv_status.set(f"Fetching track {i} / {len(tracks)}")

                    artists = tr["artists"]
                    genres = set()
                    for a in artists:
                        genres.update(sp.artist(a["id"])["genres"])

                    data.append({
                        "Track URI": tr["uri"],
                        "Track Name": tr["name"],
                        "Album Name": tr["album"]["name"],
                        "Artist Name(s)": ", ".join(a["name"] for a in artists),
                        "Release Date": tr["album"]["release_date"],
                        "Duration (ms)": tr["duration_ms"],
                        "Popularity": tr["popularity"],
                        "Explicit": tr["explicit"],
                        "Added By": t["added_by"]["id"],
                        "Added At": t["added_at"],
                        "Genres": ", ".join(genres),
                        "Record Label": tr["album"].get("label", ""),
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
                    })
                    self.csv_progress["value"] = i

                name = sanitize_filename(playlist["name"])
                path = os.path.join(out, f"{name}.csv")
                pd.DataFrame(data).to_csv(path, index=False, encoding="utf-8-sig")

                # Auto-load CSV into downloader
                self.last_exported_csv = path
                self.csv_path = path
                self.csv_label.config(text=os.path.basename(path), fg="black")

                messagebox.showinfo(
                    "Metadata Ready",
                    "Metadata downloaded in CSV and auto-loaded for download."
                )
                self.output_dir = None
                self.out_label.config(text="No folder selected", fg="gray")
                self.log(f"CSV exported and auto-loaded: {path}")
                self.csv_status.set(f"Completed ({len(tracks)} tracks)")
            finally:
                self.csv_progress["value"] = 0
                self.csv_status.set("Idle")

        threading.Thread(target=task, daemon=True).start()

    # ---------- DOWNLOADER ----------

    def build_downloader(self):
        self.csv_path = None
        self.output_dir = None
        self.stop_event = threading.Event()

        tk.Button(self.right, text="Import CSV", command=self.pick_csv).pack(fill="x")
        self.csv_label = tk.Label(self.right, text="No CSV selected", fg="gray")
        self.csv_label.pack(anchor="w", pady=2)

        tk.Button(self.right, text="Select Output Folder", command=self.pick_out).pack(fill="x", pady=(6,0))
        self.out_label = tk.Label(self.right, text="No folder selected", fg="gray")
        self.out_label.pack(anchor="w", pady=2)

        tk.Label(self.right, text="Format").pack(anchor="w", pady=(6,0))
        self.format_var = tk.StringVar(value="mp3")
        for f in ["mp3", "flac", "wav"]:
            tk.Radiobutton(self.right, text=f.upper(), variable=self.format_var, value=f,
                           command=self.toggle_bitrate).pack(anchor="w")

        self.bitrate_var = tk.StringVar(value="320")
        self.bitrate_box = ttk.Combobox(
            self.right, values=["128","160","192","256","320"],
            textvariable=self.bitrate_var, state="readonly"
        )
        self.bitrate_box.pack(anchor="w", pady=4)

        tk.Label(self.right, text="If file exists").pack(anchor="w", pady=(6,0))
        self.overwrite_var = tk.StringVar(value="skip")
        tk.Radiobutton(self.right, text="Skip", variable=self.overwrite_var, value="skip").pack(anchor="w")
        tk.Radiobutton(self.right, text="Overwrite", variable=self.overwrite_var, value="overwrite").pack(anchor="w")

        self.dl_status = tk.StringVar(value="Idle")
        tk.Label(self.right, textvariable=self.dl_status).pack(anchor="w", pady=4)

        self.dl_progress = ttk.Progressbar(self.right, mode="determinate")
        self.dl_progress.pack(fill="x", pady=4)

        btns = tk.Frame(self.right)
        btns.pack(pady=6)
        tk.Button(btns, text="Start", width=12, command=self.start_dl).pack(side="left", padx=4)
        tk.Button(btns, text="Stop", width=12, command=self.stop_dl).pack(side="left", padx=4)

        self.toggle_bitrate()

    def toggle_bitrate(self):
        if self.format_var.get() == "mp3":
            self.bitrate_box.configure(state="readonly")
        else:
            self.bitrate_box.configure(state="disabled")

    def pick_csv(self):
        p = filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if p:
            self.csv_path = p
            self.csv_label.config(text=os.path.basename(p), fg="black")
        self.output_dir = None
        self.out_label.config(text="No folder selected", fg="gray")

    def pick_out(self):
        p = filedialog.askdirectory()
        if p:
            self.output_dir = p
            self.out_label.config(text=p, fg="black")

    def start_dl(self):
        if not self.csv_path:
            messagebox.showerror("Error", "Select CSV first")
            return

        # Auto-create output folder if not selected
        if not self.output_dir:
            self.output_dir = self.get_default_output_dir()
            self.out_label.config(text=self.output_dir, fg="black")
            self.log(f"Output folder auto-created: {self.output_dir}")

        self.stop_event.clear()
        threading.Thread(target=self.run_dl, daemon=True).start()

    def stop_dl(self):
        self.stop_event.set()
        self.dl_status.set("Stopping…")

    def run_dl(self):
        df = pd.read_csv(self.csv_path)
        tracks = list(zip(df["Artist Name(s)"], df["Track Name"], df["Track URI"]))
        self.dl_progress["maximum"] = len(tracks)

        for i,(artist,title,uri) in enumerate(tracks,1):
            if self.stop_event.is_set():
                break
            self.dl_status.set(f"{i}/{len(tracks)} {title}")
            self.log(f"Downloading: {artist} - {title}")
            self.download_track(artist, title, uri)
            self.dl_progress["value"] = i

        self.dl_status.set("Done")
        self.dl_progress["value"] = 0

    def download_track(self, artist, title, uri):
        fmt = self.format_var.get()
        bitrate = self.bitrate_var.get()
        overwrite = self.overwrite_var.get()

        filename = build_safe_filename(artist, title, fmt)
        out = os.path.join(self.output_dir, filename)

        if overwrite == "skip" and os.path.exists(out):
            self.log(f"Skipped (exists): {filename}")
            return

        with tempfile.TemporaryDirectory() as tmp:
            cmd = [
                "yt-dlp",
                "--extractor-args","youtube:music",
                f"ytsearch1:{artist} - {title}",
                "-x","--audio-format",fmt,
                "-o",os.path.join(tmp,"audio.%(ext)s")
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            audio = next(f for f in os.listdir(tmp) if f.startswith("audio."))
            cover = download_spotify_cover(uri, tmp)

            ff = [
                "ffmpeg","-y",
                "-i",os.path.join(tmp,audio),
                "-i",cover,
                "-map","0:a","-map","1:v",
                "-c:a","copy","-c:v","mjpeg",
                "-metadata:s:v","title=Album cover",
                "-metadata:s:v","comment=Cover (front)"
            ]
            if fmt == "mp3":
                ff += ["-id3v2_version","3"]
            ff.append(out)
            subprocess.run(ff, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log(f"Finished: {artist} - {title}")


# ---------------- Run ----------------

if __name__ == "__main__":
    root = tk.Tk()
    app = SpotiSaverApp(root)
    root.mainloop()
