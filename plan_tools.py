"""Viewport tools for AI plan reading: overview / zoom / measure / mark / overlay.

Coordinates for zoom, measure, and mark are given in PDF points (page space),
so results from one command feed directly into the next. Every rendered image
prints its own page-space bounding box so the model can convert pixel
observations back to page coordinates:
    page_x = bbox.x0 + px / img_w * (bbox.x1 - bbox.x0)

Usage:
  python plan_tools.py overview  <pdf> [page]                 -> full page @150dpi
  python plan_tools.py zoom      <pdf> <page> <x0> <y0> <x1> <y1> [dpi]
  python plan_tools.py measure   <pdf> <scale_denom> <x1> <y1> <x2> <y2>
  python plan_tools.py mark      <pdf> <page> <out.png> <spec.json>
  python plan_tools.py overlay   <pdfA> <pageA> <pdfB> <pageB> <out.png>
  python plan_tools.py text      <pdf> <page>                 -> words + coords

mark spec.json: [{"type":"rect|line|circle","pts":[x0,y0,x1,y1],
                  "color":[1,0,0],"label":"..."}, ...]
"""
import json
import math
import sys

import fitz

PT_PER_M_PAPER = 72 / 25.4 * 1000  # points per paper-metre


def render(page, clip=None, dpi=150, out="view.png"):
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
    pix.save(out)
    box = clip if clip else page.rect
    print(f"wrote {out}  {pix.width}x{pix.height}px  "
          f"page-bbox=({box.x0:.1f},{box.y0:.1f},{box.x1:.1f},{box.y1:.1f})")


def main():
    cmd = sys.argv[1]
    if cmd == "overview":
        doc = fitz.open(sys.argv[2])
        pno = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        render(doc[pno], out="overview.png")

    elif cmd == "zoom":
        pdf, pno = sys.argv[2], int(sys.argv[3])
        x0, y0, x1, y1 = map(float, sys.argv[4:8])
        dpi = int(sys.argv[8]) if len(sys.argv) > 8 else 300
        doc = fitz.open(pdf)
        render(doc[pno], clip=fitz.Rect(x0, y0, x1, y1), dpi=dpi, out="zoom.png")

    elif cmd == "measure":
        scale = float(sys.argv[3])
        x1, y1, x2, y2 = map(float, sys.argv[4:8])
        d_pt = math.hypot(x2 - x1, y2 - y1)
        d_real = d_pt / PT_PER_M_PAPER * scale
        print(f"distance: {d_pt:.2f} pt on paper = {d_real:.3f} m real (1:{scale:.0f})")

    elif cmd == "mark":
        pdf, pno, out, specfile = sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
        doc = fitz.open(pdf)
        page = doc[pno]
        shape = page.new_shape()
        labels = []
        for m in json.load(open(specfile)):
            col = tuple(m.get("color", (1, 0, 0)))
            x0, y0, x1, y1 = (m["pts"] + [0, 0])[:4]
            if m["type"] == "text":
                labels.append((fitz.Point(x0, y0), m["label"], col))
                shape = page.new_shape()
                continue
            if m["type"] == "rect":
                shape.draw_rect(fitz.Rect(x0, y0, x1, y1))
            elif m["type"] == "line":
                shape.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1))
            elif m["type"] == "circle":
                shape.draw_circle(fitz.Point(x0, y0), x1)
            shape.finish(color=col, width=1.5)
            shape.commit()
            shape = page.new_shape()
            if m.get("label"):
                labels.append((fitz.Point(x0, y0 - 5), m["label"], col))
        for p, txt, col in labels:
            page.insert_text(p, txt, fontsize=10, color=col, fontname="hebo")
        render(page, dpi=150, out=out)

    elif cmd == "overlay":
        a, pa, b, pb, out = sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5]), sys.argv[6]
        from PIL import Image, ImageChops
        imgs = []
        for f, p, tint in ((a, pa, (255, 0, 0)), (b, pb, (0, 0, 255))):
            doc = fitz.open(f)
            pix = doc[p].get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72))
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
            rgb = Image.merge("RGB", [
                im.point(lambda v, c=c: 255 - (255 - v) * (255 - c) // 255)
                for c in tint])
            imgs.append(rgb)
        w = min(i.width for i in imgs); h = min(i.height for i in imgs)
        merged = ImageChops.multiply(imgs[0].crop((0, 0, w, h)), imgs[1].crop((0, 0, w, h)))
        merged.save(out)
        print(f"wrote {out}  A=red B=blue, shared strokes dark")

    elif cmd == "layers":
        # layers <pdf>                      -> list OCG layers
        # layers <pdf> <page> <out.png> on=1,3 off=2  -> render with layer set
        doc = fitz.open(sys.argv[2])
        ocgs = doc.get_ocgs()
        if len(sys.argv) < 4:
            if not ocgs:
                print("no OCG layers in this PDF")
            for xref, info in ocgs.items():
                print(f"xref={xref} on={info['on']} name={info['name']!r}")
        else:
            pno, out = int(sys.argv[3]), sys.argv[4]
            on, off = [], []
            for arg in sys.argv[5:]:
                k, v = arg.split("=")
                (on if k == "on" else off).extend(int(x) for x in v.split(","))
            doc.set_layer(-1, on=on, off=off)
            render(doc[pno], dpi=150, out=out)

    elif cmd == "snap":
        # snap <pdf> <page> <x> <y> [radius] -> vector edges near the point
        pdf, pno = sys.argv[2], int(sys.argv[3])
        x, y = float(sys.argv[4]), float(sys.argv[5])
        rad = float(sys.argv[6]) if len(sys.argv) > 6 else 15
        doc = fitz.open(pdf)
        hits = []
        for d in doc[pno].get_drawings():
            for item in d["items"]:
                if item[0] == "l":
                    pts = [(item[1], item[2])]
                elif item[0] == "re":
                    r = item[1]
                    pts = [(r.tl, r.tr), (r.tr, r.br), (r.br, r.bl), (r.bl, r.tl)]
                else:
                    continue
                for a, b in pts:
                    # distance point -> segment
                    ax, ay, bx, by = a.x, a.y, b.x, b.y
                    dx, dy = bx - ax, by - ay
                    t = 0 if dx == dy == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
                    px, py = ax + t * dx, ay + t * dy
                    dist = math.hypot(x - px, y - py)
                    if dist <= rad:
                        hits.append((dist, ax, ay, bx, by))
        for dist, ax, ay, bx, by in sorted(hits)[:8]:
            o = "V" if abs(ax - bx) < 0.01 else ("H" if abs(ay - by) < 0.01 else "D")
            print(f"d={dist:5.2f}pt {o} ({ax:.2f},{ay:.2f})-({bx:.2f},{by:.2f})")

    elif cmd == "text":
        doc = fitz.open(sys.argv[2])
        for w in doc[int(sys.argv[3])].get_text("words"):
            print(f"({w[0]:.1f},{w[1]:.1f},{w[2]:.1f},{w[3]:.1f}) {w[4]}")


if __name__ == "__main__":
    main()
