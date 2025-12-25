import requests
from bs4 import BeautifulSoup
from art import text2art
from colorama import init
from termcolor import colored
import datetime
import re
import os

# Store links as dict with metadata
Scraped_Links = []


def m3u_Creator(fname):
    # Ask user if they want to save
    save_choice = input(colored("\n[?] Do you want to save the scraped links? (Y/n): ", "yellow")).strip().lower()
    
    if save_choice == 'n':
        print(colored("[!] Files not saved.", "red"))
        return
    
    x = datetime.datetime.now()
    
    # Create folder named by date
    folder_name = x.strftime('%d-%m-%Y')
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(colored(f"[*] Created folder: {folder_name}", "cyan"))
    
    # Create filename with time
    filename = os.path.join(folder_name, f"{x.strftime('%I-%M-%S-%p')} {fname.upper()}.m3u")

    print(colored("[*] Creating m3u file..........", "yellow"))
    
    try:
        with open(filename, "w", encoding="utf-8") as m3u_file:
            # Write M3U header (required, must be first line)
            m3u_file.write("#EXTM3U\n\n")
            
            # Write each link in proper M3U format
            for link_data in Scraped_Links:
                if isinstance(link_data, dict):
                    # Structured data with metadata
                    title = link_data.get('title', 'Stream')
                    url = link_data.get('url', '')
                    # EXTINF format: #EXTINF:duration,title
                    # -1 means unknown/infinite duration (for streams)
                    m3u_file.write(f"#EXTINF:-1,{title}\n")
                    m3u_file.write(f"{url}\n")
                else:
                    # Plain URL string (backward compatibility)
                    m3u_file.write(f"#EXTINF:-1,Stream\n")
                    m3u_file.write(f"{link_data}\n")
        
        print(colored(f"[✓] Created m3u file: {filename}", "green"))
        print(colored(f"[✓] Total links saved: {len(Scraped_Links)}", "green"))
        
    except Exception as e:
        print(colored(f"[!] Error creating m3u file: {str(e)}", "red"))


init()


def test_iptv_link(link, timeout=8):
    """Test if an IPTV link is actually playable"""
    try:
        headers = {
            'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18',
            'Accept': '*/*'
        }
        
        response = requests.get(link, timeout=timeout, stream=True, allow_redirects=True, headers=headers)
        
        if response.status_code != 200:
            return False
        
        content_type = response.headers.get('content-type', '').lower()
        
        # For M3U8 playlists, validate the content
        if link.endswith('.m3u8') or link.endswith('.m3u') or 'mpegurl' in content_type:
            # Read the playlist content
            try:
                content = response.text if hasattr(response, 'text') else next(response.iter_content(8192)).decode('utf-8', errors='ignore')
                
                # Check if it's a valid M3U8 playlist
                if '#EXTM3U' not in content and 'http' not in content:
                    return False
                
                # Check if playlist has actual stream URLs
                lines = content.split('\n')
                has_stream_url = False
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and ('http' in line or line.endswith('.ts')):
                        has_stream_url = True
                        break
                
                return has_stream_url
                
            except:
                return False
        
        # For direct streams, check if we can read data
        elif 'video' in content_type or 'stream' in content_type or 'octet-stream' in content_type:
            chunk = next(response.iter_content(8192), None)
            return chunk is not None and len(chunk) > 0
        
        return False
        
    except requests.exceptions.Timeout:
        return False
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return False


def random_iptv(no, name):
    working_links_found = 0
    
    print(colored(f"[*] Searching for IPTV links for: {name}", "yellow"))
    
    # Use iptv-org GitHub repository - a reliable source
    m3u_sources = [
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams.m3u",
        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
        "https://raw.githubusercontent.com/iptv-org/iptv/master/channels.m3u"
    ]
    
    for source_url in m3u_sources:
        if working_links_found >= no:
            break
            
        print(colored(f"[*] Fetching from source: {source_url.split('/')[-2]}...", "cyan"))
        
        try:
            response = requests.get(source_url, timeout=15)
            if response.status_code != 200:
                print(colored(f"[!] Failed to fetch from {source_url}", "red"))
                continue
            
            content = response.text
            
            # Parse M3U format
            lines = content.split('\n')
            current_name = ""
            
            for line in lines:
                line = line.strip()
                
                # Check if it's an info line
                if line.startswith('#EXTINF'):
                    # Extract channel name
                    current_name = line.split(',')[-1].strip() if ',' in line else ""
                    
                # Check if it's a stream URL
                elif line and not line.startswith('#') and (line.startswith('http') or line.startswith('rtmp')):
                    # Filter by channel name if specified
                    if not name or name.lower() in current_name.lower() or name.lower() in line.lower():
                        
                        print(colored(f"[*] Found: {current_name or line[:50]}", "white"))
                        print(colored(f"[*] Testing: {line[:60]}...", "white"), end=" ")
                        
                        if test_iptv_link(line):
                            print(colored("✓ WORKING", "green"))
                            # Save with metadata as dict
                            Scraped_Links.append({
                                'title': current_name if current_name else 'Stream',
                                'url': line
                            })
                            working_links_found += 1
                            
                            if working_links_found >= no:
                                print(colored(f"\n[✓] Found {working_links_found} working link(s)!", "green"))
                                return
                        else:
                            print(colored("✗ Failed", "red"))
                    
                    current_name = ""  # Reset for next entry
        
        except Exception as e:
            print(colored(f"[!] Error fetching from {source_url}: {str(e)}", "red"))
    
    if working_links_found == 0:
        print(colored(f"[!] No working links found. Try a different search term.", "red"))
    else:
        print(colored(f"\n[✓] Found {working_links_found} working link(s)!", "green"))


art = text2art("IPTV Scraper")
print(colored(art, "red"))
print(colored("Developed By Musashi", "cyan"))

try:
    channel_name = input("Channel to search (or leave empty for all): ")
    no_of_links = int(input("How many working links to find: "))

    random_iptv(no_of_links, channel_name)

    if Scraped_Links:
        m3u_Creator(channel_name if channel_name else "all_channels")
    else:
        print(colored("[!] No links to save.", "red"))
        
except KeyboardInterrupt:
    print(colored("\n\n[!] The operation is canceled by the user.", "red"))
    exit(0)