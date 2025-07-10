<p align="center">
  <img src="https://github.com/user-attachments/assets/e0fa1f38-f71b-496f-ac65-c08bf222382b" alt="Spotisave Banner" style="width:100%; max-height:220px; object-fit:cover;">
</p>

<h1 align="center">Spotisave</h1>

<p align="center">
  A command-line tool to download and backup public Spotify playlist metadata.
</p>

<p align="center">
  <a href="#"><img alt="Version" src="https://img.shields.io/badge/version-1.0.0-blue.svg"></a>
  <a href="#"><img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg"></a>
  <a href="#"><img alt="Python" src="https://img.shields.io/badge/python-3.7+-yellow.svg"></a>
</p>

---
**Spotisave** is a lightweight terminal-based tool that lets you download and back up metadata from any **public Spotify playlist** or all **public playlists of a Spotify user**.  
All data is saved in CSV format by default, with an option to export as Excel.

---

## ✨ Features

- 🎵 Extract track metadata (title, artists, album, popularity, etc.)
- 🧑‍💼 Download all public playlists of any Spotify user
- 📂 Saves each playlist as a CSV file (XLS optional)
- 🌐 Supports Unicode (Japanese, emojis, etc.)
- 🗂️ Creates a dedicated folder for each user’s playlists

---

## 🔧 Requirements

- Python 3.7 or higher
- Spotify Developer credentials
- `pip install -r requirements.txt`

---

## 🛠️ Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/spotisave.git
cd spotisave
```

### 2. Create a `.env` file in the root

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🚀 Usage

### ▶ Download a single playlist

```bash
python spotisave.py https://open.spotify.com/playlist/xxxxxxxxxx
```

### 👤 Download all playlists of a user

```bash
python spotisave.py https://open.spotify.com/user/xxxxxxxxxx
```

### ➕ Also export Excel (`.xlsx`) files

```bash
python spotisave.py <spotify_url> -xls
```

---

## 📁 Output Details

- Default format: `.csv` (Excel optional with `-xls`)
- Output files are named after playlist titles
- For user URLs, playlists are saved inside:
  ```
  <username>'s spotify playlist data/
  ```

---

## 🔐 Security Note

Keep your credentials private.

- ✅ Never commit `.env` to version control
- ✅ Use `.env.example` for sharing setup
- ✅ Add `.env` to `.gitignore`

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🤝 Credits

Built using:
- [Spotipy](https://github.com/plamere/spotipy)
- [Spotify Developer API](https://developer.spotify.com/documentation/web-api)
