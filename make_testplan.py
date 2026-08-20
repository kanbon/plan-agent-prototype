"""Generate a synthetic architectural floor plan PDF (vector) at scale 1:100.

A3 landscape. 1:100 -> 1 m real = 10 mm paper = 28.3465 pt.
Planted discrepancy: the bedroom dimension chain claims 4.00 m but the drawn
geometry is 3.60 m.
"""
import fitz

MM = 72 / 25.4          # pt per mm
M = 10 * MM             # pt per real-world metre at 1:100

PAGE_W, PAGE_H = 420 * MM, 297 * MM  # A3 landscape

doc = fitz.open()
page = doc.new_page(width=PAGE_W, height=PAGE_H)

# Origin of the building outline on paper
OX, OY = 40 * MM, 220 * MM  # bottom-left corner (PDF y grows downward)

def pt(x_m, y_m):
    """Real-world metres (x right, y up) -> page points."""
    return fitz.Point(OX + x_m * M, OY - y_m * M)

shape = page.new_shape()

WALL = 0.30   # outer wall thickness m
IW = 0.115    # inner wall thickness m

# ---- outer walls: building 10.0 x 7.0 m outside dimensions ----
BW, BH = 10.0, 7.0
outer = fitz.Rect(pt(0, BH), pt(BW, 0))
inner = fitz.Rect(pt(WALL, BH - WALL), pt(BW - WALL, WALL))
shape.draw_rect(outer)
shape.draw_rect(inner)

# ---- inner walls ----
# vertical wall separating living room (left) from bedroom+bath (right)
# bedroom drawn width = 3.60 m (from right inner wall face) -> wall at x = BW-WALL-3.60
xv = BW - WALL - 3.60
shape.draw_rect(fitz.Rect(pt(xv, BH - WALL), pt(xv + IW, WALL)))
# horizontal wall separating bedroom (top) and bathroom (bottom) on the right
yh = 2.50
shape.draw_rect(fitz.Rect(pt(xv + IW, yh + IW), pt(BW - WALL, yh)))

shape.finish(color=(0, 0, 0), fill=(0.85, 0.85, 0.85), width=0.6, even_odd=True); shape.commit()

# ---- door openings (white gaps + swing arcs) ----
shape2 = page.new_shape()
def door(x_m, y_m, w_m, horizontal=True, wall_t=IW):
    """White out an opening in a wall and draw a quarter-circle swing."""
    if horizontal:
        r = fitz.Rect(pt(x_m, y_m + wall_t + 0.01), pt(x_m + w_m, y_m - 0.01))
    else:
        r = fitz.Rect(pt(x_m - 0.01, y_m + w_m), pt(x_m + wall_t + 0.01, y_m))
    shape2.draw_rect(r)

door(xv + IW + 0.20, yh, 0.90)                    # bath door in horizontal wall
door(xv, 3.20, 1.00, horizontal=False)            # bedroom door in vertical wall
# entrance door in bottom outer wall, living room
r = fitz.Rect(pt(1.20, WALL + 0.01), pt(2.20, -0.01))
shape2.draw_rect(r)
shape2.finish(color=None, fill=(1, 1, 1)); shape2.commit()

# swings
shape3 = page.new_shape()
c = pt(xv + IW + 0.20, yh + IW)
shape3.draw_sector(c, fitz.Point(c.x + 0.90 * M, c.y), 90)
c = pt(xv + IW, 3.20 + 1.00)
shape3.draw_sector(c, fitz.Point(c.x + 1.00 * M, c.y), 90)
c = pt(1.20, WALL)
shape3.draw_sector(c, fitz.Point(c.x + 1.00 * M, c.y), -90)
shape3.finish(color=(0, 0, 0), width=0.4); shape3.commit()

# ---- room labels ----
FS = 9
def label(x_m, y_m, text, size=FS):
    p = pt(x_m, y_m)
    page.insert_text(p, text, fontsize=size, fontname="helv")

label(1.5, 3.6, "WOHNEN")
label(1.5, 3.1, "31.2 m2", size=7)
label(7.2, 5.0, "SCHLAFEN")
label(7.2, 4.5, "13.4 m2", size=7)
label(7.2, 1.3, "BAD")
label(7.2, 0.9, "6.9 m2", size=7)

# ---- dimension chains (top, outside building) ----
def dim(x1_m, x2_m, y_m, text):
    a, b = pt(x1_m, y_m), pt(x2_m, y_m)
    s = page.new_shape()
    s.draw_line(a, b)
    for p in (a, b):
        s.draw_line(fitz.Point(p.x - 2, p.y + 2), fitz.Point(p.x + 2, p.y - 2))
    s.finish(color=(0, 0, 0), width=0.4); s.commit()
    mid = fitz.Point((a.x + b.x) / 2 - 8, a.y - 3)
    page.insert_text(mid, text, fontsize=7, fontname="helv")

# overall
dim(0, BW, BH + 1.2, "10.00")
# chain: living | wall | bedroom   -- PLANTED ERROR: bedroom labelled 4.00, drawn 3.60
dim(0, WALL, BH + 0.6, "30")
dim(WALL, xv, BH + 0.6, "5.86")
dim(xv, xv + IW, BH + 0.6, "11.5")
dim(xv + IW, BW - WALL, BH + 0.6, "4.00")   # <-- WRONG: geometry is 3.60
dim(BW - WALL, BW, BH + 0.6, "30")

# left side vertical dims
def vdim(y1_m, y2_m, x_m, text):
    a, b = pt(x_m, y1_m), pt(x_m, y2_m)
    s = page.new_shape()
    s.draw_line(a, b)
    for p in (a, b):
        s.draw_line(fitz.Point(p.x - 2, p.y + 2), fitz.Point(p.x + 2, p.y - 2))
    s.finish(color=(0, 0, 0), width=0.4); s.commit()
    page.insert_text(fitz.Point(a.x - 18, (a.y + b.y) / 2), text, fontsize=7, fontname="helv")

vdim(0, BH, -1.0, "7.00")

# ---- title block ----
tb = fitz.Rect(PAGE_W - 120 * MM, PAGE_H - 45 * MM, PAGE_W - 10 * MM, PAGE_H - 10 * MM)
s = page.new_shape()
s.draw_rect(tb)
s.draw_line(fitz.Point(tb.x0, tb.y0 + 12 * MM), fitz.Point(tb.x1, tb.y0 + 12 * MM))
s.draw_line(fitz.Point(tb.x0, tb.y0 + 24 * MM), fitz.Point(tb.x1, tb.y0 + 24 * MM))
s.finish(color=(0, 0, 0), width=0.8); s.commit()
page.insert_text(fitz.Point(tb.x0 + 4, tb.y0 + 8 * MM), "PROJEKT: WHG TOP 4 - MUSTERGASSE 12", fontsize=9, fontname="helv")
page.insert_text(fitz.Point(tb.x0 + 4, tb.y0 + 20 * MM), "GRUNDRISS EG", fontsize=9, fontname="helv")
page.insert_text(fitz.Point(tb.x0 + 4, tb.y0 + 32 * MM), "MASSSTAB 1:100   PLAN-NR. A-01   27.07.2026", fontsize=9, fontname="helv")

doc.save("testplan.pdf")
print("wrote testplan.pdf")
