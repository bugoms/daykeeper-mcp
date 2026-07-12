# -*- coding: utf-8 -*-
"""DayKeeper 대표 이미지 생성 (1024x1024 PNG, PlayMCP 등록용).

컨셉: 따뜻한 그라데이션 배경 + 달력 카드 + 하트 = '기념일 챙김'
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 2048          # 슈퍼샘플링 캔버스
OUT = 1024        # 최종 출력 크기
OUT_PATH = Path(__file__).parent.parent / "assets" / "daykeeper_icon.png"

# 팔레트
GRAD_TOP = (255, 214, 140)     # 웜 옐로
GRAD_BOTTOM = (255, 118, 92)   # 코럴
CARD = (255, 255, 255)
HEADER = (244, 82, 82)         # 카드 헤더 레드
HEART = (244, 82, 82)
RING = (255, 236, 214)
DOT = (226, 226, 232)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def heart_points(cx, cy, size, n=240):
    """파라메트릭 하트 곡선."""
    pts = []
    for i in range(n):
        t = math.pi * 2 * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * size / 16, cy - y * size / 16))
    return pts


img = Image.new("RGB", (S, S))
draw = ImageDraw.Draw(img)

# 1) 대각선 그라데이션 배경
for yy in range(S):
    draw.line([(0, yy), (S, yy)], fill=lerp(GRAD_TOP, GRAD_BOTTOM, yy / S))

# 은은한 장식 원 (좌상단, 우하단)
deco = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ddraw = ImageDraw.Draw(deco)
ddraw.ellipse([-380, -380, 560, 560], fill=(255, 255, 255, 26))
ddraw.ellipse([S - 500, S - 500, S + 340, S + 340], fill=(255, 255, 255, 22))
img = Image.alpha_composite(img.convert("RGBA"), deco)

# 2) 카드 그림자
card_w, card_h = 1290, 1210
cx0 = (S - card_w) // 2
cy0 = (S - card_h) // 2 + 60
radius = 110

shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
sdraw = ImageDraw.Draw(shadow)
sdraw.rounded_rectangle([cx0 - 8, cy0 + 34, cx0 + card_w + 8, cy0 + card_h + 46], radius, fill=(120, 30, 20, 110))
shadow = shadow.filter(ImageFilter.GaussianBlur(46))
img = Image.alpha_composite(img, shadow)

draw = ImageDraw.Draw(img)

# 3) 카드 본체 + 헤더
draw.rounded_rectangle([cx0, cy0, cx0 + card_w, cy0 + card_h], radius, fill=CARD)
header_h = 320
draw.rounded_rectangle([cx0, cy0, cx0 + card_w, cy0 + header_h + radius], radius, fill=HEADER)
draw.rectangle([cx0, cy0 + header_h, cx0 + card_w, cy0 + header_h + radius], fill=CARD)

# 헤더 위 스프링 링 2개
ring_w, ring_h = 64, 240
for rx in (cx0 + card_w // 3, cx0 + card_w * 2 // 3):
    draw.rounded_rectangle([rx - ring_w // 2, cy0 - 130, rx + ring_w // 2, cy0 - 130 + ring_h], ring_w // 2, fill=RING)

# 4) 하트 (본문 중앙)
body_cy = cy0 + header_h + (card_h - header_h) // 2 - 28
draw.polygon(heart_points(S // 2, body_cy - 60, 272), fill=HEART)

# 하트 아래 날짜 점 3개 (달력 느낌)
dot_y = cy0 + card_h - 118
for i, dx in enumerate((-140, 0, 140)):
    color = HEART if i == 1 else DOT
    r = 26
    draw.ellipse([S // 2 + dx - r, dot_y - r, S // 2 + dx + r, dot_y + r], fill=color)

# 5) 다운스케일 & 저장
OUT_PATH.parent.mkdir(exist_ok=True)
img.convert("RGB").resize((OUT, OUT), Image.LANCZOS).save(OUT_PATH, "PNG")
print(f"saved: {OUT_PATH} ({OUT}x{OUT})")
