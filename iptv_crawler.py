
#!/usr/bin/env python3
"""
IPTV M3U/M3u8 Crawler & Consolidator
======================================
Searches the internet for publicly available M3U/M3U8 IPTV playlists,
parses and categorizes channels by type, deduplicates them, and outputs
a single consolidated M3U file.

Usage:
    python3 iptv_crawler.py [--output channels.m3u] [--update-interval 3600]

Requirements: Python 3.10+ (stdlib only — no pip install needed)
"""

import re
import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import ipaddress
from datetime import datetime, timezone
from html.parser import HTMLParser
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT = "iptv_channels.m3u"
DEFAULT_JSON_OUTPUT = "iptv_channels.json"
REQUEST_TIMEOUT = 15          # seconds per HTTP request
MAX_REDIRECTS = 5
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Known public M3U/M3U8 playlist URLs and aggregator pages
# These are well-known public repositories that host free IPTV playlists
SEED_URLS = [
    # GitHub raw playlist repos (public, free)
    "https://raw.githubusercontent.com/iptv-org/iptv/master/index.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/index.m3u",
    # Free-IPTV aggregator
    "https://raw.githubusercontent.com/Free-IPTV/Free-IPTV/master/playlist.m3u",
    # Public playlist mirrors
    "https://raw.githubusercontent.com/jnk22/kodinerds-iptv/master/iptv/iptv-m3u/kodinerds.m3u",
    "https://raw.githubusercontent.com/EmilianoHE/SOMOS-FREE-IPTV/master/SOMOS-FREE-IPTV.m3u",
    "https://raw.githubusercontent.com/botallen/repository.github.io/master/m3u/playlist.m3u",
    # Additional community playlists
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/af.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/al.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/dz.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ar.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/au.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/at.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/be.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/br.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ca.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cl.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/co.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/hr.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cz.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/dk.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/eg.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/fi.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/fr.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/de.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/gr.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/hk.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/hu.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/in.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/id.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ie.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/il.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/it.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/jp.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/kr.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/my.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/mx.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/nl.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/nz.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/no.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/pk.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ph.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/pl.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/pt.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ro.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ru.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/sa.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/sg.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/za.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/es.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/se.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ch.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/tr.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ua.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ae.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/gb.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/us.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ve.m3u",
]

# Pages that list / link to M3U playlists (we crawl these for more URLs)
DISCOVERY_PAGES = [
    "https://github.com/iptv-org/iptv",
    "https://github.com/search?q=m3u+iptv+playlist&type=repositories",
    "https://www.reddit.com/r/IPTV/",
    "https://www.reddit.com/r/iptvresellers/",
]

# ---------------------------------------------------------------------------
# Channel categorization rules
# ---------------------------------------------------------------------------

# Each rule: (category_name, list_of_keywords)
# Keywords are matched case-insensitively against channel name / group-title
CATEGORY_RULES = [
    ("News", [
        "news", "cnn", "bbc", "al jazeera", "fox news", "msnbc", "sky news",
        "france 24", "dw", "rt", "cnbc", "bloomberg", "reuters", "abc news",
        "cbs news", "nbc news", "pbs", "newsmax", "oann", "news12", "ndtv",
        "times now", "republic", "wion", "trt world", "nhk world", "cgtn",
        "press tv", "i24", "euronews", "sky news", "gb news", "itv news",
        "channel 4 news", "tagesschau", "n-tv", "rtl news", "sat.1 news",
        "prosieben news", "abc", "cbs", "nbc", "fox", "pbs", "cw",
    ]),
    ("Sports", [
        "sport", "espn", "fox sports", "nbc sports", "cbs sports", "sky sports",
        "bt sport", "bein", "dazn", "nfl", "nba", "mlb", "nhl", "fifa",
        "uefa", "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
        "champions league", "europa league", "formula 1", "f1", "moto gp",
        "wwe", "ufc", "boxing", "tennis", "golf", "cricket", "rugby", "ncaaf",
        "ncaam", "espn+", "tbs sports", "tnt sports", "mlb network",
        "nfl network", "nba tv", "golf channel", "tennis channel",
        "sport tv", "eleven sports", "viaplay", "setant", "arena sport",
        "supersport", "star sports", "sony sports", "willow", "willow cricket",
        "ten sports", "a sports", "geo super", "ptv sports",
    ]),
    ("Movies", [
        "movie", "cinema", "film", "hbo", "showtime", "starz", "cinemax",
        "amc", "tcm", "fxm", "sony movie", "movie plex", "film4", "movies",
        "warner", "universal", "paramount", "disney", "pixar", "dreamworks",
        "fox movie", "mgm", "liongate", "netflix", "prime video", "appletv",
        "hulu", "peacock", "tubi", "crackle", "popcorn", "flix",
    ]),
    ("Entertainment", [
        "entertainment", "tv", "series", "drama", "comedy", "sitcom",
        "abc", "nbc", "cbs", "fox", "cw", "tnt", "tbs", "usa network",
        "bravo", "e!", "oxygen", "oxygen", "lifetime", "hallmark", "freeform",
        "fx", "fxx", "amc", "ifc", "sundance", "bbc one", "bbc two", "itv",
        "channel 4", "channel 5", "sky one", "sky atlantic", "sky witness",
        "rtl", "sat.1", "prosieben", "zdf", "ard", "arte", "tf1", "france 2",
        "france 3", "canal+", "m6", "d8", "w9", "nrj", "cherie 25",
    ]),
    ("Kids", [
        "kids", "children", "cartoon", "disney", "nickelodeon", "nick jr",
        "cartoon network", "boomerang", "baby tv", "disney junior",
        "disney xd", "pbs kids", "cbeebies", "cbbc", "pop", "tiny pop",
        "boing", "gulli", "tiiji", "canal j", "m6 kid", "kidz",
        "toonami", "anime", "naruto", "pokemon", "yoyo", "minimax",
        "duck tv", "baby first", "kids zone", "kids tv",
    ]),
    ("Music", [
        "music", "mtv", "vh1", "bet", "cmt", "gac", "vevo", "music choice",
        "mtv live", "mtv hits", "mtv classic", "club mtv", "mtv 80s",
        "mtv 90s", "kerrang", "kiss", "magic", "the box", "4music",
        "trace", "trace urban", "trace tropical", "trace africa",
        "mezzo", "mezzo live", "stingray", "qmusic", "radio",
    ]),
    ("Documentary", [
        "documentary", "discovery", "national geographic", "nat geo",
        "history", "history channel", "a&e", "crime", "investigation",
        "id", "science channel", "animal planet", "planet earth",
        "bbc earth", "nova", "pbs nature", "love animal", "travel",
        "travel channel", "food network", "cooking", "hgtv", "diy",
        "home garden", "dmax", "quest", "really", "yesterday",
        "smithsonian", "curiosity", "docubay", "docu",
    ]),
    ("Religious", [
        "religion", "church", "gospel", "christian", "islam", "muslim",
        "quran", "bible", "faith", "trinity", "tbn", "god tv", "eWTN",
        "3abn", "hope channel", "llbn", "al karama", "alsaadat",
        "huda tv", "peace tv", "iqra", "madani", "sunnah", "hidayah",
        "temple", "synagogue", "buddhist", "hindu", "sikh",
    ]),
    ("Lifestyle", [
        "lifestyle", "fashion", "cooking", "food", "travel", "home",
        "diy", "hgtv", "food network", "cooking channel", "tlc",
        "fashion tv", "fashion one", "e! entertainment", "e! news",
        "vanity fair", "vogue", "gq", "elle", "bazaar",
    ]),
    ("Education", [
        "education", "learn", "university", "college", "academic",
        "khan academy", "crash course", "ted", "tedx", "edx",
        "coursera", "udemy", "skillshare", "masterclass",
        "nova", "pbs", "bbc learn", "open university",
    ]),
    ("Science & Tech", [
        "science", "technology", "tech", "space", "nasa", "spacex",
        "engineering", "mechanical", "electrical", "computer",
        "coding", "programming", "ai", "robotics", "gadget",
        "techcrunch", "wired", "verge", "engadget",
    ]),
    ("Business", [
        "business", "finance", "stock", "market", "money", "economy",
        "cnbc", "bloomberg", "fox business", "yahoo finance",
        "wall street", "nasdaq", "dow jones", "ft", "financial",
        "forbes", "fortune", "economist", "business insider",
    ]),
    ("Regional", [
        "regional", "local", "community", "state", "province",
        "county", "city", "municipal", "civic",
    ]),
    ("International", [
        "international", "global", "world", "overseas", "foreign",
        "expat", "diaspora",
    ]),
    ("Adult", [
        "xxx", "adult", "porn", "erotic", "sex", "playboy",
        "hustler", "brazzers", "reality kings", "naughty",
    ]),
]

# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------

class HTTPClient:
    """Simple HTTP client using only stdlib."""

    def __init__(self, timeout=REQUEST_TIMEOUT):
        self.timeout = timeout

    def fetch(self, url, headers=None):
        """Fetch URL content. Returns (status_code, content_bytes, final_url)."""
        hdrs = {"User-Agent": USER_AGENT}
        if headers:
            hdrs.update(headers)

        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
                return resp.status, data, resp.url
        except urllib.error.HTTPError as e:
            return e.code, b"", url
        except Exception:
            return 0, b"", url

    def fetch_text(self, url, encoding="utf-8", errors="replace"):
        """Fetch and decode text content."""
        status, data, final_url = self.fetch(url)
        if status >= 200 and status < 400 and data:
            return status, data.decode(encoding, errors=errors), final_url
        return status, "", final_url


class LinkExtractor(HTMLParser):
    """Extract all href links from an HTML page."""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in ("a", "link"):
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def is_private_ip(url):
    """Check if URL points to a private/internal IP (SSRF protection)."""
    try:
        hostname = urllib.parse.urlparse(url).hostname
        if not hostname:
            return True
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_reserved
    except ValueError:
        return False


def resolve_url(base, link):
    """Resolve a relative link against a base URL."""
    return urllib.parse.urljoin(base, link)

def verify_stream(url, timeout=8, max_bytes=8192):
    """
    Verify a stream URL is accessible by doing a partial download.
    Returns (is_working: bool, status_code: int, bytes_received: int).
    """
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(max_bytes)
            return True, resp.status, len(data)
    except urllib.error.HTTPError as e:
        return False, e.code, 0
    except Exception:
        return False, 0, 0


def verify_channel(channel, timeout=8):
    """Verify a single channel's stream URL. Returns (channel, is_working)."""
    is_working, status, nbytes = verify_stream(channel.url, timeout=timeout)
    return channel, is_working, status, nbytes



# ---------------------------------------------------------------------------
# M3U Parser
# ---------------------------------------------------------------------------

class M3UChannel:
    """Represents a single IPTV channel entry."""

    def __init__(self):
        self.name = ""
        self.url = ""
        self.group = ""
        self.logo = ""
        self.tvg_id = ""
        self.tvg_name = ""
        self.tvg_country = ""
        self.attrs = {}       # raw #EXTINF attributes
        self.source = ""      # which playlist file this came from

    @property
    def uid(self):
        """Unique identifier for dedup: hash of URL."""
        return hashlib.md5(self.url.strip().lower().encode()).hexdigest()

    def category(self):
        """Determine channel category from name, group, and attributes."""
        text = f"{self.name} {self.group} {self.tvg_name} {self.tvg_id}".lower()

        for cat_name, keywords in CATEGORY_RULES:
            for kw in keywords:
                if kw in text:
                    return cat_name

        return "Uncategorized"

    def to_m3u_line(self):
        """Render this channel as M3U #EXTINF + URL lines."""
        attrs = []
        if self.tvg_id:
            attrs.append(f'tvg-id="{self.tvg_id}"')
        if self.tvg_name:
            attrs.append(f'tvg-name="{self.tvg_name}"')
        if self.logo:
            attrs.append(f'tvg-logo="{self.logo}"')
        if self.group:
            attrs.append(f'group-title="{self.group}"')
        if self.tvg_country:
            attrs.append(f'tvg-country="{self.tvg_country}"')

        # Add any other raw attrs
        for k, v in self.attrs.items():
            if k not in ("tvg-id", "tvg-name", "tvg-logo", "group-title", "tvg-country"):
                attrs.append(f'{k}="{v}"')

        attr_str = " ".join(attrs)
        extinf = f"#EXTINF:-1 {attr_str},{self.name}" if attr_str else f"#EXTINF:-1,{self.name}"
        return f"{extinf}\n{self.url}"


def parse_m3u(content, source_url=""):
    """
    Parse M3U/M3U8 content and return list of M3UChannel objects.
    Handles standard #EXTINF lines followed by URL lines.
    """
    channels = []
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("#EXTINF:"):
            channel = M3UChannel()
            channel.source = source_url

            # Parse #EXTINF attributes
            # Format: #EXTINF:-1 tvg-id="..." tvg-name="..." ...,Channel Name
            extinf = line

            # Extract channel name (after the last comma)
            comma_idx = extinf.rfind(",")
            if comma_idx != -1:
                channel.name = extinf[comma_idx + 1:].strip()
                attr_part = extinf[:comma_idx]
            else:
                attr_part = extinf

            # Parse key="value" attributes
            attr_pattern = re.compile(r'(\w+(?:-\w+)*)="([^"]*)"')
            for match in attr_pattern.finditer(attr_part):
                key, value = match.group(1), match.group(2)
                channel.attrs[key] = value
                if key == "tvg-id":
                    channel.tvg_id = value
                elif key == "tvg-name":
                    channel.tvg_name = value
                elif key == "tvg-logo":
                    channel.logo = value
                elif key == "group-title":
                    channel.group = value
                elif key == "tvg-country":
                    channel.tvg_country = value

            # Next non-empty, non-comment line is the URL
            i += 1
            while i < len(lines):
                url_line = lines[i].strip()
                if url_line and not url_line.startswith("#"):
                    channel.url = url_line
                    break
                i += 1

            if channel.url and (channel.url.startswith("http://") or
                                channel.url.startswith("https://") or
                                channel.url.startswith("rtmp://") or
                                channel.url.startswith("rtsp://") or
                                channel.url.startswith("mms://")):
                channels.append(channel)

        i += 1

    return channels


# ---------------------------------------------------------------------------
# Discovery: find more M3U URLs from web pages
# ---------------------------------------------------------------------------

def discover_m3u_urls(http, page_url, visited=None):
    """Crawl a page looking for .m3u / .m3u8 links."""
    if visited is None:
        visited = set()

    if page_url in visited:
        return []
    visited.add(page_url)

    found_urls = []
    status, text, final_url = http.fetch_text(page_url)

    if status < 200 or status >= 400:
        return found_urls

    # Extract links from HTML
    parser = LinkExtractor()
    try:
        parser.feed(text)
    except Exception:
        pass

    for link in parser.links:
        absolute = resolve_url(final_url, link)
        lower = absolute.lower()

        if lower.endswith(".m3u") or lower.endswith(".m3u8") or ".m3u?" in lower:
            if not is_private_ip(absolute):
                found_urls.append(absolute)

    # Also search raw text for m3u URLs
    url_pattern = re.compile(
        r'https?://[^\s<>"\']+?\.m3u8?[^\s<>"\']*',
        re.IGNORECASE
    )
    for match in url_pattern.finditer(text):
        url = match.group(0).rstrip(".,;:!?)\"'")
        if not is_private_ip(url):
            found_urls.append(url)

    return list(set(found_urls))


# ---------------------------------------------------------------------------
# Main Crawler
# ---------------------------------------------------------------------------

class IPTVCrawler:
    """Main crawler that fetches, parses, categorizes, and consolidates IPTV channels."""

    def __init__(self, output_file=DEFAULT_OUTPUT, json_file=DEFAULT_JSON_OUTPUT):
        self.output_file = output_file
        self.json_file = json_file
        self.http = HTTPClient()
        self.channels = []           # list of M3UChannel
        self.seen_urls = set()       # for dedup
        self.stats = defaultdict(int)

    def fetch_playlist(self, url):
        """Fetch and parse a single M3U playlist URL."""
        print(f"  Fetching: {url[:100]}...")
        status, text, final_url = self.http.fetch_text(url)

        if status < 200 or status >= 400:
            print(f"    -> HTTP {status}, skipping")
            self.stats["failed_fetches"] += 1
            return []

        if not text.strip().startswith("#EXTM3U") and "#EXTINF" not in text:
            print(f"    -> Not a valid M3U file, skipping")
            self.stats["invalid_files"] += 1
            return []

        channels = parse_m3u(text, source_url=url)
        print(f"    -> Found {len(channels)} channels")
        self.stats["successful_fetches"] += 1
        return channels

    def add_channels(self, channels):
        """Add channels with deduplication."""
        added = 0
        duped = 0
        for ch in channels:
            uid = ch.uid
            if uid not in self.seen_urls:
                self.seen_urls.add(uid)
                self.channels.append(ch)
                added += 1
            else:
                duped += 1
        self.stats["duplicates_removed"] += duped
        return added

    def verify_all_channels(self, max_workers=20, timeout=8):
        """
        Verify all channels using concurrent partial downloads.
        Removes channels that don't respond successfully.
        Returns (working_count, dead_count).
        """
        print()
        print("=" * 60)
        print(f"Verifying {len(self.channels)} channels ({max_workers} concurrent workers)...")
        print("=" * 60)

        working = []
        dead = 0
        total = len(self.channels)
        checked = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ch = {
                executor.submit(verify_channel, ch, timeout): ch
                for ch in self.channels
            }

            for future in as_completed(future_to_ch):
                checked += 1
                try:
                    ch, is_working, status, nbytes = future.result()
                    if is_working:
                        working.append(ch)
                    else:
                        dead += 1
                        if dead % 50 == 0 or dead <= 5:
                            print(f"  [{checked}/{total}] DEAD ({status}): {ch.name[:60]}")
                except Exception:
                    dead += 1

                if checked % 200 == 0:
                    print(f"  Progress: {checked}/{total} checked, {len(working)} working, {dead} dead")

        self.channels = working
        self.stats["channels_verified"] = checked
        self.stats["channels_working"] = len(working)
        self.stats["channels_dead"] = dead

        print(f"\nVerification complete: {len(working)} working, {dead} dead (out of {total})")
        return len(working), dead

    def crawl(self, seed_urls=None, discover=True):
        """Main crawl loop."""
        if seed_urls is None:
            seed_urls = SEED_URLS

        all_urls = list(seed_urls)
        visited_urls = set()

        # Phase 1: Fetch all seed playlists
        print("=" * 60)
        print("Phase 1: Fetching seed playlists")
        print("=" * 60)

        for url in all_urls:
            if url in visited_urls:
                continue
            visited_urls.add(url)

            if is_private_ip(url):
                print(f"  Skipping private URL: {url}")
                continue

            channels = self.fetch_playlist(url)
            added = self.add_channels(channels)
            print(f"    -> Added {added} new channels (total: {len(self.channels)})")

        # Phase 2: Discovery — crawl pages for more M3U links
        if discover:
            print()
            print("=" * 60)
            print("Phase 2: Discovering more playlists from web pages")
            print("=" * 60)

            for page_url in DISCOVERY_PAGES:
                print(f"  Crawling: {page_url}")
                try:
                    found = discover_m3u_urls(self.http, page_url, visited_urls)
                    print(f"    -> Found {len(found)} M3U links")

                    for m3u_url in found[:20]:  # limit per page
                        if m3u_url in visited_urls:
                            continue
                        visited_urls.add(m3u_url)
                        channels = self.fetch_playlist(m3u_url)
                        added = self.add_channels(channels)
                        print(f"    -> Added {added} new channels (total: {len(self.channels)})")
                except Exception as e:
                    print(f"    -> Error: {e}")

        return len(self.channels)

    def categorize(self):
        """Group channels by category."""
        categories = defaultdict(list)
        for ch in self.channels:
            cat = ch.category()
            categories[cat].append(ch)
        return categories

    def save_m3u(self, categories):
        """Save consolidated M3U file, organized by category."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"# Generated by IPTV Crawler on {now}\n")
            f.write(f"# Total channels: {len(self.channels)}\n")
            f.write(f"# Categories: {len(categories)}\n\n")

            # Sort categories: put common ones first
            priority = ["News", "Sports", "Movies", "Entertainment", "Kids",
                        "Music", "Documentary", "Science & Tech", "Business",
                        "Lifestyle", "Education", "Religious", "Regional",
                        "International", "Adult", "Uncategorized"]

            ordered = []
            for cat in priority:
                if cat in categories:
                    ordered.append(cat)
            for cat in sorted(categories.keys()):
                if cat not in ordered:
                    ordered.append(cat)

            for cat_name in ordered:
                channels = categories[cat_name]
                f.write(f"\n# ===== {cat_name} ({len(channels)} channels) =====\n\n")

                for ch in channels:
                    # Ensure group-title is set to category
                    ch.group = cat_name
                    f.write(ch.to_m3u_line() + "\n")

        print(f"\nSaved M3U file: {self.output_file}")

    def save_json(self, categories):
        """Save JSON index of all channels."""
        data = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "total_channels": len(self.channels),
            "categories": {}
        }

        for cat_name, channels in sorted(categories.items()):
            data["categories"][cat_name] = [
                {
                    "name": ch.name,
                    "url": ch.url,
                    "logo": ch.logo,
                    "tvg_id": ch.tvg_id,
                    "tvg_name": ch.tvg_name,
                    "country": ch.tvg_country,
                    "source": ch.source,
                }
                for ch in channels
            ]

        with open(self.json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Saved JSON index: {self.json_file}")

    def print_summary(self, categories):
        """Print a summary of what was collected."""
        print()
        print("=" * 60)
        print("CRAWL SUMMARY")
        print("=" * 60)
        print(f"Total unique channels: {len(self.channels)}")
        print(f"Categories found:      {len(categories)}")
        print()

        for cat_name, channels in sorted(categories.items(), key=lambda x: -len(x[1])):
            print(f"  {cat_name:20s} {len(channels):6d} channels")

        print()
        print("Stats:")
        for k, v in sorted(self.stats.items()):
            print(f"  {k}: {v}")
        print()
        print(f"Output files:")
        print(f"  M3U:  {os.path.abspath(self.output_file)}")
        print(f"  JSON: {os.path.abspath(self.json_file)}")

    def run(self, discover=True, verify=False, verify_workers=20, verify_timeout=8):
        """Execute the full crawl pipeline."""
        print("IPTV M3U Crawler")
        print("=" * 60)
        start = time.time()

        self.crawl(discover=discover)

        if verify:
            self.verify_all_channels(max_workers=verify_workers, timeout=verify_timeout)

        categories = self.categorize()
        self.save_m3u(categories)
        self.save_json(categories)
        self.print_summary(categories)

        elapsed = time.time() - start
        print(f"\nCompleted in {elapsed:.1f} seconds")


# ---------------------------------------------------------------------------
# Auto-update daemon mode
# ---------------------------------------------------------------------------

def run_daemon(crawler, interval=3600):
    """Run crawler in a loop, updating every `interval` seconds."""
    print(f"Starting daemon mode — updating every {interval}s (Ctrl+C to stop)")
    while True:
        try:
            crawler.channels.clear()
            crawler.seen_urls.clear()
            crawler.stats.clear()
            crawler.run(discover=False)
            print(f"\nNext update in {interval}s...")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nDaemon stopped.")
            break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="IPTV M3U/M3U8 Crawler — finds, categorizes, and consolidates IPTV channels"
    )
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output M3U file path (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--json",
        default=DEFAULT_JSON_OUTPUT,
        help=f"Output JSON index path (default: {DEFAULT_JSON_OUTPUT})"
    )
    parser.add_argument(
        "--no-discover",
        action="store_true",
        help="Skip web discovery phase (only use seed URLs)"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in daemon mode, periodically re-crawling"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Update interval in seconds for daemon mode (default: 3600)"
    )
    parser.add_argument(
        "--add-url",
        action="append",
        default=[],
        help="Add extra M3U playlist URL(s) to crawl"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify streams are accessible (partial download test)"
    )
    parser.add_argument(
        "--verify-workers",
        type=int,
        default=20,
        help="Number of concurrent workers for verification (default: 20)"
    )
    parser.add_argument(
        "--verify-timeout",
        type=int,
        default=8,
        help="Timeout in seconds per stream verification (default: 8)"
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all channel categories and exit"
    )

    args = parser.parse_args()

    if args.list_categories:
        print("Available channel categories:")
        for cat_name, keywords in CATEGORY_RULES:
            print(f"  - {cat_name}")
        sys.exit(0)

    crawler = IPTVCrawler(output_file=args.output, json_file=args.json)

    # Add any extra URLs
    extra = args.add_url
    if extra:
        SEED_URLS.extend(extra)

    if args.daemon:
        run_daemon(crawler, interval=args.interval)
    else:
        crawler.run(discover=not args.no_discover, verify=args.verify,
                    verify_workers=args.verify_workers, verify_timeout=args.verify_timeout)
