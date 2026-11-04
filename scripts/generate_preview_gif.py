import asyncio
import json
import subprocess
import tempfile
import urllib.request
import websockets
import base64
from PIL import Image, ImageDraw
import io
import os

def add_rounded_corners(im, radius=14):
    mask = Image.new('L', im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), im.size], radius=radius, fill=255)
    
    bg = Image.new('RGB', im.size, (14, 12, 10))
    bg.paste(im, (0, 0), mask)
    return bg

async def generate_crisp_gif():
    temp_dir = tempfile.mkdtemp()
    edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    
    # 16:9 viewport standard
    vw, vh = 1280, 720
    
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
    
    await asyncio.sleep(2.0)
    
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

            # Dismiss opener and start field
            await send("Runtime.evaluate", {
                "expression": """
                const op = document.getElementById('opener');
                if (op) op.remove();
                if (typeof ready === 'function') ready();
                document.body.classList.add('ready');
                """
            })
            
            # Wait for images and textures to decode
            print("Waiting for artwork assets to warm and decode...")
            await asyncio.sleep(3.5)
            
            frames = []
            num_frames = 24
            print(f"Recording {num_frames} interactive frames at {vw}x{vh}...")
            
            for i in range(num_frames):
                t = i / float(num_frames)
                
                # Smooth interactive cursor movement across the artwork cards
                mx = vw * 0.35 + (vw * 0.35) * (0.5 - abs(t - 0.5) * 2)
                my = vh * 0.42 + 90 * (t * 2 - 1 if t < 0.5 else 1 - (t - 0.5) * 2)
                
                await send("Input.dispatchMouseEvent", {
                    "type": "mouseMoved",
                    "x": mx,
                    "y": my
                })
                
                await send("Runtime.evaluate", {
                    "expression": """
                    if(typeof px !== 'undefined') {
                        px += 3.2;
                        py -= 1.2;
                    }
                    """
                })
                
                await asyncio.sleep(0.08)
                
                # Capture uncompressed frame
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
                
                # Proportional 16:9 resize to 960x540
                img_scaled = img.resize((960, 540), Image.Resampling.LANCZOS)
                
                # Add subtle rounded corners
                img_rounded = add_rounded_corners(img_scaled, radius=14)
                
                frames.append(img_rounded)
                print(f"Captured frame {i+1}/{num_frames}")

            print("Optimizing adaptive color palette for high clarity...")
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
                duration=115,
                loop=0
            )
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            print(f"Successfully generated preview.gif ({size_mb:.2f} MB, {processed_frames[0].size})")
            
    finally:
        proc.terminate()

asyncio.run(generate_crisp_gif())
