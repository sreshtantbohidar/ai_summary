# OPEN2AIR

IPTV M3U Crawler + Web Player — crawls the internet for publicly available IPTV playlists, categorizes channels, verifies streams, and plays them in the browser.

## Features

- **Crawler** — Fetches M3U/M3U8 playlists from 60+ public sources (GitHub repos, community playlists)
- **Categorization** — Auto-categorizes channels into 15 types: News, Sports, Movies, Entertainment, Kids, Music, Documentary, Religious, Lifestyle, Education, Science & Tech, Business, Regional, International, Adult
- **Deduplication** — MD5 URL-based dedup ensures no duplicate channels
- **Stream Verification** — Concurrent partial-download testing to filter out dead streams
- **Web Player** — Full-featured browser player with HLS support, category sidebar, search, PiP, fullscreen

## Quick Start

### 1. Crawl & Build Playlist

```bash
# Basic crawl (fetches from all seed URLs)
python3 iptv_crawler.py

# Crawl + verify streams are working
python3 iptv_crawler.py --verify

# Faster: skip web discovery, only use seed URLs
python3 iptv_crawler.py --no-discover --verify

# Custom output
python3 iptv_crawler.py --output my_channels.m3u --json my_channels.json
```

### 2. Open the Player

```bash
# Start a local server
python3 -m http.server 8080
```

Open http://localhost:8080/iptv_player.html in your browser.

The player auto-loads `iptv_channels.json` from the same directory. You can also manually load any JSON or M3U file via the file picker.

## Files

| File | Description |
|------|-------------|
| `iptv_crawler.py` | Python crawler — fetches, parses, categorizes, verifies, and consolidates IPTV channels |
| `iptv_player.html` | Single-file web player — no build step, no dependencies, just open in browser |
| `iptv_channels.m3u` | Generated M3U playlist (output of crawler) |
| `iptv_channels.json` | Generated JSON index with all channels by category |

## Requirements

- **Crawler:** Python 3.10+ (stdlib only, no pip installs)
- **Player:** Any modern browser (Chrome/Firefox/Edge recommended for HLS.js support)

## Player Controls

| Key | Action |
|-----|--------|
| Space | Play / Pause |
| F | Fullscreen |
| M | Mute |
| Up/Down | Previous / Next channel |
| Esc | Exit fullscreen |

## Crawler Options

```
--output FILE          Output M3U file path (default: iptv_channels.m3u)
--json FILE            Output JSON index path (default: iptv_channels.json)
--no-discover         Skip web discovery phase (only use seed URLs)
--verify              Verify streams are accessible (partial download test)
--verify-workers N    Concurrent workers for verification (default: 20)
--verify-timeout S    Timeout per stream verification in seconds (default: 8)
--daemon              Run in daemon mode, periodically re-crawling
--interval SECONDS    Update interval for daemon mode (default: 3600)
--add-url URL         Add extra M3U playlist URL(s) to crawl
--list-categories     List all channel categories and exit
```

## License

MIT
