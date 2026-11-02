import asyncio
import json
import subprocess
import tempfile
import urllib.request
import websockets
import base64
from PIL import Image
import io
import os

async def generate_crisp_gif():
    temp_dir = tempfile.mkdtemp()
    edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    
    # 16:9 viewport standard
    vw, vh = 1200, 675
    
    proc = subprocess.Popen([
        edge_path,
        '--headless=new',
        f'--user-data-dir={temp_dir}',
        '--remote-debugging-port=9888',
        f'--window-size={vw},{vh}',
        '--hide-scrollbars',
        '--disable-gpu',
        'http://localhost:3000'
    ])
    
    await asyncio.sleep(2.5)
    
    try:
        req = urllib.request.urlopen('http://127.0.0.1:9888/json')
        tabs = json.loads(req.read().decode())
        page_tab = next(t for t in tabs if t.get('type') == 'page')
        ws_url = page_tab['webSocketDebuggerUrl']
        
        async with websockets.connect(ws_url) as ws:
            msg_id = 0
            async def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                payload = {"id": msg_id, "method": method}
                if params:
                    payload["params"] = params
                await ws.send(json.dumps(payload))
                return json.loads(await ws.recv())

            # Set exact viewport metrics to prevent any stretching
            await send("Emulation.setDeviceMetricsOverride", {
                "width": vw,
                "height": vh,
                "deviceScaleFactor": 1,
                "mobile": False
            })

            # Dismiss opener and trigger ready
            await send("Runtime.evaluate", {
                "expression": """
                const op = document.getElementById('opener'); 
                if(op) op.remove(); 
                if(typeof ready === 'function') ready();
                document.body.classList.add('ready');
                """
            })
            await asyncio.sleep(1.2)
            
            frames = []
            num_frames = 32
            print(f"Capturing {num_frames} frames at {vw}x{vh}...")
            
            for i in range(num_frames):
                t = i / float(num_frames)
                
                # Organic smooth curve for mouse
                mx = vw * 0.5 + 240 * (0.5 - abs(t - 0.5) * 2)
                my = vh * 0.5 + 60 * (t * 2 - 1 if t < 0.5 else 1 - (t - 0.5) * 2)
                
                await send("Input.dispatchMouseEvent", {
                    "type": "mouseMoved",
                    "x": mx,
                    "y": my
                })
                
                await send("Runtime.evaluate", {
                    "expression": """
                    if(typeof px !== 'undefined') {
                        px += 2.0;
                        py -= 0.8;
                    }
                    """
                })
                
                await asyncio.sleep(0.08)
                
                # Capture uncompressed PNG screenshot for maximum clarity
                resp = await send("Page.captureScreenshot", {
                    "format": "png",
                    "clip": {
                        "x": 0,
                        "y": 0,
                        "width": vw,
                        "height": vh,
                        "scale": 1
                    }
                })
                img_data = base64.b64decode(resp['result']['data'])
                img = Image.open(io.BytesIO(img_data)).convert('RGB')
                
                # Resize proportionally (maintaining exact 16:9 ratio without any distortion)
                # 960 x 540 is standard high-def 16:9
                img_scaled = img.resize((960, 540), Image.Resampling.LANCZOS)
                frames.append(img_scaled)
                print(f"Frame {i+1}/{num_frames} captured ({img_scaled.size})")

            print("Quantizing with 256 colors adaptive palette without noisy dithering...")
            processed_frames = []
            for f in frames:
                # Use max 256 colors with ADAPTIVE palette and dither=NONE for pristine clean gradients
                p = f.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)
                processed_frames.append(p)
            
            out_path = "preview.gif"
            processed_frames[0].save(
                out_path,
                save_all=True,
                append_images=processed_frames[1:],
                optimize=True,
                duration=95,
                loop=0
            )
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            print(f"Pristine preview GIF successfully generated at {out_path} ({size_mb:.2f} MB, {processed_frames[0].size})")
            
    finally:
        proc.terminate()

asyncio.run(generate_crisp_gif())
