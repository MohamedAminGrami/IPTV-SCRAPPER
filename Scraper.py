#!/usr/bin/env python3
"""
IPTV Scraper - Standalone Script
A simple standalone script for quick IPTV link scraping.
For full features, use the CLI: iptv-scraper or ipsc

Author: Musashi
License: MIT
"""

import requests
from art import text2art
from colorama import init
from termcolor import colored
import datetime
import os

# Initialize colorama for Windows support
init()

# Store scraped links with metadata
scraped_links = []


def test_iptv_link(link, timeout=8):
    """Test if an IPTV link is actually playable."""
    try:
        headers = {
            'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18',
            'Accept': '*/*'
        }
        
        response = requests.get(
            link, 
            timeout=timeout, 
            stream=True, 
            allow_redirects=True, 
            headers=headers
        )
        
        if response.status_code != 200:
            return False
        
        content_type = response.headers.get('content-type', '').lower()
        
        # Validate M3U8 playlists
        if link.endswith('.m3u8') or link.endswith('.m3u') or 'mpegurl' in content_type:
            try:
                content = next(response.iter_content(8192)).decode('utf-8', errors='ignore')
                
                if '#EXTM3U' not in content:
                    return False
                
                # Check for actual stream URLs
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#') and ('http' in line or line.endswith('.ts')):
                        return True
                return False
            except:
                return False
        
        # Validate direct streams
        elif 'video' in content_type or 'stream' in content_type or 'octet-stream' in content_type:
            chunk = next(response.iter_content(8192), None)
            return chunk is not None and len(chunk) > 0
        
        return False
        
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return False
    except Exception:
        return False


def save_m3u(filename):
    """Save scraped links to M3U file."""
    save_choice = input(colored("\n[?] Save the scraped links? (Y/n): ", "yellow")).strip().lower()
    
    if save_choice == 'n':
        print(colored("[!] Files not saved.", "red"))
        return
    
    now = datetime.datetime.now()
    folder_name = now.strftime('%d-%m-%Y')
    
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(colored(f"[*] Created folder: {folder_name}", "cyan"))
    
    filepath = os.path.join(folder_name, f"{now.strftime('%I-%M-%S-%p')} {filename.upper()}.m3u")
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            
            for link_data in scraped_links:
                if isinstance(link_data, dict):
                    title = link_data.get('title', 'Stream')
                    url = link_data.get('url', '')
                    f.write(f"#EXTINF:-1,{title}\n{url}\n")
                else:
                    f.write(f"#EXTINF:-1,Stream\n{link_data}\n")
        
        print(colored(f"[✓] Saved: {filepath}", "green"))
        print(colored(f"[✓] Total links: {len(scraped_links)}", "green"))
        
    except Exception as e:
        print(colored(f"[!] Error saving: {e}", "red"))


def scrape_iptv(num_links, channel_name=""):
    """Scrape IPTV links from public sources."""
    working_count = 0
    
    print(colored(f"[*] Searching for: {channel_name or 'all channels'}", "yellow"))
    
    sources = [
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams.m3u",
        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    ]
    
    for source_url in sources:
        if working_count >= num_links:
            break
            
        print(colored(f"[*] Fetching: {source_url.split('/')[-2]}...", "cyan"))
        
        try:
            response = requests.get(source_url, timeout=15)
            if response.status_code != 200:
                continue
            
            current_name = ""
            
            for line in response.text.split('\n'):
                line = line.strip()
                
                if line.startswith('#EXTINF'):
                    current_name = line.split(',')[-1].strip() if ',' in line else ""
                    
                elif line and not line.startswith('#') and line.startswith(('http', 'rtmp')):
                    # Filter by channel name
                    if not channel_name or channel_name.lower() in current_name.lower() or channel_name.lower() in line.lower():
                        print(colored(f"[*] Testing: {current_name or line[:50]}...", "white"), end=" ")
                        
                        if test_iptv_link(line):
                            print(colored("✓ WORKING", "green"))
                            scraped_links.append({
                                'title': current_name or 'Stream',
                                'url': line
                            })
                            working_count += 1
                            
                            if working_count >= num_links:
                                break
                        else:
                            print(colored("✗ Failed", "red"))
                    
                    current_name = ""
                    
        except Exception as e:
            print(colored(f"[!] Error: {e}", "red"))
    
    if working_count == 0:
        print(colored("[!] No working links found. Try different search term.", "red"))
    else:
        print(colored(f"\n[✓] Found {working_count} working link(s)!", "green"))


def main():
    """Main entry point."""
    # Display banner
    print(colored(text2art("IPTV Scraper"), "red"))
    print(colored("Developed by Musashi", "cyan"))
    print(colored("For full features, install with: pip install .\n", "yellow"))
    
    try:
        channel = input("Channel to search (or leave empty for all): ").strip()
        num_links = int(input("How many working links to find: "))
        
        scrape_iptv(num_links, channel)
        
        if scraped_links:
            save_m3u(channel or "all_channels")
            
    except KeyboardInterrupt:
        print(colored("\n[!] Cancelled by user.", "red"))
    except ValueError:
        print(colored("[!] Please enter a valid number.", "red"))


if __name__ == "__main__":
    main()
