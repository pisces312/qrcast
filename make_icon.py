from PIL import Image, ImageDraw, ImageFont
import math, os, random

def refine_icon():
    size = 1024
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # === Color Palette ===
    deep_blue   = (26,  86,  219)   # #1A56DB
    bright_blue  = (37,  99,  235)   # #2563EB
    cyan         = (6,   182, 212)   # #06B6D4
    sky          = (147, 197, 253)   # #93C5FD
    white        = (255, 255, 255)
    dark_bg      = (15,  23,  42)   # #0F172A

    # === Helpers ===
    def rounded_rect(d, bbox, r, fill):
        x1,y1,x2,y2 = bbox
        d.rectangle([x1+r,y1,x2-r,y2], fill=fill)
        d.rectangle([x1,y1+r,x2,y2-r], fill=fill)
        d.pieslice([x1,y1,x1+2*r,y1+2*r], 180,270, fill=fill)
        d.pieslice([x2-2*r,y1,x2,y1+2*r], 270,360, fill=fill)
        d.pieslice([x1,y2-2*r,x1+2*r,y2],  90,180, fill=fill)
        d.pieslice([x2-2*r,y2-2*r,x2,y2],   0, 90, fill=fill)

    def finder(d, x, y, sz, oc, wc):
        g = sz // 7
        cx = sz // 2
        cs = sz // 3
        d.rectangle([x,y,x+sz,y+sz], fill=oc)
        d.rectangle([x+g,y+g,x+sz-g,y+sz-g], fill=wc)
        d.rectangle([x+cx-cs//2,y+cx-cs//2,x+cx+cs//2,y+cx+cs//2], fill=oc)

    def arrow_head(d, x, y, sz, fill, angle_deg=320):
        ang = math.radians(angle_deg)
        pts = [
            (x, y),
            (x + sz*math.cos(ang-0.5), y - sz*math.sin(ang-0.5)),
            (x + sz*0.6*math.cos(ang), y - sz*0.6*math.sin(ang)),
            (x + sz*math.cos(ang+0.5), y - sz*math.sin(ang+0.5)),
        ]
        d.polygon(pts, fill=fill)

    # === 1. Dark rounded background ===
    rounded_rect(draw, (32, 32, size-32, size-32), 200, dark_bg)

    # === 2. Subtle grid pattern in background ===
    grid_col = (37, 55, 91, 60)   # very faint
    step = 64
    for gx in range(32, size-32, step):
        draw.line([(gx,32),(gx,size-32)], fill=grid_col, width=1)
    for gy in range(32, size-32, step):
        draw.line([(32,gy),(size-32,gy)], fill=grid_col, width=1)

    # === 3. Document / File silhouette (lower-left) ===
    dx, dy, dw, dh = 80, 360, 400, 580
    fold = 90
    # Main body with folded corner
    body_pts = [(dx,dy),(dx+dw-fold,dy),(dx+dw,dy+fold),(dx+dw,dy+dh),(dx,dy+dh)]
    draw.polygon(body_pts, fill=bright_blue)
    # Fold
    fold_pts = [(dx+dw-fold,dy),(dx+dw-fold,dy+fold),(dx+dw,dy+fold)]
    draw.polygon(fold_pts, fill=sky)
    # Fold shadow line
    draw.line([(dx+dw-fold,dy),(dx+dw-fold,dy+fold),(dx+dw,dy+fold)], fill=deep_blue, width=3)

    # Document content: title bar + lines
    draw.rectangle([dx+40, dy+50, dx+dw-50, dy+90], fill=sky)  # title bar
    draw.rectangle([dx+40, dy+110, dx+200, dy+145], fill=white)  # title text block
    for i in range(5):
        ly = dy + 170 + i * 70
        lw = 260 - i * 15
        draw.rectangle([dx+40, ly, dx+40+lw, ly+28], fill=(100,149,237,180))

    # Small checkmark in title
    cx_chk = dx + dw - 90
    cy_chk = dy + 70
    draw.ellipse([cx_chk-22,cx_chk-22,cx_chk+22,cx_chk+22], fill=cyan)
    draw.line([(cx_chk-10,cy_chk),(cx_chk-3,cy_chk+10),(cx_chk+12,cy_chk-10)], fill=white, width=5)

    # === 4. QR code matrix (upper-right area) ===
    qx, qy = 470, 80
    cell = 72
    qr = [
        [1,1,1,1,1,1,1,0,1,0,1],
        [1,0,0,0,0,0,1,0,0,1,0],
        [1,0,1,1,1,0,1,0,1,1,0],
        [1,0,1,1,1,0,1,0,0,1,1],
        [1,0,1,1,1,0,1,0,1,0,0],
        [1,0,0,0,0,0,1,0,1,1,0],
        [1,1,1,1,1,1,1,0,0,1,0],
        [0,0,0,0,0,0,0,0,1,0,1],
        [1,0,1,1,0,1,0,1,1,0,0],
        [0,1,0,1,1,0,1,0,1,1,1],
        [1,0,1,0,1,1,0,1,0,1,0],
    ]
    for r in range(11):
        for c in range(11):
            if qr[r][c]:
                draw.rectangle([qx+c*cell, qy+r*cell, qx+c*cell+cell-4, qy+r*cell+cell-4], fill=deep_blue)

    # Finder patterns
    finder(draw, qx-34, qy-34, cell*3+24, deep_blue, white)
    # Bottom-left finder (partial, near document)
    finder(draw, qx-34, qy+cell*4-10, cell*3+24, bright_blue, white)

    # === 5. Data flow: clean arc ===
    acx, acy = 540, 520
    ar = 300
    for i in range(30):
        a1 = math.radians(195 + i * 4.5)
        a2 = math.radians(195 + (i+1) * 4.5)
        t = i / 30.0
        rc = int(6   + t*(26-6))
        gc = int(182 + t*(86-182))
        bc = int(212 + t*(219-212))
        col = (rc, gc, bc)
        x1 = acx + ar*math.cos(a1);  y1 = acy - ar*math.sin(a1)
        x2 = acx + ar*math.cos(a2);  y2 = acy - ar*math.sin(a2)
        draw.line([(x1,y1),(x2,y2)], fill=col, width=14)

    # Arrow
    ax = acx + ar*math.cos(math.radians(330))
    ay = acy - ar*math.sin(math.radians(330))
    arrow_head(draw, ax, ay, 42, cyan, 330)

    # Glow dot at arc start
    sx = acx + ar*math.cos(math.radians(195))
    sy = acy - ar*math.sin(math.radians(195))
    draw.ellipse([sx-16,sy-16,sx+16,sy+16], fill=cyan)

    # === 6. Small data particles (sparse, intentional) ===
    random.seed(777)
    positions = [
        (400,380),(440,340),(490,310),(550,300),(610,330),(660,380),
        (380,460),(420,500),(470,530),(540,560),(600,530),(650,490),
        (400,620),(460,650),(520,660),(580,640),(640,600),(670,550),
    ]
    for px, py in positions:
        r = random.randint(5,12)
        a = random.randint(100,200)
        draw.ellipse([px-r,py-r,px+r,py+r], fill=(*cyan,a))

    # === 7. "QR TRANSFER" label ===
    try:
        fnt = ImageFont.truetype("arial.ttf", 60)
        fnt_b = ImageFont.truetype("arialbd.ttf", 68)
    except:
        fnt = ImageFont.load_default()
        fnt_b = fnt
    draw.text((size//2+3, 878+3), "QR TRANSFER", anchor="mm", fill=(0,0,0,80), font=fnt_b)
    draw.text((size//2, 878), "QR TRANSFER", anchor="mm", fill=white, font=fnt_b)

    # === 8. Corner marks ===
    draw.line([(55,130),(55,55),(130,55)], fill=sky, width=8)
    draw.line([(size-55,size-130),(size-55,size-55),(size-130,size-55)], fill=sky, width=8)

    # === Save all sizes ===
    out_dir = r"D:\nili\my-git-projects\my-notebooks\my_projects\qr_transfer_app"
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, "icon")
    for s in [16,32,48,64,128,256,512,1024]:
        img.resize((s,s), Image.LANCZOS).save(f"{base}_{s}x{s}.png")
    img.resize((512,512), Image.LANCZOS).save(f"{base}.png")
    print("Icon saved:", base)

refine_icon()
