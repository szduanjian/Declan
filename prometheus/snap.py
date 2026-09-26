import sys
from PIL import Image
import render
for t in map(float, sys.argv[1:]):
    buf = render.render(int(t * render.FPS))
    Image.frombytes("RGB", (render.W, render.H), buf).save(f"build/snap_{t:05.1f}.png")
    print("ok", t)
