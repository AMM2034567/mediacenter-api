import asyncio
import json
import httpx

CHINESE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; MI 6; Build/QQ3A.200805.001) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "X-Forwarded-For": "116.25.146.177",  # 广东深圳电信国内 IP
    "X-Real-IP": "116.25.146.177",
    "Client-IP": "116.25.146.177",
    "X-Client-IP": "116.25.146.177",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "application/json, text/plain, */*",
}

async def check_audio_stream(client: httpx.AsyncClient, url: str):
    """验证音频流真实可用性（HEAD 或 GET 范围探测）"""
    if not url or not url.startswith("http"):
        return False, "Invalid URL"
    try:
        resp = await client.head(url, timeout=5.0, follow_redirects=True)
        ct = resp.headers.get("content-type", "")
        cl = resp.headers.get("content-length", "0")
        if resp.status_code in (200, 206) and ("audio" in ct or "mpeg" in ct or "octet-stream" in ct or int(cl) > 50000):
            return True, f"OK ({ct}, {int(cl)//1024}KB)"
        # 降级尝试 Range GET
        resp_get = await client.get(url, headers={"Range": "bytes=0-1024"}, timeout=5.0, follow_redirects=True)
        ct_get = resp_get.headers.get("content-type", "")
        if resp_get.status_code in (200, 206):
            return True, f"OK (Range 206, {ct_get}, len={len(resp_get.content)}B)"
        return False, f"HTTP {resp.status_code} ({ct})"
    except Exception as e:
        return False, str(e)

async def test_qq_tang_api(client: httpx.AsyncClient):
    print("\n--- 1. 测试 QQ 音乐：唐接口 (tang.api.s01s.cn) ---")
    url = "https://tang.api.s01s.cn/music_open_api.php?msg=周杰伦&type=json"
    try:
        r = await client.get(url, timeout=8.0)
        print(f"搜索状态码: {r.status_code}")
        data = r.json()
        print(f"搜索结果类型: {type(data).__name__}, 数量: {len(data) if isinstance(data, list) else 'dict'}")
        if isinstance(data, list) and data:
            first = data[0]
            print(f"  首条: {first.get('song_title')} - {first.get('singer_name')}, MID: {first.get('song_mid')}")
            mid = first.get('song_mid')
            # 请求详情
            detail_url = f"https://tang.api.s01s.cn/music_open_api.php?msg=周杰伦&type=json&mid={mid}"
            r_detail = await client.get(detail_url, timeout=8.0)
            det = r_detail.json()
            if isinstance(det, dict):
                print(f"  详情字段: 歌名={det.get('song_title')}, 专辑={det.get('album_title')}")
                play_urls = {k: v for k, v in det.items() if k.startswith("song_play_url") and v}
                print(f"  可用音质直链数: {len(play_urls)}")
                for k, v in list(play_urls.items())[:2]:
                    ok, msg = await check_audio_stream(client, v)
                    print(f"    - {k}: {v[:60]}... -> {msg}")
                has_lrc = bool(det.get('song_lyric') or det.get('lyric'))
                print(f"  歌词存在: {has_lrc}")
    except Exception as e:
        print(f"  唐接口出错: {e}")

async def test_qq_oiapi(client: httpx.AsyncClient):
    print("\n--- 2. 测试 QQ 音乐：oiapi.net 接口 ---")
    key = "oiapi-ef6133b7-ac2f-dc7d-878c-d3e207a82575"
    mid = "0039MnYb0qxYhV"  # 晴天
    url = f"https://oiapi.net/api/QQ_Music?key={key}&type=json&br=320k&mid={mid}"
    try:
        r = await client.get(url, timeout=8.0)
        print(f"oiapi QQ 响应: {r.status_code}, 内容: {r.text[:120]}")
    except Exception as e:
        print(f"  oiapi QQ 出错: {e}")

async def test_qq_cyapi(client: httpx.AsyncClient):
    print("\n--- 3. 测试 QQ 音乐：cyapi.top 接口 ---")
    key = "1ffdf5733f5d538760e63d7e46ba17438d9f7b9dfc18c51be1109386fd74c3a1"
    mid = "0039MnYb0qxYhV"
    url = f"https://cyapi.top/API/qq_music.php?apikey={key}&type=json&mid={mid}"
    try:
        r = await client.get(url, timeout=8.0)
        print(f"cyapi QQ 响应: {r.status_code}, 内容: {r.text[:120]}")
    except Exception as e:
        print(f"  cyapi QQ 出错: {e}")

async def test_qq_vkeys(client: httpx.AsyncClient):
    print("\n--- 4. 测试 QQ 音乐：vkeys.cn 接口 ---")
    mid = "0039MnYb0qxYhV"
    url = f"https://api.vkeys.cn/v2/music/tencent/geturl?mid={mid}"
    try:
        r = await client.get(url, timeout=8.0)
        print(f"vkeys QQ 响应: {r.status_code}, 内容: {r.text[:120]}")
    except Exception as e:
        print(f"  vkeys QQ 出错: {e}")

async def test_netease_oiapi(client: httpx.AsyncClient):
    print("\n--- 5. 测试网易云：oiapi.net 接口 ---")
    key = "oiapi-ef6133b7-ac2f-dc7d-878c-d3e207a82575"
    song_id = "440103454"
    url = f"https://oiapi.net/api/Music_163?key={key}&type=json&id={song_id}"
    try:
        r = await client.get(url, timeout=8.0)
        print(f"oiapi 网易 响应: {r.status_code}, 内容: {r.text[:120]}")
        data = r.json()
        audio_url = data.get("data", {}).get("url") or data.get("url")
        if audio_url:
            ok, msg = await check_audio_stream(client, audio_url)
            print(f"  音频可用性: {ok}, {msg}")
    except Exception as e:
        print(f"  oiapi 网易 出错: {e}")

async def test_netease_official_direct(client: httpx.AsyncClient):
    print("\n--- 6. 测试网易云：官方开放接口与外链 ---")
    # 搜索
    search_url = "https://music.163.com/api/search/get/web?s=晴天&type=1&offset=0&limit=5"
    try:
        r = await client.get(search_url, timeout=6.0)
        data = r.json()
        songs = data.get("result", {}).get("songs", [])
        print(f"网易搜索结果: {len(songs)} 首")
        if songs:
            s0 = songs[0]
            sid = s0.get("id")
            sname = s0.get("name")
            ar = s0.get("artists", [{}])[0].get("name")
            print(f"  首条: {sname} - {ar}, ID: {sid}")
            
            # 外链直链
            outer_url = f"https://music.163.com/song/media/outer/url?id={sid}.mp3"
            ok, msg = await check_audio_stream(client, outer_url)
            print(f"  外链播放地址: {outer_url} -> {msg}")
            
            # 歌词
            lrc_url = f"https://music.163.com/api/song/lyric?os=pc&id={sid}&lv=-1&kv=-1&tv=-1"
            r_lrc = await client.get(lrc_url, timeout=6.0)
            lrc_json = r_lrc.json()
            lrc_txt = lrc_json.get("lrc", {}).get("lyric", "")
            print(f"  歌词获取成功: {bool(lrc_txt)}, 长度: {len(lrc_txt)} 字符")
    except Exception as e:
        print(f"  网易官方接口出错: {e}")

async def test_netease_ranks(client: httpx.AsyncClient):
    print("\n--- 7. 测试网易云：精选/热歌/车载榜单 ---")
    ranks = {
        "热歌榜": "3778678",
        "飙升榜": "19723756",
        "新歌榜": "3779629",
        "抖音热歌": "2884035",
        "车载嗨歌": "528263379"
    }
    for name, rid in ranks.items():
        try:
            url = f"https://music.163.com/api/playlist/detail?id={rid}"
            r = await client.get(url, timeout=6.0)
            data = r.json()
            tracks = data.get("result", {}).get("tracks", [])
            print(f"  榜单 [{name}] (ID: {rid}): {len(tracks)} 首歌曲, 示例: {tracks[0].get('name') if tracks else '空'}")
        except Exception as e:
            print(f"  榜单 [{name}] 失败: {e}")

async def test_nonebot_all(client: httpx.AsyncClient):
    print("\n--- 8. 测试聚合榜单：NoneBot 音乐点歌 V2 ---")
    url = "https://api.nonebot.top/api/v2/music/order/all"
    try:
        r = await client.get(url, timeout=8.0)
        print(f"NoneBot 状态: {r.status_code}")
        data = r.json()
        print(f"NoneBot 返回键: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    except Exception as e:
        print(f"  NoneBot 出错: {e}")

async def main():
    print("==================================================")
    print("带中国大陆网络凭据 (伪造国内电信 IP) 探测音乐 API 可用性")
    print(f"Headers: X-Forwarded-For={CHINESE_HEADERS['X-Forwarded-For']}")
    print("==================================================")
    
    async with httpx.AsyncClient(headers=CHINESE_HEADERS, verify=False) as client:
        await test_qq_tang_api(client)
        await test_qq_oiapi(client)
        await test_qq_cyapi(client)
        await test_qq_vkeys(client)
        await test_netease_oiapi(client)
        await test_netease_official_direct(client)
        await test_netease_ranks(client)
        await test_nonebot_all(client)

if __name__ == "__main__":
    asyncio.run(main())
