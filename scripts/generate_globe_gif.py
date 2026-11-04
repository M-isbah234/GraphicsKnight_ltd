import asyncio
import json
import subprocess
import tempfile
import urllib.request
import websockets
import base64
import io
import os
from PIL import Image, ImageDraw

def add_rounded_corners(im, radius=12):
    mask = Image.new('L', im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), im.size], radius=radius, fill=255)
    
    bg = Image.new('RGB', im.size, (14, 12, 10))
    bg.paste(im, (0, 0), mask)
    return bg

async def generate_globe_gif():
    # Start server if needed
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_proc = None
    if s.connect_ex(('127.0.0.1', 3000)) != 0:
        server_proc = subprocess.Popen(['node', 'server.js'])
        await asyncio.sleep(1.5)
    s.close()

    temp_dir = tempfile.mkdtemp()
    edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    vw, vh = 1280, 720
    proc = subprocess.Popen([
        edge_path, '--headless=new', f'--user-data-dir={temp_dir}',
        '--remote-debugging-port=9888', f'--window-size={vw},{vh}',
        '--hide-scrollbars', '--disable-gpu', 'http://localhost:3000/#about'
    ])
    await asyncio.sleep(2.0)
    try:
        req = urllib.request.urlopen('http://127.0.0.1:9888/json')
        tabs = json.loads(req.read().decode())
        ws_url = next(t for t in tabs if t.get('type') == 'page')['webSocketDebuggerUrl']
        async with websockets.connect(ws_url) as ws:
            msg_id = 0
            async def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                await ws.send(json.dumps({'id': msg_id, 'method': method, 'params': params or {}}))
                return json.loads(await ws.recv())

            await send('Emulation.setDeviceMetricsOverride', {
                'width': vw, 'height': vh, 'deviceScaleFactor': 1, 'mobile': False
            })

            # Switch to #work and setView(true)
            await send('Runtime.evaluate', {
                'expression': '''
                (function() {
                    location.hash = '#work';
                    if (typeof window.setView === 'function') window.setView(true);
                })()
                '''
            })
            
            # Settle globe
            await asyncio.sleep(3.0)
            
            num_frames = 18
            frame_delay = 120 # ms
            frames = []
            print(f"Recording {num_frames} frames of rotating 3D globe...")
            
            for i in range(num_frames):
                await asyncio.sleep(frame_delay / 1000.0)
                resp = await send('Page.captureScreenshot', {
                    'format': 'png',
                    'clip': {'x': 0, 'y': 0, 'width': vw, 'height': vh, 'scale': 1}
                })
                img_data = base64.b64decode(resp['result']['data'])
                img = Image.open(io.BytesIO(img_data)).convert('RGB')
                
                # Resize to 800x450 (16:9, fast loading and crisp)
                img_scaled = img.resize((800, 450), Image.Resampling.LANCZOS)
                img_rounded = add_rounded_corners(img_scaled, radius=12)
                frames.append(img_rounded)
                print(f"Frame {i+1}/{num_frames}")

            processed_frames = []
            for f in frames:
                p = f.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)
                processed_frames.append(p)

            out_path = "preview.gif"
            processed_frames[0].save(
                out_path,
                save_all=True,
                append_images=processed_frames[1:],
                optimize=True,
                duration=frame_delay,
                loop=0
            )
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            print(f"Compact preview.gif generated successfully ({size_mb:.2f} MB, {processed_frames[0].size})")
    finally:
        proc.terminate()
        if server_proc: server_proc.terminate()

asyncio.run(generate_globe_gif())
