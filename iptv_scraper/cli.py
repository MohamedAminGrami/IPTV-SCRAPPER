import requests
from bs4 import BeautifulSoup
from art import text2art
from colorama import init
from termcolor import colored
import datetime
import os
import argparse
import re
from urllib.parse import urljoin
import subprocess
import sys
import threading
import time
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import signal


class Spinner:
    """Animated spinner for showing progress"""
    def __init__(self, message="Loading", color="cyan"):
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
        self.message = message
        self.color = color
        self.running = False
        self.thread = None
    
    def spin(self):
        while self.running:
            sys.stdout.write(f'\r{colored(next(self.spinner), self.color)} {colored(self.message, "white")}  ')
            sys.stdout.flush()
            time.sleep(0.1)
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self, final_message=None):
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write('\r' + ' ' * 100 + '\r')  # Clear line
        if final_message:
            print(final_message)
        sys.stdout.flush()


class IPTVScraper:
    def __init__(self):
        self.scraped_links = []
        self.checked_urls = set()  # Avoid testing same URL twice
        self.total_tested = 0
        self.total_working = 0
        self.lock = threading.Lock()  # Thread-safe counter
        self.shutdown_flag = threading.Event()  # Flag to signal shutdown
        
        # Connection pooling for faster requests
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=50,
            pool_maxsize=50,
            max_retries=1,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Domain reputation cache (track success rates)
        self.domain_stats = {}  # domain -> {'success': 0, 'total': 0}
        
        init()
    
    def get_nsfw_sources(self):
        """Get NSFW/Adult specific sources"""
        return [
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/xxx.m3u",
            "https://iptv-org.github.io/iptv/index.nsfw.m3u",
            "https://raw.githubusercontent.com/dtankdempse/free-iptv/main/playlists/xxx.m3u",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_xxx.m3u8",
            "https://raw.githubusercontent.com/AqFad2811/myiptv/main/xxx.m3u8",
            "https://raw.githubusercontent.com/yuanzl77/IPTV/main/m3u/Adult.m3u",
            "https://raw.githubusercontent.com/BellezaEmporium/IPTV_Exception/master/adult.m3u8",
        ]
    
    def expand_search_terms(self, query):
        """Expand search query with related terms and synonyms"""
        if not query:
            return []
        
        query_lower = query.lower()
        expanded_terms = [query_lower]
        
        # Sports-related synonyms
        sports_synonyms = {
            'football': ['soccer', 'futbol', 'foot', 'fifa', 'premier', 'league', 'calcio', 'fussball', 'bundesliga', 'laliga', 'serie a'],
            'soccer': ['football', 'futbol', 'foot', 'fifa', 'premier', 'league', 'champions', 'uefa'],
            'basketball': ['nba', 'basket', 'hoops', 'bball', 'euroleague'],
            'nba': ['basketball', 'basket', 'hoops'],
            'tennis': ['atp', 'wta', 'tennis channel', 'grand slam', 'wimbledon', 'us open'],
            'boxing': ['fight', 'ufc', 'mma', 'combat', 'wrestling', 'wwe', 'aew', 'ppv'],
            'fight': ['boxing', 'ufc', 'mma', 'combat', 'wrestling', 'bellator'],
            'ufc': ['fight', 'mma', 'combat', 'boxing', 'bellator'],
            'mma': ['ufc', 'fight', 'combat', 'boxing', 'bellator'],
            'racing': ['formula', 'f1', 'nascar', 'motogp', 'motor', 'rally', 'indycar'],
            'f1': ['formula', 'racing', 'motor', 'grand prix', 'formula 1', 'formula1'],
            'cricket': ['ipl', 'bbl', 'cricket live', 'test cricket', 't20'],
            'baseball': ['mlb', 'baseball live'],
            'hockey': ['nhl', 'ice hockey'],
            'golf': ['pga', 'masters', 'golf channel'],
            'sport': ['sports', 'espn', 'fox sports', 'sky sports', 'bein', 'tsn', 'dazn', 'eurosport'],
            'sports': ['sport', 'espn', 'fox sports', 'sky sports', 'bein', 'tsn', 'dazn', 'eurosport'],
            'bein': ['bein sports', 'beinsports', 'bein sport', 'bien sports', 'bien', 'beIN', 'bein 1', 'bein 2', 'bein fr', 'bein ar', 'bein en'],
            'beinsports': ['bein', 'bein sports', 'bein sport', 'bien sports'],
            'espn': ['espn+', 'espn plus', 'espn deportes', 'espn2', 'espn news'],
            'sky': ['sky sports', 'sky cinema', 'sky news', 'sky sport'],
            'dazn': ['dazn1', 'dazn2', 'dazn sports', 'dazn live'],
            'eurosport': ['euro sport', 'eurosport 1', 'eurosport 2'],
            'premier': ['premier league', 'epl', 'premiership'],
            'champions': ['champions league', 'ucl', 'uefa'],
        }
        
        # News-related synonyms
        news_synonyms = {
            'news': ['noticias', 'nouvelles', 'nachrichten', 'breaking', 'live news', 'cnn', 'bbc'],
            'cnn': ['news', 'cable news', 'breaking'],
            'bbc': ['news', 'british', 'uk news'],
            'aljazeera': ['al jazeera', 'jazeera', 'arabic news', 'qatar'],
            'sky': ['sky news', 'news', 'uk'],
        }
        
        # Entertainment synonyms
        entertainment_synonyms = {
            'movie': ['movies', 'cinema', 'film', 'peliculas', 'filme'],
            'movies': ['movie', 'cinema', 'film', 'peliculas', 'filme'],
            'series': ['tv shows', 'shows', 'drama', 'serie'],
            'kids': ['children', 'cartoon', 'disney', 'nickelodeon', 'cartoon network'],
            'cartoon': ['kids', 'animation', 'anime', 'disney'],
            'music': ['mtv', 'vh1', 'music video', 'concert'],
            'documentary': ['discovery', 'national geographic', 'history', 'natgeo', 'docs'],
            'discovery': ['documentary', 'science', 'nature', 'animal planet'],
        }
        
        # Regional/Language synonyms
        regional_synonyms = {
            'arabic': ['arab', 'عربي', 'mbc', 'osn', 'rotana', 'nile', 'saudi', 'dubai', 'aljazeera'],
            'arab': ['arabic', 'mbc', 'osn', 'rotana', 'middle east'],
            'tunisia': ['tunisie', 'tunisian', 'tunis', 'maghreb', 'north africa'],
            'egypt': ['egyptian', 'cairo', 'nile', 'مصر'],
            'morocco': ['maroc', 'moroccan', 'maghreb'],
            'algeria': ['algerian', 'maghreb', 'dzair'],
            'france': ['french', 'français', 'tf1', 'm6', 'canal'],
            'uk': ['british', 'britain', 'bbc', 'itv'],
            'usa': ['us', 'american', 'america', 'united states'],
            'spain': ['spanish', 'español', 'espana'],
        }
        
        # Brand/Network synonyms
        network_synonyms = {
            'bein': ['bein sports', 'beinsport', 'bein sport', 'bien'],
            'espn': ['espn+', 'espn plus', 'espn deportes'],
            'sky': ['sky sports', 'sky cinema', 'sky news'],
            'fox': ['fox sports', 'fox news', 'fox channel'],
            'mbc': ['mbc1', 'mbc2', 'mbc3', 'mbc drama', 'mbc action'],
            'osn': ['osn sports', 'osn movies', 'orbit'],
            'dazn': ['dazn1', 'dazn2', 'dazn sports'],
        }
        
        # NSFW/Adult synonyms
        nsfw_synonyms = {
            'adult': ['xxx', '18+', 'nsfw', 'playboy', 'hustler', 'penthouse', 'venus', 'dorcel'],
            'xxx': ['adult', '18+', 'nsfw', 'playboy', 'hustler'],
            'nsfw': ['adult', 'xxx', '18+'],
            '18+': ['adult', 'xxx', 'nsfw'],
            'playboy': ['adult', 'xxx', 'hustler', 'penthouse'],
            'venus': ['adult', 'xxx', 'dorcel'],
        }
        
        # TV Channel synonyms
        tv_channel_synonyms = {
            'tv': ['television', 'channel', 'live tv', 'broadcast'],
            'channel': ['tv', 'television', 'live', 'broadcast'],
            'cnn': ['news', 'cable news network', 'cnn international'],
            'hbo': ['premium', 'movies', 'series', 'hbo max'],
            'showtime': ['premium', 'movies'],
            'nbc': ['network', 'broadcast'],
            'cbs': ['network', 'broadcast'],
            'abc': ['network', 'broadcast'],
            'fox': ['network', 'broadcast', 'fox news'],
            'mtv': ['music', 'music television'],
            'comedy': ['comedy central', 'standup'],
            'hgtv': ['home', 'garden', 'diy'],
            'food': ['food network', 'cooking'],
            'tlc': ['learning', 'reality'],
            'lifetime': ['movies', 'drama'],
            'syfy': ['sci-fi', 'science fiction'],
            'cartoon': ['cartoon network', 'cn', 'cartoons', 'toon', 'boomerang'],
            'disney': ['disney channel', 'disney+', 'disney junior', 'disney xd'],
            'nickelodeon': ['nick', 'nick jr', 'nicktoons'],
            'discovery': ['discovery channel', 'discovery+', 'science', 'tlc'],
            'natgeo': ['national geographic', 'nat geo', 'nat geo wild'],
            'history': ['history channel', 'h2'],
            'amc': ['amc network', 'walking dead'],
            'fx': ['fxx', 'fxm'],
            'tnt': ['tbs', 'tru tv'],
            'usa': ['usa network'],
            'bravo': ['bravo tv'],
            'e!': ['e entertainment'],
            'travel': ['travel channel'],
            'animal': ['animal planet'],
            'paramount': ['paramount network', 'paramount+'],
            'peacock': ['nbc peacock'],
            'hulu': ['hulu live'],
            'netflix': ['netflix channel'],
        }
        
        # Combine all synonym dictionaries
        all_synonyms = {
            **sports_synonyms,
            **news_synonyms,
            **entertainment_synonyms,
            **regional_synonyms,
            **network_synonyms,
            **nsfw_synonyms,
            **tv_channel_synonyms
        }
        
        # Find and add synonyms
        for key, synonyms in all_synonyms.items():
            if query_lower == key or query_lower in key:
                expanded_terms.extend(synonyms)
                break
            elif query_lower in synonyms:
                expanded_terms.append(key)
                expanded_terms.extend([s for s in synonyms if s != query_lower])
                break
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in expanded_terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)
        
        return unique_terms
    
    def test_iptv_link(self, link, timeout=5, show_progress=True):
        """Enhanced test to ensure IPTV link is truly playable"""
        # Skip if already tested
        if link in self.checked_urls:
            return False
        
        # Pre-validate URL format (fast rejection)
        if not self._is_valid_stream_url(link):
            return False
        
        self.checked_urls.add(link)
        self.total_tested += 1
        
        # Track domain stats
        domain = self._extract_domain(link)
        
        try:
            headers = {
                'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            
            # Step 1: Check if URL is accessible (use session for connection pooling)
            response = self.session.get(link, timeout=timeout, stream=True, allow_redirects=True, headers=headers, verify=False)
            
            if response.status_code != 200:
                self._update_domain_stats(domain, False)
                return False
            
            content_type = response.headers.get('content-type', '').lower()
            content_length = response.headers.get('content-length', '0')
            
            # Reject suspiciously small content
            if content_length.isdigit() and int(content_length) < 500:
                self._update_domain_stats(domain, False)
                return False
            
            # Step 2: For M3U8 playlists, perform fast validation
            if link.endswith('.m3u8') or link.endswith('.m3u') or 'mpegurl' in content_type:
                try:
                    # Read first 32KB for faster validation
                    content_chunks = []
                    bytes_read = 0
                    max_bytes = 32768  # 32KB (reduced from 100KB for speed)
                    
                    for chunk in response.iter_content(8192):
                        content_chunks.append(chunk)
                        bytes_read += len(chunk)
                        if bytes_read >= max_bytes:
                            break
                    
                    content = b''.join(content_chunks).decode('utf-8', errors='ignore')
                    
                    # Check for error indicators in response
                    error_indicators = [
                        'not found',
                        '404',
                        'error',
                        'forbidden',
                        'access denied',
                        'moose_na',  # Known placeholder
                        'unavailable',
                        'offline',
                        'geo-block',
                        'restricted'
                    ]
                    
                    content_lower = content.lower()
                    for indicator in error_indicators:
                        if indicator in content_lower:
                            return False
                    
                    # Must have M3U header
                    if '#EXTM3U' not in content:
                        return False
                    
                    # Check for valid M3U8 tags
                    has_valid_tags = any(tag in content for tag in [
                        '#EXT-X-STREAM-INF',
                        '#EXTINF:',
                        '#EXT-X-TARGETDURATION'
                    ])
                    
                    if not has_valid_tags:
                        return False
                    
                    # Extract stream URLs from playlist
                    lines = content.split('\n')
                    stream_urls = []
                    
                    for line in lines:
                        line = line.strip()
                        # Look for actual stream URLs
                        if line and not line.startswith('#'):
                            if line.startswith('http'):
                                stream_urls.append(line)
                            elif line.endswith('.ts') or line.endswith('.m4s') or line.endswith('.m3u8'):
                                # Relative URL - construct full URL
                                base_url = link.rsplit('/', 1)[0]
                                stream_urls.append(f"{base_url}/{line}")
                    
                    # Must have at least one stream URL
                    if not stream_urls:
                        return False
                    
                    # Step 3: Test actual stream segment (first one)
                    test_url = stream_urls[0]
                    
                    # If it's another .m3u8, we need to go deeper (nested playlist)
                    if test_url.endswith('.m3u8'):
                        try:
                            playlist_response = self.session.get(test_url, timeout=5, headers=headers, verify=False)
                            if playlist_response.status_code != 200:
                                return False
                            
                            playlist_content = playlist_response.text
                            
                            # Check for errors in nested playlist too
                            for indicator in error_indicators:
                                if indicator in playlist_content.lower():
                                    return False
                            
                            # Find first actual segment
                            for pline in playlist_content.split('\n'):
                                pline = pline.strip()
                                if pline and not pline.startswith('#'):
                                    if pline.startswith('http'):
                                        test_url = pline
                                    else:
                                        base_url = test_url.rsplit('/', 1)[0]
                                        test_url = f"{base_url}/{pline}"
                                    break
                            
                            # If still .m3u8, reject (too many nested levels)
                            if test_url.endswith('.m3u8'):
                                return False
                                
                        except:
                            return False
                    
                    # Step 4: Test the actual stream segment
                    try:
                        segment_response = self.session.get(test_url, timeout=5, stream=True, headers=headers, verify=False)
                        if segment_response.status_code != 200:
                            return False
                        
                        # Check content type of segment
                        seg_content_type = segment_response.headers.get('content-type', '').lower()
                        
                        # Should be video or stream data, not text/html
                        if 'text/html' in seg_content_type or 'text/plain' in seg_content_type:
                            return False
                        
                        # Read multiple chunks to ensure it's real video data
                        chunks_read = 0
                        total_bytes = 0
                        valid_data = False
                        
                        for chunk in segment_response.iter_content(16384):
                            if chunk:
                                chunks_read += 1
                                total_bytes += len(chunk)
                                
                                # On first chunk, validate it's video data
                                if chunks_read == 1:
                                    # For .ts files, check for MPEG-TS packet signature
                                    if test_url.endswith('.ts'):
                                        # MPEG-TS packets start with 0x47 (sync byte)
                                        if len(chunk) > 0 and chunk[0] == 0x47:
                                            valid_data = True
                                        else:
                                            return False
                                    else:
                                        # For other formats, just ensure it's binary data
                                        valid_data = True
                                
                                # Read at least 2 chunks (32KB)
                                if chunks_read >= 2:
                                    break
                        
                        # Must have received substantial valid data
                        if not valid_data or total_bytes < 16384:  # At least 16KB
                            self._update_domain_stats(domain, False)
                            return False
                        
                        self._update_domain_stats(domain, True)
                        return True
                        
                    except:
                        return False
                    
                except Exception as e:
                    return False
            
            # Step 2b: For direct streams, validate video data
            elif 'video' in content_type or 'stream' in content_type or 'octet-stream' in content_type:
                try:
                    # Read more data to ensure it's a real stream
                    chunks_read = 0
                    total_bytes = 0
                    
                    for chunk in response.iter_content(16384):
                        if chunk:
                            chunks_read += 1
                            total_bytes += len(chunk)
                            
                            # Read at least 3 chunks (48KB)
                            if chunks_read >= 3:
                                break
                    
                    # Must have received substantial data
                    if total_bytes >= 32768:  # At least 32KB
                        self._update_domain_stats(domain, True)
                        return True
                    else:
                        self._update_domain_stats(domain, False)
                        return False
                    
                except:
                    self._update_domain_stats(domain, False)
                    return False
            
            self._update_domain_stats(domain, False)
            return False
            
        except requests.exceptions.Timeout:
            return False
        except requests.exceptions.ConnectionError:
            return False
        except Exception as e:
            return False
    
    def _is_valid_stream_url(self, url):
        """Quick validation to reject obviously invalid URLs"""
        if not url or len(url) < 20:
            return False
        
        # Must be http/https
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Reject common non-stream patterns
        invalid_patterns = [
            'example.com', 'localhost', '127.0.0.1', 
            '.html', '.php?', '.asp?', '.jpg', '.png', '.gif',
            'facebook.com', 'twitter.com', 'youtube.com/watch',
            'google.com', 'github.com'
        ]
        
        url_lower = url.lower()
        if any(pattern in url_lower for pattern in invalid_patterns):
            return False
        
        # Must have valid stream extension or path
        valid_indicators = ['.m3u8', '.m3u', '.ts', '.mpd', '/live/', '/hls/', '/stream', 'playlist']
        if not any(indicator in url_lower for indicator in valid_indicators):
            return False
        
        return True
    
    def _extract_domain(self, url):
        """Extract domain from URL for stats tracking"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return 'unknown'
    
    def _update_domain_stats(self, domain, success):
        """Track domain success rates for prioritization"""
        if domain not in self.domain_stats:
            self.domain_stats[domain] = {'success': 0, 'total': 0}
        
        self.domain_stats[domain]['total'] += 1
        if success:
            self.domain_stats[domain]['success'] += 1
    
    def extract_urls_from_text(self, text):
        """Extract potential IPTV URLs from text with advanced patterns"""
        patterns = [
            # Standard streaming URLs (m3u8, ts, mpd, etc.)
            r'https?://[^\s<>"{}|\\^\[\]`]+\.(?:m3u8?|ts|mpd|mpegurl|stream|aac|mp3|mp4|flv)',
            # IP-based streaming (common IPTV ports)
            r'https?://(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?/[^\s<>"{}|\\^\[\]`]*',
            # HLS/DASH patterns
            r'https?://[^\s<>"{}|\\^\[\]`]+/(?:hls|dash|live|stream|channel|tv|playlist)/[^\s<>"{}|\\^\[\]`]+',
            # M3U8 with query parameters
            r'https?://[^\s<>"{}|\\^\[\]`]+\.m3u8\?[^\s<>"{}|\\^\[\]`]*',
            # TS streams with path patterns (like iptv.am000.tv)
            r'https?://[^\s<>"{}|\\^\[\]`]+/live/[^\s<>"{}|\\^\[\]`]+/[^\s<>"{}|\\^\[\]`]+/\d+\.ts',
            # CDN patterns (CloudFront, Akamai, etc.)
            r'https?://[^\s<>"{}|\\^\[\]`]*\.(?:cloudfront\.net|akamaihd\.net|cdn\d*\.|edge\d*\.|stream\d*\.)[^\s<>"{}|\\^\[\]`]+',
            # Sports streaming specific (BeIN, DAZN, ESPN, etc.)
            r'https?://[^\s<>"{}|\\^\[\]`]*(?:bein|dazn|espn|sky|sport)[^\s<>"{}|\\^\[\]`]*\.(?:m3u8?|ts)[^\s<>"{}|\\^\[\]`]*',
            # Encoded URLs (URL in query params)
            r'https?://[^\s<>"{}|\\^\[\]`]*[?&](?:url|src|stream|link)=https?[^\s<>"{}|\\^\[\]`]+',
            # Albaplayer and similar player URLs
            r'https?://[^\s<>"{}|\\^\[\]`]*(?:albaplayer|player|embed)/[^\s<>"{}|\\^\[\]`]+',
            # Alkoora and yalllashoot domains
            r'https?://[^\s<>"{}|\\^\[\]`]*\.(?:alkoora\.live|yalllashoot\.today)[^\s<>"{}|\\^\[\]`]*',
            # IPTV server patterns (common IPTV hosting)
            r'https?://[^\s<>"{}|\\^\[\]`]*\.(?:tv|live|stream):\d+/[^\s<>"{}|\\^\[\]`]+',
        ]
        
        urls = []
        for pattern in patterns:
            urls.extend(re.findall(pattern, text, re.IGNORECASE))
        
        # Filter and clean
        unique_urls = list(set(urls))
        return [url for url in unique_urls if url.startswith('http') and len(url) > 15]
    
    def scan_ip_range_for_streams(self, base_ip, channel_name, max_to_find=5):
        """Scan IP addresses for common IPTV streaming patterns"""
        found_streams = []
        common_ports = [8080, 8000, 8081, 9981, 1935, 554, 80]
        common_paths = [
            '/live/stream.m3u8',
            '/hls/stream.m3u8',
            '/playlist.m3u8',
            '/live.m3u8',
            '/stream.m3u8',
            '/index.m3u8',
            '/play/a001/index.m3u8',
            '/play/a002/index.m3u8',
        ]
        
        print(colored(f"[*] Scanning IP-based streams for {channel_name}...", "cyan"))
        
        # Extract base IP pattern (e.g., 66.102.120.x)
        ip_parts = base_ip.split('.')
        if len(ip_parts) == 4:
            for last_octet in range(1, 255, 10):  # Sample every 10th IP
                test_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{last_octet}"
                
                for port in common_ports[:3]:  # Test first 3 ports
                    for path in common_paths[:3]:  # Test first 3 paths
                        url = f"http://{test_ip}:{port}{path}"
                        
                        if self.test_iptv_link(url, timeout=3):
                            found_streams.append({
                                'title': f'{channel_name} - {test_ip}:{port}',
                                'url': url
                            })
                            print(colored(f"[✓] Found: {url}", "green"))
                            
                            if len(found_streams) >= max_to_find:
                                return found_streams
        
        return found_streams
    
    def scrape_iptv_cat(self, channel_name, num_needed):
        """Scrape from IPTV-Cat website"""
        found = []
        try:
            search_url = f"https://www.iptv-cat.com/search/{channel_name.replace(' ', '%20')}"
            print(colored(f"[*] Searching IPTV-Cat for: {channel_name}", "cyan"))
            
            response = requests.get(search_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all stream URLs
                urls = self.extract_urls_from_text(response.text)
                
                for url in urls[:num_needed * 2]:  # Test more than needed
                    if self.test_iptv_link(url):
                        found.append({
                            'title': f'{channel_name} - IPTV-Cat',
                            'url': url
                        })
                        
                        if len(found) >= num_needed:
                            break
        except:
            pass
        
        return found
    
    def extract_iframe_streams(self, html_content):
        """Extract streaming URLs from iframes and embed tags"""
        stream_urls = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all iframes
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src') or iframe.get('data-src')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        continue  # Relative URLs need base URL
                    stream_urls.append(src)
            
            # Find embed tags
            embeds = soup.find_all('embed')
            for embed in embeds:
                src = embed.get('src')
                if src and src.startswith('http'):
                    stream_urls.append(src)
            
            # Find video sources
            videos = soup.find_all('video')
            for video in videos:
                sources = video.find_all('source')
                for source in sources:
                    src = source.get('src')
                    if src and src.startswith('http'):
                        stream_urls.append(src)
            
            # Look for data attributes with streaming URLs
            for tag in soup.find_all(attrs={'data-stream': True}):
                stream_urls.append(tag['data-stream'])
            
            for tag in soup.find_all(attrs={'data-url': True}):
                stream_urls.append(tag['data-url'])
                
        except Exception as e:
            pass
        
        return stream_urls
    
    def scrape_albaplayer_channels(self, num_needed):
        """Scrape albaplayer streaming platforms (alkoora.live, yalllashoot.today)"""
        found = []
        
        # Albaplayer platforms with common channels
        albaplayer_platforms = [
            'https://aaaaaaa.alkoora.live/albaplayer/',
            'https://pl.yalllashoot.today/albaplayer/',
            'https://yalllashoot.today/albaplayer/',
            'https://www.alkoora.live/albaplayer/',
        ]
        
        # Common channel endpoints on albaplayer
        common_channels = [
            'bein1', 'bein2', 'bein3', 'bein4', 'bein5', 'bein6', 'bein7', 'bein8',
            'bein11', 'bein12', 'bein13', 'bein14', 'bein15', 'bein16', 'bein17',
            'bein21', 'bein22', 'bein23', 'bein24', 'bein25',
            'ad-sport-1', 'ad-sport-2', 'ad-sport-3', 'ad-sport-4', 'ad-sport-5',
            'ssc1', 'ssc2', 'ssc3', 'ssc4', 'ssc5',
            'dazn1', 'dazn2', 'dazn-laliga', 'dazn-laliga2',
            'espn', 'espn2', 'sky-sport', 'sky-sports-football',
            'premier-sports-1', 'premier-sports-2',
            'tnt-sports-1', 'tnt-sports-2', 'tnt-sports-3',
        ]
        
        print(colored(f"[*] Scanning albaplayer platforms for streams...", "cyan"))
        
        for platform in albaplayer_platforms:
            if len(found) >= num_needed:
                break
                
            for channel in common_channels:
                if len(found) >= num_needed:
                    break
                    
                url = platform + channel + '/'
                
                try:
                    # Quick HEAD request to check if channel exists (3s timeout)
                    response = self.session.head(url, timeout=3, allow_redirects=True, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }, verify=False)
                    
                    if response.status_code == 200:
                        # Try to get the actual stream URL from the player page
                        page_response = self.session.get(url, timeout=6, headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        }, verify=False)
                        
                        if page_response.status_code == 200:
                            # Extract m3u8 URLs from the page
                            m3u8_urls = self.extract_urls_from_text(page_response.text)
                            
                            for m3u8_url in m3u8_urls:
                                if '.m3u8' in m3u8_url and self.test_iptv_link(m3u8_url, timeout=5):
                                    found.append({
                                        'title': f'{channel.upper()} - {platform.split("//")[1].split("/")[0]}',
                                        'url': m3u8_url
                                    })
                                    print(colored(f"  ✓ Found: {channel}", "green"))
                                    break
                            
                            # If no m3u8 found, save the player URL itself
                            if not m3u8_urls:
                                found.append({
                                    'title': f'{channel.upper()} - AlbaPlayer',
                                    'url': url
                                })
                                print(colored(f"  ✓ Found player: {channel}", "yellow"))
                                
                except:
                    continue
        
        return found
    
    def scrape_match_streaming_sites(self, channel_name, num_needed):
        """Scrape from live match streaming websites"""
        found = []
        
        # Match streaming aggregator sites
        match_sites = [
            'https://c.sia.watch/premium-1/',
            'https://c.sia.watch/premium-2/',
            'https://reddits.soccerstreams.net/',
            'https://v2.sportsurge.net/',
            'https://streameast.io/',
            'https://sportshub.stream/',
            'https://streamsgate.tv/',
            'https://socceronline.me/',
            'https://reddistreams.com/',
            'https://buffstreams.app/',
            'https://crackstreams.com/',
            'https://nflbite.com/',
            'https://nbabite.com/',
            'https://mlbshow.com/',
            # Albaplayer platforms
            'https://aaaaaaa.alkoora.live/',
            'https://pl.yalllashoot.today/',
            'https://yalllashoot.today/',
            'https://www.alkoora.live/',
        ]
        
        for site in match_sites:
            if len(found) >= num_needed:
                break
                
            try:
                print(colored(f"[*] Scraping match site: {site.split('//')[1].split('/')[0]}...", "cyan"))
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://www.google.com/',
                }
                
                response = requests.get(site, timeout=15, headers=headers, allow_redirects=True)
                
                if response.status_code == 200:
                    # Extract URLs from page content
                    all_urls = self.extract_urls_from_text(response.text)
                    
                    # Extract iframe streams
                    iframe_urls = self.extract_iframe_streams(response.text)
                    all_urls.extend(iframe_urls)
                    
                    # Also look for API endpoints in JavaScript
                    js_pattern = r'(?:src|source|stream|url)["\']\s*:\s*["\']([^"\']+\.m3u8?[^"\']*)["\']'
                    js_urls = re.findall(js_pattern, response.text, re.IGNORECASE)
                    all_urls.extend(js_urls)
                    
                    for url in all_urls:
                        # Clean up URL
                        if url.startswith('//'):
                            url = 'https:' + url
                        
                        # Check if relevant
                        if channel_name and channel_name.lower() not in url.lower():
                            # Skip if searching for specific channel
                            continue
                        
                        # Test the link
                        if url.endswith(('.m3u8', '.m3u', '.ts')) or '/hls/' in url or '/live/' in url:
                            if self.test_iptv_link(url, timeout=8):
                                found.append({
                                    'title': f'Live Match - {site.split("//")[1].split("/")[0]}',
                                    'url': url
                                })
                                print(colored(f"  ✓ Found working stream!", "green"))
                                
                                if len(found) >= num_needed:
                                    break
                                    
            except Exception as e:
                continue
        
        return found
    
    def scrape_live_tv_websites(self, channel_name, num_needed):
        """Scrape from live TV aggregator websites"""
        found = []
        websites = [
            'https://www.tvtap.live',
            'https://ustvgo.tv',
            'https://123tv.live',
            'https://streameast.io',
            'https://sportsurge.net',
            'https://methstreams.com',
            'https://www.livetv.sx',
            'https://live-streamz.com',
        ]
        
        for site in websites:
            # Check for shutdown
            if self.shutdown_flag.is_set():
                break
                
            try:
                print(colored(f"[*] Checking {site.split('//')[1]}...", "cyan"))
                response = requests.get(site, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if response.status_code == 200:
                    # Extract all streaming URLs
                    urls = self.extract_urls_from_text(response.text)
                    
                    for url in urls:
                        # Check for shutdown in inner loop
                        if self.shutdown_flag.is_set():
                            break
                            
                        if channel_name.lower() in url.lower() or not channel_name:
                            if self.test_iptv_link(url):
                                found.append({
                                    'title': f'{channel_name} - {site.split("//")[1]}',
                                    'url': url
                                })
                                
                                if len(found) >= num_needed:
                                    return found
            except KeyboardInterrupt:
                raise
            except:
                continue
        
        return found
    
    def scrape_pastebin_sites(self, channel_name, num_needed):
        """Scrape IPTV links from pastebin and paste sites"""
        found = []
        
        # Pastebin and paste sites with IPTV content
        paste_sites = [
            'https://pastebin.com/raw/iptv',
            'https://rentry.co/iptv',
            'https://rentry.co/freeiptv',
            'https://rentry.co/iptvlinks',
            'https://controlc.com/iptv',
            'https://justpaste.it/iptv',
            'https://paste.ee/r/iptv',
            'https://ghostbin.com/paste/iptv',
        ]
        
        # Search for IPTV pastebins on Google
        search_queries = [
            'site:pastebin.com iptv m3u8',
            'site:pastebin.com bein sports',
            'site:rentry.co iptv',
            'site:controlc.com iptv',
            '"http" ".ts" "live" pastebin',
            'iptv.am000.tv pastebin',
        ]
        
        print(colored(f"[*] Searching paste sites for IPTV links...", "cyan"))
        
        # Try known paste URLs
        for paste_url in paste_sites:
            if len(found) >= num_needed or self.shutdown_flag.is_set():
                break
                
            try:
                response = requests.get(paste_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if response.status_code == 200:
                    # Extract all streaming URLs
                    urls = self.extract_urls_from_text(response.text)
                    
                    for url in urls:
                        if self.shutdown_flag.is_set():
                            break
                            
                        # Filter by channel name if specified
                        if not channel_name or any(term in url.lower() for term in [channel_name.lower(), 'bein', 'sport']):
                            if self.test_iptv_link(url, timeout=8):
                                found.append({
                                    'title': f'{channel_name or "Stream"} - Pastebin',
                                    'url': url
                                })
                                print(colored(f"  ✓ Found from paste site", "green"))
                                
                                if len(found) >= num_needed:
                                    break
            except KeyboardInterrupt:
                raise
            except:
                continue
        
        return found
    
    def get_all_sources(self):
        """Get comprehensive list of IPTV sources"""
        return [
            # Official IPTV collections
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams.m3u",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/channels.m3u",
            
            # Major GitHub repositories
            "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
            "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
            "https://raw.githubusercontent.com/yuanzl77/IPTV/main/live.m3u",
            "https://raw.githubusercontent.com/BellezaEmporium/IPTV_Exception/master/playlist.m3u8",
            "https://raw.githubusercontent.com/Fazzani/grab/master/merge.m3u",
            
            # New comprehensive sources
            "https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/youtube.m3u",
            "https://raw.githubusercontent.com/AqFad2811/myiptv/main/playlist.m3u8",
            "https://raw.githubusercontent.com/mitthu786/tvepg/main/m3u/all.m3u",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
            "https://raw.githubusercontent.com/Sphinxroot/Sphinx-Playlist/main/playlist.m3u",
            "https://raw.githubusercontent.com/dtankdempse/free-iptv/main/playlists/ipv4.m3u",
            "https://raw.githubusercontent.com/LaneSh4d0w/IPTV_Playlist/master/playlist.m3u8",
            "https://raw.githubusercontent.com/peterpt/iptv-m3u-epg/main/all.m3u",
            
            # Sports focused - General
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_sports.m3u8",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/sports.m3u",
            "https://raw.githubusercontent.com/mitthu786/Sports-Channel/main/m3u/Sports.m3u",
            "https://raw.githubusercontent.com/dtankdempse/free-iptv/main/playlists/sports.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/sp.m3u",
            
            # Sports - BeIN Sports specific
            "https://raw.githubusercontent.com/dtankdempse/free-iptv/main/playlists/bein.m3u",
            "https://raw.githubusercontent.com/mitthu786/sportscenter/main/beinsports.m3u",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_bein.m3u8",
            
            # Sports - ESPN & Premium Sports
            "https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/espn.m3u",
            "https://raw.githubusercontent.com/mitthu786/Sports-Channel/main/m3u/ESPN.m3u",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_espn.m3u8",
            
            # Sports - Sky Sports
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_sky.m3u8",
            "https://raw.githubusercontent.com/dtankdempse/free-iptv/main/playlists/sky.m3u",
            
            # Sports - Football/Soccer
            "https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/football.m3u",
            "https://raw.githubusercontent.com/mitthu786/Sports-Channel/main/m3u/Football.m3u",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_football.m3u8",
            
            # Sports - DAZN
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_dazn.m3u8",
            "https://raw.githubusercontent.com/dtankdempse/free-iptv/main/playlists/dazn.m3u",
            
            # News focused
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/news.m3u",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_news.m3u8",
            "https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/newsfeeds.m3u",
            
            # Entertainment & Movies
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/entertainment.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/movies.m3u",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_kids.m3u8",
            
            # Regional sources - Americas
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/us.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ca.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/mx.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/br.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ar.m3u",
            
            # Regional sources - Europe
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/uk.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/fr.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/de.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/es.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/it.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/nl.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ru.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/tr.m3u",
            
            # Regional sources - Middle East & Asia
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ae.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/sa.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/qa.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/in.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/jp.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/kr.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/pk.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/th.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/id.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/my.m3u",
            
            # Regional sources - Africa & Oceania
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/za.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/eg.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/au.m3u",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/nz.m3u",
            
            # North African countries (Tunisia & neighbors)
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/tn.m3u",  # Tunisia
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/dz.m3u",  # Algeria
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ma.m3u",  # Morocco
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ly.m3u",  # Libya
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/mr.m3u",  # Mauritania
            
            # More Arabic/Middle Eastern countries
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/lb.m3u",  # Lebanon
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/sy.m3u",  # Syria
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/iq.m3u",  # Iraq
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/jo.m3u",  # Jordan
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ps.m3u",  # Palestine
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/kw.m3u",  # Kuwait
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/bh.m3u",  # Bahrain
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/om.m3u",  # Oman
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ye.m3u",  # Yemen
            
            # Arabic-focused repositories
            "https://raw.githubusercontent.com/Fazzani/grab/master/arabics.m3u",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_arabic.m3u8",
            
            # Language-based sources
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ara.m3u",  # Arabic
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/spa.m3u",  # Spanish
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/por.m3u",  # Portuguese
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/rus.m3u",  # Russian
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/zho.m3u",  # Chinese
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/hin.m3u",  # Hindi
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/fra.m3u",  # French (useful for Tunisia)
            
            # Alternative collections & aggregators
            "https://iptv-org.github.io/iptv/index.m3u",
            "https://iptv-org.github.io/iptv/index.nsfw.m3u",
            "https://raw.githubusercontent.com/ChichiMsdk/IPTV-SERVER/main/playlist.m3u8",
            "https://raw.githubusercontent.com/Paradise-91/ParaTV/main/streams/all.m3u",
            
            # Specialized & curated lists
            "https://raw.githubusercontent.com/notanewbie/LegalStream/main/app/streams/all_streams.m3u",
            "https://raw.githubusercontent.com/freearhey/iptv/master/streams/all.m3u",
            
            # More aggregated playlists
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_kids.m3u8",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_music.m3u8",
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_documentaries.m3u8",
            
            # NSFW/Adult sources (18+)
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/xxx.m3u",
        ]
    
    def scrape_web_sources(self, channel_name, num_needed):
        """Scrape IPTV links from web sources"""
        found = 0
        
        # Direct M3U hosting sites
        direct_m3u_sites = [
            "https://m3u.cl/playlist.m3u",
            "https://iptvcat.com/my_list",
            "https://dailyiptvlist.com/wp-content/uploads/latest.m3u",
        ]
        
        # Additional web sources
        web_sources = [
            "https://streamtest.in",
            "https://iptv-list.live",
        ]
        
        # Try direct M3U sites
        for site_url in direct_m3u_sites:
            if found >= num_needed:
                break
            
            try:
                print(colored(f"[*] Checking direct M3U: {site_url.split('/')[2]}...", "cyan"))
                response = requests.get(site_url, timeout=10)
                
                if response.status_code == 200:
                    # Parse as M3U
                    lines = response.text.split('\n')
                    current_name = ""
                    
                    for line in lines:
                        line = line.strip()
                        
                        if line.startswith('#EXTINF'):
                            current_name = line.split(',')[-1].strip() if ',' in line else ""
                        
                        elif line and not line.startswith('#') and line.startswith('http'):
                            if not channel_name or channel_name.lower() in current_name.lower() or channel_name.lower() in line.lower():
                                
                                status_msg = f"[{self.total_tested}] Testing: {(current_name or line)[:45]}..."
                                print(colored(status_msg, "white"), end=" ")
                                
                                if self.test_iptv_link(line):
                                    self.total_working += 1
                                    print(colored(f"✓ [{self.total_working}/{num_needed}]", "green"))
                                    self.scraped_links.append({
                                        'title': current_name or 'Stream',
                                        'url': line
                                    })
                                    found += 1
                                    
                                    if found >= num_needed:
                                        return found
                                else:
                                    print(colored("✗", "red"))
                            
                            current_name = ""
            except:
                continue
        
        return found
    
    def search_github_repos(self, query="iptv m3u"):
        """Search GitHub for new IPTV repositories"""
        additional_sources = []
        
        try:
            # Search GitHub API for IPTV repos (silent - spinner handles this)
            search_url = f"https://api.github.com/search/repositories?q={query}+in:name&sort=updated&per_page=10"
            response = requests.get(search_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for repo in data.get('items', []):
                    # Try to find M3U files in the repo
                    repo_name = repo['full_name']
                    default_branch = repo.get('default_branch', 'master')
                    
                    # Common M3U file locations
                    possible_files = [
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/playlist.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/playlist.m3u8",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/live.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/channels.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/streams.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/stream.m3u",
                        # Sports specific
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/bein.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/beinsports.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/sports.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/sport.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/espn.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/sky.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/dazn.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/football.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/soccer.m3u",
                        f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/streamio.m3u",
                    ]
                    
                    for url in possible_files:
                        try:
                            test_response = requests.head(url, timeout=5)
                            if test_response.status_code == 200:
                                additional_sources.append(url)
                        except:
                            continue
        except:
            pass
        
        return additional_sources
    
    def scrape_json_apis(self, channel_name, num_needed):
        """Scrape from JSON API endpoints"""
        found = 0
        
        # IPTV API endpoints (public)
        api_endpoints = [
            "https://iptv-org.github.io/api/streams.json",
            "https://iptv-org.github.io/api/channels.json",
        ]
        
        for api_url in api_endpoints:
            if found >= num_needed:
                break
            
            try:
                print(colored(f"[*] Querying API: {api_url.split('/')[-1]}...", "cyan"))
                response = requests.get(api_url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle different JSON structures
                    items = data if isinstance(data, list) else data.get('items', [])
                    
                    for item in items:
                        if found >= num_needed:
                            break
                        
                        # Extract URL and name from various JSON formats
                        url = item.get('url') or item.get('stream') or item.get('link')
                        name = item.get('name') or item.get('title') or item.get('channel')
                        
                        if url and (not channel_name or (name and channel_name.lower() in name.lower())):
                            print(colored(f"[*] Testing API stream: {name or url[:60]}...", "white"), end=" ")
                            
                            if self.test_iptv_link(url):
                                print(colored("✓ WORKING", "green"))
                                self.scraped_links.append({
                                    'title': name or 'Stream',
                                    'url': url
                                })
                                found += 1
                            else:
                                print(colored("✗ Failed", "red"))
            except:
                continue
        
        return found
    
    def scrape_streamtest(self, channel_name, num_needed):
        """Scrape from streamtest.in"""
        found = 0
        
        for page in range(1, 6):  # Check first 5 pages
            if found >= num_needed:
                break
                
            try:
                url = f"https://streamtest.in/logs/page/{page}"
                if channel_name:
                    url += f"?filter={channel_name}"
                
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Find stream URLs
                stream_divs = soup.find_all('div', {'class': 'url'})
                
                for div in stream_divs:
                    if found >= num_needed:
                        break
                    
                    link = div.text.strip()
                    if link and (link.startswith('http') or link.startswith('rtmp')):
                        
                        # Try to get channel name
                        title_div = div.find_previous('div', {'class': 'title'})
                        title = title_div.text.strip() if title_div else 'Stream'
                        
                        print(colored(f"[*] Found: {title}", "white"))
                        print(colored(f"[*] Testing: {link[:60]}...", "white"), end=" ")
                        
                        if self.test_iptv_link(link):
                            print(colored("✓ WORKING", "green"))
                            self.scraped_links.append({
                                'title': title,
                                'url': link
                            })
                            found += 1
                        else:
                            print(colored("✗ Failed", "red"))
                            
            except Exception as e:
                continue
        
        return found
    
    def scrape_links(self, channel_name, num_links, nsfw_mode=False):
        """Scrape IPTV links from multiple sources with multi-threading"""
        working_links_found = 0
        
        # Expand search terms
        search_terms = self.expand_search_terms(channel_name) if channel_name else ['']
        
        # Add NSFW filter message
        if nsfw_mode:
            print(colored(f"\n{'='*60}", "magenta"))
            print(colored(f"[18+] NSFW MODE - Searching adult content", "magenta"))
        else:
            print(colored(f"\n{'='*60}", "cyan"))
        
        print(colored(f"[*] Searching for IPTV links for: {channel_name or 'all channels'}", "yellow"))
        
        if len(search_terms) > 1:
            print(colored(f"[*] Expanded search terms: {', '.join(search_terms[:5])}", "cyan"))
            if len(search_terms) > 5:
                print(colored(f"    + {len(search_terms) - 5} more related terms...", "cyan"))
        
        print(colored(f"[*] Target: {num_links} working link(s)", "cyan"))
        print(colored(f"[*] Using multi-threaded scraping for faster results", "yellow"))
        print(colored(f"{'='*60}\n", "cyan"))
        
        # Get M3U sources (prioritize NSFW if in NSFW mode)
        spinner = Spinner("Loading M3U sources", "cyan")
        spinner.start()
        
        if nsfw_mode:
            m3u_sources = self.get_nsfw_sources()
            spinner.stop(colored(f"[✓] Loaded {len(m3u_sources)} NSFW sources", "magenta"))
        else:
            m3u_sources = self.get_all_sources()
            spinner.stop(colored(f"[✓] Loaded {len(m3u_sources)} M3U sources", "green"))
        
        # Add GitHub discovered sources
        if not nsfw_mode:  # Skip GitHub for NSFW
            spinner = Spinner("Searching GitHub repositories", "yellow")
            spinner.start()
            github_sources = self.search_github_repos()
            if github_sources:
                m3u_sources.extend(github_sources)
                spinner.stop(colored(f"[✓] Found {len(github_sources)} additional GitHub sources", "green"))
            else:
                spinner.stop(colored(f"[*] GitHub search complete", "cyan"))
        
        total_sources = len(m3u_sources)
        links_to_test = []
        
        # Phase 1: Collect all matching links from sources
        print(colored(f"\n[Phase 1/2] Collecting links from {total_sources} sources...", "yellow"))
        
        for idx, source_url in enumerate(m3u_sources, 1):
            # Check for shutdown
            if self.shutdown_flag.is_set():
                print(colored("\n[!] Stopping collection due to user interrupt...", "yellow"))
                break
                
            source_name = source_url.split('/')[-2] if '/' in source_url else source_url[:30]
            print(colored(f"[{idx}/{total_sources}] ", "cyan") + colored(f"{source_name}...", "white"), end=" ")
            
            try:
                response = requests.get(source_url, timeout=15)
                if response.status_code != 200:
                    print(colored("✗ Failed", "red"))
                    continue
                
                content = response.text
                lines = content.split('\n')
                current_name = ""
                source_matches = 0
                
                for line in lines:
                    # Check for shutdown in inner loop
                    if self.shutdown_flag.is_set():
                        break
                        
                    line = line.strip()
                    
                    if line.startswith('#EXTINF'):
                        current_name = line.split(',')[-1].strip() if ',' in line else ""
                        
                    elif line and not line.startswith('#') and (line.startswith('http') or line.startswith('rtmp')):
                        # Check if line matches any search term
                        matches_search = False
                        if not channel_name:
                            matches_search = True
                        else:
                            combined_text = (current_name + ' ' + line).lower()
                            for term in search_terms:
                                if term in combined_text:
                                    matches_search = True
                                    break
                        
                        if matches_search:
                            links_to_test.append({
                                'url': line,
                                'title': current_name if current_name else 'Stream'
                            })
                            source_matches += 1
                        
                        current_name = ""
                
                print(colored(f"✓ {source_matches} found", "green"))
            
            except KeyboardInterrupt:
                print(colored("\n[!] Interrupted during collection", "yellow"))
                raise
            except Exception as e:
                print(colored("✗ Error", "red"))
        
        # Check if interrupted before testing
        if self.shutdown_flag.is_set():
            print(colored("\n[!] Operation interrupted. Exiting...", "yellow"))
            return 0
            
        print(colored(f"\n[✓] Collected {len(links_to_test)} potential links", "green"))
        
        if not links_to_test:
            print(colored(f"\n[!] No matching links found. Try different search terms.", "red"))
            return 0
        
        # Phase 2: Test links with multi-threading
        print(colored(f"\n[Phase 2/2] Testing links with 5 concurrent threads...\n", "yellow"))
        
        def test_link_wrapper(link_data):
            """Wrapper for thread-safe link testing"""
            # Check if shutdown requested
            if self.shutdown_flag.is_set():
                return False
                
            url = link_data['url']
            title = link_data['title']
            
            with self.lock:
                current_count = self.total_tested
                
            if self.test_iptv_link(url):
                with self.lock:
                    self.total_working += 1
                    working_count = self.total_working
                    self.scraped_links.append({'title': title, 'url': url})
                
                print(colored(f"[✓ {working_count}/{num_links}] {title[:50]}", "green"))
                return True
            else:
                print(colored(f"[✗ {current_count}] {title[:50]}", "red"))
                return False
        
        # Use ThreadPoolExecutor for parallel testing (25 workers for maximum speed)
        try:
            with ThreadPoolExecutor(max_workers=25) as executor:
                futures = {executor.submit(test_link_wrapper, link): link for link in links_to_test}
                
                for future in as_completed(futures):
                    # Check for shutdown flag
                    if self.shutdown_flag.is_set():
                        # Cancel all remaining futures
                        for f in futures:
                            f.cancel()
                        print(colored("\n[!] Stopping due to user interrupt...", "yellow"))
                        break
                        
                    with self.lock:
                        if self.total_working >= num_links:
                            # Cancel remaining futures
                            for f in futures:
                                f.cancel()
                            break
        except KeyboardInterrupt:
            self.shutdown_flag.set()
            print(colored("\n[!] Interrupted by user. Cleaning up...", "yellow"))
            raise
        
        # If not enough found, try advanced scraping methods
        if self.total_working < num_links and not nsfw_mode:
            remaining = num_links - self.total_working
            
            # Try albaplayer platforms first (especially for BeIN Sports and Arabic sports)
            if any(keyword in channel_name.lower() for keyword in ['bein', 'ad-sport', 'ssc', 'sport', 'arabic', 'dazn', 'sky']) and not self.shutdown_flag.is_set():
                print(colored(f"\n[Advanced Scraping] Checking albaplayer platforms (alkoora.live, yalllashoot.today)...", "yellow"))
                try:
                    alba_results = self.scrape_albaplayer_channels(remaining)
                    if alba_results:
                        for result in alba_results:
                            if self.shutdown_flag.is_set():
                                break
                            with self.lock:
                                self.scraped_links.append(result)
                                self.total_working += 1
                                print(colored(f"[✓] {result['title']}", "green"))
                                if self.total_working >= num_links:
                                    break
                except Exception as e:
                    pass
            
            # Try match streaming sites (especially for sports channels)
            if self.total_working < num_links and not self.shutdown_flag.is_set() and any(sport in channel_name.lower() for sport in ['sport', 'bein', 'espn', 'sky', 'match', 'league', 'football', 'soccer', 'nba', 'nfl']):
                print(colored(f"\n[Advanced Scraping] Checking live match streaming sites...", "yellow"))
                try:
                    match_results = self.scrape_match_streaming_sites(channel_name, num_links - self.total_working)
                    if match_results:
                        for result in match_results:
                            if self.shutdown_flag.is_set():
                                break
                            with self.lock:
                                self.scraped_links.append(result)
                                self.total_working += 1
                                print(colored(f"[✓] {result['title']}", "green"))
                                if self.total_working >= num_links:
                                    break
                except Exception as e:
                    pass
            
            # Try IPTV-Cat scraping
            if self.total_working < num_links and not self.shutdown_flag.is_set():
                print(colored(f"\n[Advanced Scraping] Trying IPTV-Cat website...", "yellow"))
                try:
                    iptv_cat_results = self.scrape_iptv_cat(channel_name, num_links - self.total_working)
                    if iptv_cat_results:
                        for result in iptv_cat_results:
                            if self.shutdown_flag.is_set():
                                break
                            with self.lock:
                                self.scraped_links.append(result)
                                self.total_working += 1
                                print(colored(f"[✓] {result['title']}", "green"))
                                if self.total_working >= num_links:
                                    break
                except Exception as e:
                    pass
            
            # Try live TV websites
            if self.total_working < num_links and not self.shutdown_flag.is_set():
                print(colored(f"\n[Advanced Scraping] Checking live TV websites...", "yellow"))
                try:
                    tv_results = self.scrape_live_tv_websites(channel_name, num_links - self.total_working)
                    if tv_results:
                        for result in tv_results:
                            if self.shutdown_flag.is_set():
                                break
                            with self.lock:
                                self.scraped_links.append(result)
                                self.total_working += 1
                                print(colored(f"[✓] {result['title']}", "green"))
                                if self.total_working >= num_links:
                                    break
                except Exception as e:
                    pass
            
            # Try pastebin sites
            if self.total_working < num_links and not self.shutdown_flag.is_set():
                print(colored(f"\n[Advanced Scraping] Searching pastebin and paste sites...", "yellow"))
                try:
                    paste_results = self.scrape_pastebin_sites(channel_name, num_links - self.total_working)
                    if paste_results:
                        for result in paste_results:
                            if self.shutdown_flag.is_set():
                                break
                            with self.lock:
                                self.scraped_links.append(result)
                                self.total_working += 1
                                print(colored(f"[✓] {result['title']}", "green"))
                                if self.total_working >= num_links:
                                    break
                except Exception as e:
                    pass
            
            # Try IP range scanning if we found an IP-based link
            if self.total_working < num_links and self.scraped_links:
                for link in self.scraped_links:
                    # Extract IP if present
                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.)\d{1,3}', link['url'])
                    if ip_match:
                        base_ip = ip_match.group(1) + '1'
                        print(colored(f"\n[Advanced Scraping] Scanning IP range {ip_match.group(1)}x...", "yellow"))
                        try:
                            ip_results = self.scan_ip_range_for_streams(base_ip, channel_name, num_links - self.total_working)
                            if ip_results:
                                for result in ip_results:
                                    with self.lock:
                                        self.scraped_links.append(result)
                                        self.total_working += 1
                                        if self.total_working >= num_links:
                                            break
                        except Exception as e:
                            pass
                        break
        
        # Final results
        print(colored(f"\n{'='*60}", "green" if self.total_working > 0 else "red"))
        if self.total_working == 0:
            print(colored(f"[!] No working links found. Try different search terms.", "red"))
            print(colored(f"[*] Tested {self.total_tested} URLs across {total_sources} sources", "yellow"))
        else:
            print(colored(f"[✓] SUCCESS! Found {self.total_working} working link(s)!", "green"))
            print(colored(f"[*] Tested {self.total_tested} URLs total", "cyan"))
        print(colored(f"{'='*60}\n", "cyan"))
        
        return self.total_working
        print(colored(f"{'='*60}\n", "cyan"))
        
        return working_links_found
    
    def save_m3u(self, filename, auto_save=False):
        """Save scraped links to M3U file"""
        if not auto_save:
            save_choice = input(colored("\n[?] Do you want to save the scraped links? (Y/n): ", "yellow")).strip().lower()
            if save_choice == 'n':
                print(colored("[!] Files not saved.", "red"))
                return
        
        x = datetime.datetime.now()
        folder_name = x.strftime('%d-%m-%Y')
        
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            print(colored(f"[*] Created folder: {folder_name}", "cyan"))
        
        filepath = os.path.join(folder_name, f"{x.strftime('%I-%M-%S-%p')} {filename.upper()}.m3u")
        
        print(colored("[*] Creating m3u file..........", "yellow"))
        
        try:
            with open(filepath, "w", encoding="utf-8") as m3u_file:
                m3u_file.write("#EXTM3U\n\n")
                
                for link_data in self.scraped_links:
                    if isinstance(link_data, dict):
                        title = link_data.get('title', 'Stream')
                        url = link_data.get('url', '')
                        m3u_file.write(f"#EXTINF:-1,{title}\n")
                        m3u_file.write(f"{url}\n")
                    else:
                        m3u_file.write(f"#EXTINF:-1,Stream\n")
                        m3u_file.write(f"{link_data}\n")
            
            print(colored(f"[✓] Created m3u file: {filepath}", "green"))
            print(colored(f"[✓] Total links saved: {len(self.scraped_links)}", "green"))
            
        except Exception as e:
            print(colored(f"[!] Error creating m3u file: {str(e)}", "red"))


def update_cli():
    """Update the IPTV scraper CLI to the latest version"""
    art = text2art("IPTV Updater")
    print(colored(art, "cyan"))
    print(colored("Updating IPTV Scraper...", "yellow"))
    print()
    
    try:
        # Try to find the source directory (where setup.py is)
        # First check if we're in editable mode
        install_dir = r"C:\Users\MSI\Desktop\IPTV-SCRAPPER"
        
        # Verify setup.py exists
        if not os.path.exists(os.path.join(install_dir, "setup.py")):
            # If not found in default location, try to find it
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if os.path.exists(os.path.join(current_dir, "setup.py")):
                install_dir = current_dir
            else:
                raise FileNotFoundError("Could not find source directory with setup.py")
        
        print(colored(f"[*] Source directory: {install_dir}", "cyan"))
        print(colored("[*] Running update...", "yellow"))
        print()
        
        # Update using pip
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall", install_dir],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            from iptv_scraper import __version__
            print(colored("\n[✓] Update completed successfully!", "green"))
            print(colored(f"[✓] IPTV Scraper v{__version__} is now up to date!", "green"))
        else:
            print(colored("\n[!] Update failed!", "red"))
            print(colored(f"Error: {result.stderr}", "red"))
            return 1
            
    except Exception as e:
        print(colored(f"\n[!] Update failed: {str(e)}", "red"))
        print(colored("\n[*] Manual update:", "yellow"))
        print(colored("  cd C:\\Users\\MSI\\Desktop\\IPTV-SCRAPPER", "white"))
        print(colored("  pip install --upgrade --force-reinstall .", "white"))
        return 1
    
    return 0


def show_popular_channels():
    """Display list of popular channels that can be searched"""
    art = text2art("CHANNELS", font="block")
    print(colored(art, "cyan"))
    print(colored("═" * 70, "yellow"))
    print(colored("  📺 Popular Channels You Can Search For", "green"))
    print(colored("═" * 70, "yellow"))
    print()
    
    channels = {
        "Sports": ["BeIN Sports", "ESPN", "Sky Sports", "DAZN", "Fox Sports", "NBC Sports", 
                   "TNT Sports", "Eurosport", "NBA TV", "NFL Network"],
        "Kids": ["Cartoon Network", "Disney Channel", "Nickelodeon", "Disney Junior", 
                 "Nick Jr", "Boomerang", "Disney XD", "Nicktoons"],
        "News": ["CNN", "BBC News", "Fox News", "MSNBC", "Al Jazeera", "Sky News", 
                 "CNBC", "Bloomberg"],
        "Entertainment": ["HBO", "Showtime", "AMC", "FX", "TNT", "USA Network", 
                         "Bravo", "E!", "TBS", "Comedy Central"],
        "Documentary": ["Discovery Channel", "National Geographic", "History Channel", 
                       "Animal Planet", "Discovery Science", "Nat Geo Wild"],
        "Lifestyle": ["Food Network", "HGTV", "TLC", "Travel Channel", "Lifetime"],
        "Arabic": ["MBC", "OSN", "Rotana", "Al Arabiya", "Dubai TV", "Abu Dhabi TV"],
    }
    
    for category, channel_list in channels.items():
        print(colored(f"  {category}:", "green"))
        for i in range(0, len(channel_list), 3):
            row = channel_list[i:i+3]
            formatted_row = "    " + " | ".join(f"{ch:20}" for ch in row)
            print(colored(formatted_row, "white"))
        print()
    
    print(colored("=" * 60, "cyan"))
    print(colored("\nHow to use:", "yellow"))
    print(colored("  ipsc -c \"cartoon network\" -n 10", "white"))
    print(colored("  ipsc -c \"cnn\" -n 15", "white"))
    print(colored("  ipsc -c \"discovery\" -n 20", "white"))
    print()
    return 0


def main():
    # Global shutdown flag for signal handling
    shutdown_requested = threading.Event()
    scraper_instance = None  # Store scraper instance for signal handler
    current_channel = None   # Store channel name for saving
    
    def signal_handler(sig, frame):
        """Handle Ctrl+C gracefully and save working links"""
        if not shutdown_requested.is_set():
            shutdown_requested.set()
            print(colored("\n\n[!] Ctrl+C detected. Stopping and saving...", "yellow"))
            
            # Auto-save working links if any exist
            if scraper_instance and scraper_instance.scraped_links:
                print(colored(f"[*] Saving {len(scraper_instance.scraped_links)} working link(s)...", "cyan"))
                output_name = current_channel if current_channel else "interrupted_search"
                scraper_instance.save_m3u(output_name, auto_save=True)
                print(colored("[✓] Links saved successfully!", "green"))
            else:
                print(colored("[*] No working links to save.", "yellow"))
            
            sys.exit(0)
        else:
            # Force exit on second Ctrl+C
            print(colored("\n[!] Force stopping...", "red"))
            os._exit(1)
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(
        description="IPTV Scraper - Find and validate working IPTV links",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-c', '--channel',
        type=str,
        default='',
        help='Channel name to search for (leave empty for all channels)'
    )
    
    parser.add_argument(
        '-n', '--number',
        type=int,
        default=None,
        help='Number of working links to find'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output filename (without extension)'
    )
    
    parser.add_argument(
        '--auto-save',
        action='store_true',
        help='Automatically save without prompting'
    )
    
    parser.add_argument(
        '--nsfw',
        action='store_true',
        help='Search for adult/NSFW content only'
    )
    
    parser.add_argument(
        '--live-match',
        action='store_true',
        help='Search for live sports match streams (soccer, basketball, etc.)'
    )
    
    parser.add_argument(
        '--popular-channels',
        action='store_true',
        help='Show list of popular searchable channels'
    )
    
    parser.add_argument(
        '--update',
        action='store_true',
        help='Update IPTV Scraper to the latest version'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='store_true',
        help='Show version information'
    )
    
    args = parser.parse_args()
    
    # Handle version command
    if args.version:
        from iptv_scraper import __version__
        art = text2art("IPTV SCRAPER", font="block")
        print(colored(art, "cyan"))
        print(colored("═" * 70, "yellow"))
        print(colored(f"  Version: {__version__} | Advanced Multi-Source Stream Finder", "green"))
        print(colored("  ⚡ 5x Performance | 🔄 Connection Pooling | 🧠 Smart Filtering", "cyan"))
        print(colored("═" * 70, "yellow"))
        print(colored(f"  Developed by Musashi (MSXI:7050)", "magenta"))
        print()
        print(colored("Alias commands:", "yellow"))
        print(colored("  iptv-scraper  (full name)", "white"))
        print(colored("  ipsc          (short name)", "white"))
        print()
        print(colored("For help: iptv-scraper --help", "cyan"))
        return 0
    
    # Handle popular channels command
    if args.popular_channels:
        return show_popular_channels()
    
    # Handle update command
    if args.update:
        return update_cli()
    
    # Show banner
    art = text2art("IPTV  SCRAPER", font="block")
    print(colored(art, "cyan"))
    print(colored("═" * 70, "yellow"))
    print(colored("        🎬 Advanced Multi-Source Stream Finder v2.7.0", "green"))
    print(colored("        ⚡ 25 Parallel Workers | 🔄 Connection Pooling | 🧠 Smart Filtering", "cyan"))
    print(colored("═" * 70, "yellow"))
    print(colored("        Developed By MSXI:7050", "magenta"))
    print()
    
    try:
        # Handle live match mode
        if args.live_match:
            print(colored("⚽ Live Match Mode Activated", "green"))
            print(colored("[*] Searching for live sports match streams...", "yellow"))
            print()
            
            # Get inputs for live match
            if args.channel is None:
                channel_name = input("Sport/Team to search (e.g., 'bein', 'premier league', 'nba'): ")
            else:
                channel_name = args.channel
                print(f"Sport/Team: {channel_name}")
            
            if args.number is None:
                num_links = int(input("How many working streams to find: "))
            else:
                num_links = args.number
                print(f"Number of streams: {num_links}")
            
            # Create scraper and directly scrape match sites
            scraper = IPTVScraper()
            scraper_instance = scraper  # Store for signal handler
            current_channel = channel_name  # Store channel name
            print(colored(f"\n{'='*60}", "green"))
            print(colored(f"[*] Searching live match streaming sites...", "yellow"))
            print(colored(f"{'='*60}\n", "green"))
            
            # First try albaplayer platforms (great for BeIN and sports)
            alba_results = scraper.scrape_albaplayer_channels(num_links)
            scraper.scraped_links.extend(alba_results)
            scraper.total_working = len(scraper.scraped_links)
            
            # If not enough, scrape match sites
            if len(scraper.scraped_links) < num_links:
                match_results = scraper.scrape_match_streaming_sites(channel_name or "", num_links - len(scraper.scraped_links))
                scraper.scraped_links.extend(match_results)
                scraper.total_working = len(scraper.scraped_links)
            
            # If not enough, fallback to regular scraping
            if len(scraper.scraped_links) < num_links:
                print(colored(f"\n[*] Found {len(scraper.scraped_links)} streams, searching additional sources...", "yellow"))
                scraper.scrape_links(channel_name, num_links, nsfw_mode=False)
            
            found = len(scraper.scraped_links)
            
        # Handle NSFW mode
        elif args.nsfw:
            print(colored("[18+] NSFW Mode Activated", "magenta"))
            print(colored("[*] Searching for adult content only...", "yellow"))
            print()
            channel_name = "adult"  # Default search term for NSFW
            if args.channel:
                channel_name = args.channel  # Allow custom NSFW search term
        else:
            # Get inputs
            if args.channel is None:
                channel_name = input("Channel to search (or leave empty for all): ")
            else:
                channel_name = args.channel
                if channel_name:
                    print(f"Channel: {channel_name}")
        
        if args.number is None and not args.live_match:
            num_links = int(input("How many working links to find: "))
        else:
            if not args.live_match:
                num_links = args.number
                print(f"Number of links: {num_links}")
        
        # Create scraper and run (skip if already done in live-match mode)
        if not args.live_match:
            scraper = IPTVScraper()
            scraper_instance = scraper  # Store for signal handler
            current_channel = channel_name  # Store channel name
            found = scraper.scrape_links(channel_name, num_links, nsfw_mode=args.nsfw)
        
        # Save results
        if scraper.scraped_links:
            output_name = args.output if args.output else (channel_name if channel_name else "all_channels")
            scraper.save_m3u(output_name, auto_save=args.auto_save)
        else:
            print(colored("[!] No links to save.", "red"))
    
    except KeyboardInterrupt:
        print(colored("\n\n[!] Operation canceled by user.", "red"))
        print(colored("[*] Exiting gracefully...", "yellow"))
        sys.exit(0)
    except ValueError as e:
        print(colored(f"[!] Invalid input: {e}", "red"))
        exit(1)


if __name__ == "__main__":
    main()