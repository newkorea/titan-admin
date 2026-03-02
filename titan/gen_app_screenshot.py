#!/usr/bin/env python3
"""Generate TitanVPN app screenshot PNG matching the actual app design."""
from PIL import Image, ImageDraw, ImageFont
import math, os, shutil

W, H = 460, 820
SIDEBAR_W = 68
MAIN_BG = (245, 240, 255)

img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

draw.rounded_rectangle((0, 0, W-1, H-1), radius=36, fill=MAIN_BG)

# Sidebar gradient
C_TOP = (124, 77, 255)
C_MID = (108, 63, 197)
C_BOT = (74, 42, 138)

sidebar_img = Image.new('RGBA', (SIDEBAR_W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(sidebar_img)
for y in range(H):
    ratio = y / H
    if ratio < 0.5:
        r2 = ratio * 2
        c = tuple(int(C_TOP[i]*(1-r2) + C_MID[i]*r2) for i in range(3)) + (255,)
    else:
        r2 = (ratio - 0.5) * 2
        c = tuple(int(C_MID[i]*(1-r2) + C_BOT[i]*r2) for i in range(3)) + (255,)
    sd.line([(0, y), (SIDEBAR_W-1, y)], fill=c)

mask = Image.new('L', (SIDEBAR_W, H), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle((0, 0, SIDEBAR_W + 40, H-1), radius=36, fill=255)
img.paste(sidebar_img, (0, 0), mask)

# Fonts
NOTO_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
NOTO_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
DEJA = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJA_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

font_brand = ImageFont.truetype(NOTO_B, 22)
font_status = ImageFont.truetype(NOTO_B, 22)
font_server = ImageFont.truetype(NOTO_B, 17)
font_timer = ImageFont.truetype(MONO_B, 28)
font_proto_title = ImageFont.truetype(NOTO_B, 15)
font_proto = ImageFont.truetype(NOTO_B, 14)
font_chat = ImageFont.truetype(NOTO_R, 14)
font_check = ImageFont.truetype(DEJA_B, 12)
font_diamond = ImageFont.truetype(DEJA, 14)

# Sidebar icons
icon_dim = (255, 255, 255, 110)
icon_bright = (255, 255, 255, 230)
sx = SIDEBAR_W // 2

# Logo
draw.rounded_rectangle((sx-15, 28, sx+15, 58), radius=7, fill=(255, 255, 255, 45))
draw.line((sx-6, 36, sx, 52), fill=icon_bright, width=2)
draw.line((sx, 52, sx+6, 36), fill=icon_bright, width=2)

# Icons
for y, active in [(100, True), (155, False), (210, False), (265, False)]:
    c = icon_bright if active else icon_dim
    if active:
        draw.rounded_rectangle((sx-17, y-17, sx+17, y+17), radius=9, fill=(255, 255, 255, 40))
    if y == 100:
        draw.ellipse((sx-6, y-12, sx+6, y-2), outline=c, width=2)
        draw.arc((sx-10, y+2, sx+10, y+18), 180, 360, fill=c, width=2)
    elif y == 155:
        draw.rounded_rectangle((sx-8, y-2, sx+8, y+12), radius=3, outline=c, width=2)
        draw.arc((sx-6, y-12, sx+6, y), 0, 360, fill=c, width=2)
    elif y == 210:
        draw.rounded_rectangle((sx-8, y-10, sx+8, y+12), radius=3, outline=c, width=2)
        draw.line((sx-4, y-2, sx+4, y-2), fill=c, width=2)
        draw.line((sx-4, y+4, sx+4, y+4), fill=c, width=2)
    elif y == 265:
        draw.line((sx, y-10, sx, y+4), fill=c, width=2)
        draw.line((sx-6, y-2, sx, y+6), fill=c, width=2)
        draw.line((sx+6, y-2, sx, y+6), fill=c, width=2)
        draw.line((sx-8, y+10, sx+8, y+10), fill=c, width=2)

# Bottom icons
my = H - 90
draw.rounded_rectangle((sx-9, my-8, sx+9, my+5), radius=2, outline=icon_dim, width=2)
draw.line((sx, my+5, sx, my+12), fill=icon_dim, width=2)
draw.line((sx-6, my+12, sx+6, my+12), fill=icon_dim, width=2)

ey = H - 45
draw.rounded_rectangle((sx-8, ey-8, sx+4, ey+8), radius=2, outline=icon_dim, width=2)
draw.line((sx+2, ey, sx+12, ey), fill=icon_dim, width=2)
draw.line((sx+7, ey-5, sx+12, ey), fill=icon_dim, width=2)
draw.line((sx+7, ey+5, sx+12, ey), fill=icon_dim, width=2)

# Main content
cx = SIDEBAR_W + (W - SIDEBAR_W) // 2
brand_color = (74, 42, 138)
purple = (108, 63, 197)

# Brand
draw.text((cx, 50), "TitanVPN", fill=brand_color, font=font_brand, anchor="mm")
bb = draw.textbbox((cx, 50), "TitanVPN", font=font_brand, anchor="mm")
draw.text((bb[0] - 18, 50), "✦", fill=purple, font=font_diamond, anchor="mm")

# Power Ring
ring_cy = 210
ring_r = 78
ring_thick = 7

for angle in range(360):
    rad = math.radians(angle - 90)
    ratio = angle / 360
    if ratio < 0.25:
        r2 = ratio * 4
        rc, gc, bc = (int(165*(1-r2)+16*r2), int(110*(1-r2)+185*r2), int(255*(1-r2)+129*r2))
    elif ratio < 0.5:
        r2 = (ratio-0.25)*4
        rc, gc, bc = (int(16*(1-r2)+160*r2), int(185*(1-r2)+130*r2), int(129*(1-r2)+220*r2))
    elif ratio < 0.75:
        r2 = (ratio-0.5)*4
        rc, gc, bc = (int(160*(1-r2)+180*r2), int(130*(1-r2)+100*r2), int(220*(1-r2)+255*r2))
    else:
        r2 = (ratio-0.75)*4
        rc, gc, bc = (int(180*(1-r2)+165*r2), int(100*(1-r2)+110*r2), int(255*(1-r2)+255*r2))
    for dr in range(ring_thick):
        rr = ring_r + dr
        x = cx + rr * math.cos(rad)
        y = ring_cy + rr * math.sin(rad)
        if 0 <= x < W and 0 <= y < H:
            draw.point((int(x), int(y)), fill=(rc, gc, bc, 255))

draw.ellipse((cx - ring_r + 2, ring_cy - ring_r + 2, cx + ring_r - 2, ring_cy + ring_r - 2), fill=(255, 255, 255))

# Power icon
pw_color = (120, 120, 130)
pw_r = 24
for angle in range(40, 320):
    rad = math.radians(angle - 90)
    for t in range(-2, 2):
        x = cx + (pw_r + t) * math.cos(rad)
        y = ring_cy + (pw_r + t) * math.sin(rad)
        if 0 <= x < W and 0 <= y < H:
            draw.point((int(x), int(y)), fill=pw_color)
draw.line((cx, ring_cy - pw_r - 4, cx, ring_cy - 6), fill=pw_color, width=4)

# Status
status_y = ring_cy + ring_r + 35
draw.text((cx, status_y), "연결됨", fill=purple, font=font_status, anchor="mm")

# Flag
flag_y = status_y + 55
flag_r = 20
draw.ellipse((cx-flag_r-2, flag_y-flag_r-2, cx+flag_r+2, flag_y+flag_r+2), fill=(255, 255, 255))
draw.pieslice((cx-flag_r, flag_y-flag_r, cx+flag_r, flag_y+flag_r), -180, 0, fill=(205, 46, 58))
draw.pieslice((cx-flag_r, flag_y-flag_r, cx+flag_r, flag_y+flag_r), 0, 180, fill=(0, 71, 160))

server_y = flag_y + flag_r + 16
draw.text((cx, server_y), "KOREA-LG2", fill=brand_color, font=font_server, anchor="mm")

# Timer
timer_y = server_y + 40
draw.text((cx, timer_y), "00:00:03", fill=purple, font=font_timer, anchor="mm")

# Protocol section
proto_top = timer_y + 40
lx = SIDEBAR_W + 28
rx = W - 28
draw.line((lx, proto_top, rx, proto_top), fill=(200, 190, 220, 80), width=1)

proto_title_y = proto_top + 22
title_text = "연결방식"
tb = draw.textbbox((cx, proto_title_y), title_text, font=font_proto_title, anchor="mm")
draw.rounded_rectangle((tb[0]-14, tb[1]-6, tb[2]+14, tb[3]+6), radius=12, fill=(230, 225, 240))
draw.text((cx, proto_title_y), title_text, fill=brand_color, font=font_proto_title, anchor="mm")

proto_base_y = proto_title_y + 38
col1_x = lx + 15
col2_x = cx + 10
for i, (name, checked) in enumerate([("IKEV2", True), ("SSTP", False), ("OpenVPN", False), ("V2ray", False)]):
    px = col1_x if i % 2 == 0 else col2_x
    py = proto_base_y + (i // 2) * 34
    cb = 18
    if checked:
        draw.rounded_rectangle((px, py, px+cb, py+cb), radius=4, fill=purple)
        draw.text((px+cb//2, py+cb//2), "✓", fill=(255, 255, 255), font=font_check, anchor="mm")
    else:
        draw.rounded_rectangle((px, py, px+cb, py+cb), radius=4, outline=(190, 190, 200), width=2)
    draw.text((px + cb + 10, py + cb//2), name, fill=(80, 80, 80), font=font_proto, anchor="lm")

# Live Chat
chat_y = proto_base_y + 90
draw.ellipse((cx-55, chat_y-5, cx-45, chat_y+5), fill=(245, 166, 35))
draw.text((cx-39, chat_y), "실시간 상담", fill=(140, 140, 140), font=font_chat, anchor="lm")

# Border
draw.rounded_rectangle((0, 0, W-1, H-1), radius=36, outline=(170, 150, 210, 100), width=2)

# Save
out_path = "/home/newkorea/project/titan/static/new/img/app-screenshot.png"
img.save(out_path, "PNG", optimize=True)
sz = os.path.getsize(out_path)
print(f"Saved: {out_path} ({sz:,} bytes, {W}x{H})")

dst = "/home/newkorea/project/titan/backend/static/new/img/app-screenshot.png"
os.makedirs(os.path.dirname(dst), exist_ok=True)
shutil.copy2(out_path, dst)
print(f"Copied: {dst}")
