import os
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd

import requests
import tempfile
import shutil

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import logging

load_dotenv()
logging.getLogger("spotipy").setLevel(logging.CRITICAL)

sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        cache_handler=None
    )
)

def download_spotify_cover(track_uri, temp_dir):
    track_id = track_uri.split(":")[-1]
    track = sp.track(track_id)

    images = track["album"]["images"]
    if not images:
        return None

    cover_url = images[0]["url"]  # highest resolution
    cover_path = os.path.join(temp_dir, "cover.jpg")

    r = requests.get(cover_url, timeout=15)
    with open(cover_path, "wb") as f:
        f.write(r.content)

    return cover_path



# ---------------- GUI ----------------

class DownloaderGUI:
    def __init__(self, root):

        self.root = root
        self.root.title("CSV Audio Downloader (yt-dlp)")
        self.root.geometry("600x520")
        self.root.resizable(False, True)

        self.csv_path = None
        self.output_dir = None
        self.stop_event = threading.Event()
        self.worker_thread = None

        frame = tk.Frame(root, padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        # CSV
        tk.Button(frame, text="Import CSV", command=self.load_csv).pack(anchor="w")
        self.csv_label = tk.Label(frame, text="No CSV selected", fg="gray")
        self.csv_label.pack(anchor="w", pady=4)

        # Output folder
        tk.Button(frame, text="Select Output Folder", command=self.select_output).pack(anchor="w", pady=(10, 0))
        self.out_label = tk.Label(frame, text="No folder selected", fg="gray")
        self.out_label.pack(anchor="w", pady=4)

        # Format
        tk.Label(frame, text="Audio Format").pack(anchor="w", pady=(12, 2))
        self.format_var = tk.StringVar(value="mp3")
        for text, val in [("MP3", "mp3"), ("FLAC", "flac"), ("WAV", "wav")]:
            tk.Radiobutton(frame, text=text, variable=self.format_var, value=val).pack(anchor="w")

        # MP3 bitrate
        self.bitrate_frame = tk.Frame(frame)
        self.bitrate_frame.pack(anchor="w", pady=(6, 0))
        # Overwrite / Skip option
        tk.Label(frame, text="If file exists").pack(anchor="w", pady=(10, 2))
        self.overwrite_var = tk.StringVar(value="skip")

        tk.Radiobutton(frame, text="Skip existing", variable=self.overwrite_var, value="skip").pack(anchor="w")
        tk.Radiobutton(frame, text="Overwrite", variable=self.overwrite_var, value="overwrite").pack(anchor="w")

        tk.Label(self.bitrate_frame, text="MP3 Bitrate").pack(side="left")
        self.bitrate_var = tk.StringVar(value="320")
        ttk.Combobox(
            self.bitrate_frame,
            values=["128", "160", "192", "256", "320"],
            width=6,
            textvariable=self.bitrate_var,
            state="readonly"
        ).pack(side="left", padx=6)

        # Status + progress
        self.status = tk.StringVar(value="Idle")
        tk.Label(frame, textvariable=self.status, fg="gray").pack(anchor="w", pady=(10, 0))

        self.progress = ttk.Progressbar(frame, orient="horizontal", length=560, mode="determinate")
        self.progress.pack(pady=6)

        # Buttons
        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=10)

        self.start_btn = tk.Button(btn_frame, text="Start Download", width=18, height=2, command=self.start)
        self.start_btn.pack(side="left", padx=6)

        self.stop_btn = tk.Button(btn_frame, text="Stop / Cancel", width=18, height=2, command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=6)

        self.root.update_idletasks()

    # -------- GUI actions --------

    def load_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            self.csv_path = path
            self.csv_label.config(text=os.path.basename(path), fg="black")

    def select_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir = path
            self.out_label.config(text=path, fg="black")

    def start(self):
        if not self.csv_path or not self.output_dir:
            messagebox.showerror("Error", "Select CSV and output folder")
            return

        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        self.worker_thread = threading.Thread(target=self.run_downloads, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.stop_event.set()
        self.status.set("Stopping after current track…")

    # -------- Core logic --------

    def run_downloads(self):
        try:
            df = pd.read_csv(self.csv_path)
            if not {"Track Name", "Artist Name(s)"}.issubset(df.columns):
                raise RuntimeError("CSV missing required columns")

            tracks = list(zip(
                df["Artist Name(s)"],
                df["Track Name"],
                df["Track URI"]
            ))

            total = len(tracks)

            self.progress["maximum"] = total
            self.progress["value"] = 0

            fmt = self.format_var.get()
            bitrate = self.bitrate_var.get()

            overwrite_mode = self.overwrite_var.get()

            for i, (artist, title, track_uri) in enumerate(tracks, start=1):
                if self.stop_event.is_set():
                    self.status.set("Cancelled")
                    break

                query = f"{artist} - {title}"
                self.status.set(f"Downloading {i}/{total}: {title}")

                self.download_track(query, track_uri, fmt, bitrate, overwrite_mode)

                self.progress["value"] = i

            if not self.stop_event.is_set():
                self.status.set("Done")
                messagebox.showinfo("Finished", "All downloads completed")

        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error")
        finally:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.progress["value"] = 0
            self.stop_event.clear()

    def download_track(self, query, track_uri, fmt, bitrate, overwrite_mode):

        safe_name = f"{query}.{fmt}".replace("/", "_")
        final_path = os.path.join(self.output_dir, safe_name)

        if overwrite_mode == "skip" and os.path.exists(final_path):
            return

        with tempfile.TemporaryDirectory() as tmp:
            # 1. Download audio (NO thumbnail)
            audio_out = os.path.join(tmp, "audio.%(ext)s")

            cmd = [
                "yt-dlp",
                "--extractor-args", "youtube:music",
                f"ytsearch1:{query}",
                "-x",
                "--add-metadata",
                "-o", audio_out
            ]

            if fmt == "mp3":
                cmd += ["--audio-format", "mp3", "--audio-quality", "0"]
            else:
                cmd += ["--audio-format", fmt]

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Find downloaded file
            audio_file = next(
                f for f in os.listdir(tmp)
                if f.startswith("audio.")
            )
            audio_path = os.path.join(tmp, audio_file)

            # 2. Download Spotify cover
            cover_path = download_spotify_cover(track_uri, tmp)
            if not cover_path:
                shutil.copy(audio_path, self.output_dir)
                return
            
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-i", audio_path,
                "-i", cover_path,
                "-map", "0:a",
                "-map", "1:v",
                "-c:a", "copy",
                "-c:v", "mjpeg",
                "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)",
            ]
            
            if fmt == "mp3":
                ffmpeg_cmd += ["-id3v2_version", "3"]
            
            ffmpeg_cmd.append(final_path)
            
            subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)



# ---------------- Run ----------------

if __name__ == "__main__":
    root = tk.Tk()
    app = DownloaderGUI(root)
    root.mainloop()
