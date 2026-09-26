#!/usr/bin/env bash
# Renders 薪火 (136 s, 1920x1080@30) to build/xinhuo_zh.mp4
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
python3 music.py
python3 render.py 0 4080 build/video.mp4
ffmpeg -y -loglevel error -i build/video.mp4 -i build/score.wav \
  -c:v copy -af loudnorm=I=-14:TP=-1.0:LRA=14 -ar 48000 -c:a aac -b:a 192k -shortest -movflags +faststart build/xinhuo_zh.mp4
echo "done: build/xinhuo_zh.mp4"
