# 📺 IPTV Scraper

<p align="center">
  <img src="https://img.shields.io/badge/python-3.6+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/version-2.7.1-orange.svg" alt="Version">
</p>

A powerful and fast CLI tool to scrape and validate working IPTV links from public sources. Features smart channel search, parallel link testing, and automatic M3U playlist generation.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Smart Search** | Find channels by name with intelligent synonym matching |
| ⚡ **Blazing Fast** | 25 parallel workers with connection pooling for 5x speed |
| ✅ **Link Validation** | Tests each stream to ensure it actually works |
| 📺 **M3U Export** | Standard M3U playlist format compatible with VLC, Kodi, etc. |
| 🎯 **Live Match Mode** | Special mode for finding live sports streams |
| 📁 **Auto-Organization** | Creates dated folders for your playlists |
| 🛡️ **Auto-Save** | Ctrl+C saves progress - never lose your links |

## 🚀 Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/MohamedAminGrami/iptv-scraper.git
cd iptv-scraper

# Install the package
pip install .
```

### Quick Install

```bash
pip install -e .
```

## 📖 Usage

### Interactive Mode

```bash
iptv-scraper
# or use the short alias
ipsc
```

### Command-Line Arguments

```bash
# Search for specific channel
iptv-scraper -c "BBC" -n 5

# Auto-save without prompting
iptv-scraper -c "sports" -n 10 --auto-save

# Custom output filename
iptv-scraper -c "news" -n 5 -o "my_news_channels"

# Live sports match mode
iptv-scraper --live-match -n 10

# View all popular searchable channels
iptv-scraper --popular-channels
```

### Available Arguments

| Argument | Description |
|----------|-------------|
| `-c, --channel` | Channel name to search for |
| `-n, --number` | Number of working links to find |
| `-o, --output` | Custom output filename |
| `--auto-save` | Skip save confirmation prompt |
| `--live-match` | Search live sports streaming sites |
| `--popular-channels` | Display popular searchable channels |
| `--update` | Update to the latest version |

## 🎯 Search Examples

```bash
# Sports channels
iptv-scraper -c "bein sports" -n 10
iptv-scraper -c "espn" -n 5
iptv-scraper -c "sky sports" -n 8

# News channels
iptv-scraper -c "cnn" -n 5
iptv-scraper -c "bbc news" -n 5

# Regional channels
iptv-scraper -c "arabic" -n 15
iptv-scraper -c "french" -n 10

# Entertainment
iptv-scraper -c "movie" -n 10
iptv-scraper -c "cartoon" -n 8
```

## 📊 Performance

| Metric | Value |
|--------|-------|
| Parallel Workers | 25 |
| Connection Pool | 50 connections |
| Avg. Speed | ~30-60 seconds for 10 channels |
| Link Validation | Full stream verification |

## 📁 Output Structure

```
📂 your-folder/
├── 📂 25-12-2024/
│   ├── 📄 10-30-45-AM SPORTS.m3u
│   └── 📄 02-15-30-PM NEWS.m3u
└── 📂 26-12-2024/
    └── 📄 09-00-00-AM BEIN.m3u
```

## 🔧 Requirements

- Python 3.6+
- beautifulsoup4
- requests
- termcolor
- colorama
- art

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for educational purposes only. The developers are not responsible for any misuse of this software. Please ensure you have the right to access any streams you find.

## 🤝 Contributing

Contributions are welcome! Feel free to submit a Pull Request.

---

<p align="center">Made with ❤️ by Musashi</p>
