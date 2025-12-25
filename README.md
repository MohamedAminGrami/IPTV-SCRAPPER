# IPTV Scraper

A powerful CLI tool to scrape and validate working IPTV links from public sources.

## Features

- 🔍 **Smart Search** - Find IPTV channels by name or get all available channels
- ✅ **Link Validation** - Tests each link to ensure it actually works with VLC and other players
- 📺 **M3U Format** - Saves links in standard M3U playlist format
- 🎨 **Colorful Output** - Easy-to-read terminal interface
- 📁 **Organized Storage** - Auto-creates dated folders for your playlists
- ⌨️ **CLI Arguments** - Use interactively or with command-line arguments

## Installation

### From Source

```bash
# Clone or download the repository
cd IPTV-SCRAPPER

# Install the package
pip install .
```

### Using pip (after publishing to PyPI)

```bash
pip install iptv-scraper
```

## Update

Keep your scraper up to date:

```bash
iptv-scraper --update
```

## Usage

### Interactive Mode

Simply run the command and follow the prompts:

```bash
iptv-scraper
```

### Command-Line Arguments

```bash
# Search for specific channel and get 5 working links
iptv-scraper -c "BBC" -n 5

# Get 10 links from all channels, auto-save without prompting
iptv-scraper -n 10 --auto-save

# Search and save with custom output name
iptv-scraper -c "News" -n 3 -o "news_channels"

# Get all available links (no filtering)
iptv-scraper -n 20

# Update the scraper
iptv-scraper --update
```

### For Tunisian Users

See [TUNISIA_GUIDE.md](TUNISIA_GUIDE.md) for specific examples:

```bash
# Find Tunisian channels
iptv-scraper -c tunisia -n 10

# Find Arabic channels
iptv-scraper -c arabic -n 15

# Find Bein Sports
iptv-scraper -c bein -n 10
```

### Arguments

- `-c, --channel` - Channel name to search for (optional)
- `--update` - Update IPTV Scraper to the latest version
- `-n, --number` - Number of working links to find
- `-o, --output` - Custom output filename (optional)
- `--auto-save` - Skip save confirmation prompt

## Examples

**Find 5 working news channels:**
```bash
iptv-scraper -c news -n 5
```

**Get 10 links and save automatically:**
```bash
iptv-scraper -n 10 --auto-save
```

**Search for sports channels:**
```bash
iptv-scraper -c sport -n 8 -o sports_playlist
```

## Output

- M3U playlists are saved in dated folders (e.g., `23-12-2025/`)
- Each file is timestamped to avoid overwrites
- Compatible with VLC, Kodi, and other media players

## Requirements

- Python 3.6+
- requests
- beautifulsoup4
- termcolor
- colorama
- art

## License

MIT License - Feel free to use and modify!

## Author

Developed by Musashi

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.
