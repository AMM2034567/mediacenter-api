import urllib.request
import json

def test_netease():
    print("=== Testing NetEase Cloud Music ===")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    try:
        req = urllib.request.Request('https://music.163.com/api/playlist/detail?id=3778678', headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            tracks = data.get('result', {}).get('tracks', [])
            print(f"NetEase Hot Songs count: {len(tracks)}")
            if tracks:
                first = tracks[0]
                ar_name = first.get('artists', [{}])[0].get('name') if first.get('artists') else '未知'
                print(f"  First: {first.get('name')} - {ar_name}, ID: {first.get('id')}")
                song_id = first.get('id')
                
                # Check play url
                play_url = f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"
                req2 = urllib.request.Request(play_url, headers=headers)
                try:
                    with urllib.request.urlopen(req2, timeout=6) as r2:
                        print(f"  Play URL: {r2.url}")
                        print(f"  Status: {r2.status}, Type: {r2.headers.get('content-type')}, Size: {r2.headers.get('content-length')}")
                except Exception as e:
                    print(f"  Play URL error: {e}")
                    
                # Check lyric
                req3 = urllib.request.Request(f"https://music.163.com/api/song/lyric?os=pc&id={song_id}&lv=-1&kv=-1&tv=-1", headers=headers)
                with urllib.request.urlopen(req3, timeout=6) as r3:
                    lrc_data = json.loads(r3.read().decode('utf-8'))
                    lrc = lrc_data.get('lrc', {}).get('lyric', '')
                    print(f"  Lyric preview: {repr(lrc[:80]) if lrc else 'None'}")
    except Exception as e:
        print(f"NetEase error: {e}")

def test_kugou():
    print("\n=== Testing KuGou Music ===")
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'}
    try:
        # Search API
        req = urllib.request.Request('http://mobilecdn.kugou.com/api/v3/search/song?format=json&keyword=%E5%91%A8%E6%9D%B0%E4%BC%A6&page=1&pagesize=5', headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            songs = data.get('data', {}).get('info', [])
            print(f"KuGou Search results: {len(songs)}")
            if songs:
                first = songs[0]
                hash_val = first.get('hash')
                print(f"  Song: {first.get('songname')} - {first.get('singername')}, Hash: {hash_val}")
                
                # Get song detail & play url
                req2 = urllib.request.Request(f"https://m.kugou.com/app/i/getSongInfo.php?cmd=playInfo&hash={hash_val}", headers=headers)
                with urllib.request.urlopen(req2, timeout=6) as r2:
                    info = json.loads(r2.read().decode('utf-8'))
                    print(f"  KuGou play url: {info.get('url')[:60] if info.get('url') else 'None'}")
                    print(f"  Img: {info.get('imgUrl')}")
    except Exception as e:
        print(f"KuGou error: {e}")

if __name__ == '__main__':
    test_netease()
    test_kugou()
