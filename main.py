import asyncio
import os
import aiohttp
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# ================= [ 설정 영역 ] =================
CHZZK_CHANNEL_ID = "23bf77359d688742889c336e38c9e22b"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1518268662874767562/YOQ9z0zCrLPlnsPBQKzlBvvs7XPUStc_9kXZ9ALDGwO_Eu8i6rQYGbO7srC4rsi-DAuP"
# =================================================

# Render 무료 버전이 꺼지지 않도록 가짜 웹서버를 하나 열어둡니다.
class HealthCheckServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckServer)
    server.serve_forever()

async def send_to_discord(nickname, amount, roulette_result):
    payload = {
        "username": "치지직 룰렛 알리미",
        "embeds": [{
            "title": "🎉 치지직 순정 룰렛 당첨!",
            "color": 5763719,
            "fields": [
                {"name": "👤 시청자", "value": nickname, "inline": True},
                {"name": "🪙 후원 치즈", "value": f"{amount:,} 치즈", "inline": True},
                {"name": "🎲 룰렛 결과", "value": f"**{roulette_result}**", "inline": False}
            ],
            "footer": {"text": f"치지직 실시간 연동 중 • {datetime.now().strftime('%H:%M:%S')}"}
        }]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(DISCORD_WEBHOOK_URL, json=payload) as resp:
            pass

async def get_chat_channel_id():
    url = f"https://api.chzzk.naver.com/open/v1/channels/{CHZZK_CHANNEL_ID}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("content", {}).get("chatChannelId")
    return None

async def connect_chzzk():
    chat_channel_id = await get_chat_channel_id()
    if not chat_channel_id:
        print("❌ 채널 ID 에러")
        return

    ws_url = "wss://kr-ss1.chat.chzzk.naver.com/chat" 
    print("🤖 룰렛 감시 봇 작동 시작...")
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            connect_cmd = {
                "ver": "2", "cmd": 100, "svcid": "game", "cid": chat_channel_id,
                "bdy": {"uid": None, "devType": 2001, "accTkn": "anonymous", "auth": "READ"}
            }
            await ws.send_json(connect_cmd)
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    if data.get("cmd") == 0:
                        await ws.send_json({"cmd": 10000})
                        continue
                    if data.get("cmd") == 93006:  
                        for chat_data in data.get("bdy", []):
                            if chat_data.get("msgTypeCode") == 10: 
                                import json
                                extra_inside = json.loads(chat_data.get("extra", "{}"))
                                if extra_inside.get("donationType") == "ROULETTE":
                                    profile = json.loads(chat_data.get("profile", "{}"))
                                    nickname = profile.get("nickname", "익명의시청자")
                                    amount = extra_inside.get("payAmount", 0)
                                    roulette_result = extra_inside.get("rouletteResult", "결과 없음")
                                    await send_to_discord(nickname, amount, roulette_result)

async def main():
    # 백그라운드에서 웹서버 실행
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()
    
    while True:
        try:
            await connect_chzzk()
        except Exception as e:
            print(f"재연결 중...: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
