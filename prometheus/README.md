# 薪火 · 中华文明动画短片

A 2:16 animated mini-doc, generated entirely from code. All on-screen text is in Simplified Chinese.

| Time | Chapter |
|---|---|
| 0–15 s | 标题「薪火」，火焰彗星划过星图 |
| 15–30 s | 第一章 · 孔子：我们确立大道 |
| 30–45 s | 第二章 · 秦始皇：我们一统天下 |
| 45–60 s | 第三章 · 蔡伦：我们发明纸张 |
| 60–75 s | 第四章 · 唐朝：我们盛世开放 |
| 75–90 s | 第五章 · 宋朝：我们印刷火药指南针 |
| 90–105 s | 第六章 · 明朝：我们远航建城 |
| 105–120 s | 第七章 · 近代：我们重新崛起 |
| 120–136 s | 终章：加速回顾，不朽遗产，火焰彗星结尾 |

- `render.py`: frame renderer (Pillow, 2x supersampled). It handles the parchment-to-starfield background, the schematic line diagrams drawn in with a pen-tip reveal, the bottom timeline with its rising "文明尺度" curve, the chapter titles, and the comet.
- `music.py`: procedural orchestral score (strings, brass, timpani). Every chapter holds a whole number of beats in exactly 15 s, so each cut lands on a downbeat. The tempo steps up 64 → 80 → 96 → 112 → 128 → 140 BPM, and the piece resolves on a D-major climax at 132 s.

## Build

```bash
pip install pillow numpy scipy
sudo apt-get install -y ffmpeg fonts-noto-cjk
./build.sh    # -> build/xinhuo_zh.mp4
```

For a quick preview, `python3 snap.py 26 70 130` writes stills to `build/`.
