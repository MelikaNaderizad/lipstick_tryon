DEFAULT_SKIN_BOX = (0.10, 0.30, 0.45, 0.70)
DEFAULT_SWATCH_BOX = (0.55, 0.30, 0.90, 0.70)

def parse_box(text):
    parts = [float(p) for p in str(text).replace(" ", "").split(",")]
    if len(parts) != 4:
        raise ValueError("کادر باید چهار عدد باشه: x0,y0,x1,y1")
    x0, y0, x1, y1 = parts
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("کادر باید 0 <= x0 < x1 <= 1 و 0 <= y0 < y1 <= 1 باشه")
    return (x0, y0, x1, y1)

def to_pixels(box_frac, width, height):
    x0, y0, x1, y1 = box_frac
    return (
        int(round(x0 * width)),
        int(round(y0 * height)),
        max(int(round(x1 * width)), int(round(x0 * width)) + 1),
        max(int(round(y1 * height)), int(round(y0 * height)) + 1),
    )
