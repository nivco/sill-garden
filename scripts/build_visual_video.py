#!/usr/bin/env python3
"""Build a visual review video for Sill Garden (photos + charts + narration).

Example:
  python scripts/build_visual_video.py products/youtube/video-aerogarden-vs-click-grow/storyboard.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import textwrap
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1920, 1080
FFMPEG = (
    Path(r"C:\Users\nivoo\AppData\Local\Microsoft\WinGet\Packages")
    / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    / "ffmpeg-8.1.1-full_build"
    / "bin"
    / "ffmpeg.exe"
)
FFPROBE = FFMPEG.with_name("ffprobe.exe")

# Leafy brand palette (matches site vibe without purple AI clichés)
LEAF = (45, 106, 79)
LEAF_DEEP = (27, 67, 50)
HARVEST = (196, 125, 54)
CREAM = (247, 250, 246)
INK = (20, 32, 24)
MUTED = (90, 110, 95)
CARD = (255, 255, 255)


def find_ffmpeg() -> tuple[Path, Path]:
    import shutil

    ff = shutil.which("ffmpeg")
    fp = shutil.which("ffprobe")
    if ff and fp:
        return Path(ff), Path(fp)
    if FFMPEG.is_file() and FFPROBE.is_file():
        return FFMPEG, FFPROBE
    raise RuntimeError("ffmpeg/ffprobe not found")


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        lines.extend(textwrap.wrap(para, width=width) or [para])
    return lines


def load_photo(rel: str) -> Image.Image:
    path = ROOT / "public" / rel.lstrip("/")
    if not path.is_file():
        path = ROOT / rel
    img = Image.open(path).convert("RGB")
    return img


def cover_crop(img: Image.Image, tw: int, th: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(tw / src_w, th / src_h)
    nw, nh = int(src_w * scale), int(src_h * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def rounded_paste(base: Image.Image, overlay: Image.Image, box: tuple[int, int, int, int], radius: int = 24) -> None:
    x0, y0, x1, y1 = box
    tw, th = x1 - x0, y1 - y0
    photo = cover_crop(overlay, tw, th)
    mask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (tw - 1, th - 1)], radius=radius, fill=255)
    base.paste(photo, (x0, y0), mask)


def draw_brand(draw: ImageDraw.ImageDraw, x: int = 64, y: int = 48) -> int:
    """Draw brand block; returns y just below it for next content."""
    draw.text((x, y), "SILL GARDEN", font=font(26, bold=True), fill=LEAF)
    draw.text((x, y + 36), "Apartment windowsill & countertop gardens", font=font(20), fill=MUTED)
    return y + 72


def text_height(draw: ImageDraw.ImageDraw, text: str, fnt, max_width_chars: int) -> tuple[list[str], int]:
    lines = wrap(text, max_width_chars)
    if not lines:
        return [], 0
    sample = draw.textbbox((0, 0), "Ag", font=fnt)
    line_h = (sample[3] - sample[1]) + 10
    return lines, len(lines) * line_h


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt,
    fill,
    *,
    width_chars: int,
    line_gap: int = 10,
) -> int:
    """Draw wrapped text; returns y after last line."""
    x, y = xy
    sample = draw.textbbox((0, 0), "Ag", font=fnt)
    line_h = (sample[3] - sample[1]) + line_gap
    for line in wrap(text, width_chars):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_h
    return y


def chart_png(rows: list[tuple[str, float, float]], labels: tuple[str, str]) -> Image.Image:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [r[0] for r in rows]
    a = [r[1] for r in rows]
    b = [r[2] for r in rows]
    y = range(len(names))
    fig, ax = plt.subplots(figsize=(10.2, 5.2), dpi=160)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    h = 0.32
    ax.barh([i + h / 2 for i in y], a, height=h, color="#2D6A4F", label=labels[0])
    ax.barh([i - h / 2 for i in y], b, height=h, color="#C47D36", label=labels[1])
    ax.set_yticks(list(y))
    ax.set_yticklabels(names, fontsize=13, color="#142018")
    ax.set_xlim(0, 10)
    ax.set_xlabel("Score (1–10)", fontsize=12, color="#5A6E5F")
    ax.tick_params(colors="#5A6E5F")
    for spine in ax.spines.values():
        spine.set_color("#D5E0D4")
    ax.legend(frameon=False, fontsize=11, loc="lower right")
    ax.grid(axis="x", color="#E6EEE4", linestyle="--", alpha=0.9)
    fig.tight_layout(pad=1.2)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def base_canvas(photo_rel: str | None = None, *, darken: float = 0.45) -> Image.Image:
    if photo_rel:
        bg = cover_crop(load_photo(photo_rel), W, H)
        bg = ImageEnhance.Brightness(bg).enhance(darken)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=1.2))
        veil = Image.new("RGBA", (W, H), (20, 32, 24, 110))
        bg = Image.alpha_composite(bg.convert("RGBA"), veil).convert("RGB")
    else:
        bg = Image.new("RGB", (W, H), CREAM)
        draw = ImageDraw.Draw(bg)
        draw.rectangle([(0, 0), (W, 14)], fill=LEAF)
        draw.rectangle([(0, H - 14), (W, H)], fill=HARVEST)
    return bg


def render_title(slide: dict, out: Path) -> None:
    img = base_canvas(slide.get("photo"), darken=0.38)
    draw = ImageDraw.Draw(img)
    card = (80, 140, 980, 940)
    draw.rounded_rectangle([card[:2], card[2:]], radius=28, fill=CARD)
    draw.rectangle([(card[0], card[1]), (card[2], card[1] + 14)], fill=LEAF)

    y = draw_brand(draw, x=card[0] + 48, y=card[1] + 48)
    y += 28
    y = draw_wrapped(draw, (card[0] + 48, y), slide["title"], font(58, bold=True), INK, width_chars=16, line_gap=14)
    y += 24
    y = draw_wrapped(draw, (card[0] + 48, y), slide.get("subtitle", ""), font(28), MUTED, width_chars=32, line_gap=12)
    y += 36
    badge = slide.get("badge", "Comparison")
    bw = max(280, draw.textbbox((0, 0), badge, font=font(26, bold=True))[2] + 64)
    draw.rounded_rectangle([(card[0] + 48, y), (card[0] + 48 + bw, y + 58)], radius=14, fill=LEAF)
    draw.text((card[0] + 72, y + 12), badge, font=font(26, bold=True), fill=CREAM)

    if slide.get("photo_right") or slide.get("photo"):
        rounded_paste(img, load_photo(slide.get("photo_right") or slide["photo"]), (1060, 160, 1840, 920), 28)
    img.save(out)


def render_photo_bullets(slide: dict, out: Path) -> None:
    img = base_canvas(None)
    draw = ImageDraw.Draw(img)
    y = draw_brand(draw, x=64, y=40)
    y += 12
    draw.text((64, y), slide["title"], font=font(46, bold=True), fill=INK)
    title_bottom = y + 70

    photo_box = (64, title_bottom + 24, 860, 1000)
    rounded_paste(img, load_photo(slide["photo"]), photo_box, 28)

    panel = (900, title_bottom + 24, 1856, 1000)
    draw.rounded_rectangle([panel[:2], panel[2:]], radius=28, fill=CARD)
    by = panel[1] + 48
    for bullet in slide.get("bullets", []):
        draw.ellipse([(panel[0] + 40, by + 10), (panel[0] + 62, by + 32)], fill=HARVEST)
        by = draw_wrapped(
            draw,
            (panel[0] + 84, by),
            bullet,
            font(30),
            INK,
            width_chars=36,
            line_gap=10,
        )
        by += 28
    img.save(out)


def render_chart(slide: dict, out: Path) -> None:
    img = base_canvas(None)
    draw = ImageDraw.Draw(img)
    y = draw_brand(draw, x=64, y=36)
    y += 8
    draw.text((64, y), slide["title"], font=font(44, bold=True), fill=INK)
    y += 58
    y = draw_wrapped(draw, (64, y), slide.get("subtitle", ""), font(24), MUTED, width_chars=78, line_gap=8)
    y += 20

    chart = chart_png(slide["rows"], tuple(slide.get("labels", ("A", "B"))))  # type: ignore[arg-type]
    chart_h = min(680, 1000 - y - 40)
    chart_w = 1760
    chart = chart.resize((chart_w, chart_h), Image.Resampling.LANCZOS)
    card_top = y
    draw.rounded_rectangle([(64, card_top), (1856, card_top + chart_h + 48)], radius=24, fill=CARD, outline=LEAF, width=3)
    img.paste(chart, (80, card_top + 24))
    img.save(out)


def render_table(slide: dict, out: Path) -> None:
    img = base_canvas(None)
    draw = ImageDraw.Draw(img)
    y = draw_brand(draw, x=64, y=36)
    y += 8
    draw.text((64, y), slide["title"], font=font(44, bold=True), fill=INK)
    y += 70

    headers = slide["headers"]
    rows = slide["rows"]
    col_w = [400, 660, 660]
    x0 = 80
    row_h = 88
    # header
    draw.rounded_rectangle([(x0, y), (1840, y + 78)], radius=16, fill=LEAF)
    x = x0 + 28
    for i, h in enumerate(headers):
        draw.text((x, y + 22), h, font=font(26, bold=True), fill=CREAM)
        x += col_w[i]
    y += 96
    for ri, row in enumerate(rows):
        bg = CARD if ri % 2 == 0 else (236, 243, 234)
        draw.rounded_rectangle([(x0, y), (1840, y + row_h)], radius=12, fill=bg)
        x = x0 + 28
        for i, cell in enumerate(row):
            color = HARVEST if i == 0 else INK
            # clip long cells with wrap inside column
            cell_lines = wrap(str(cell), 28 if i else 18)
            cy = y + 18 if len(cell_lines) == 1 else y + 10
            for line in cell_lines[:2]:
                draw.text((x, cy), line, font=font(24, bold=(i == 0)), fill=color)
                cy += 30
            x += col_w[i]
        y += row_h + 12
    img.save(out)


def render_split(slide: dict, out: Path) -> None:
    img = base_canvas(None)
    draw = ImageDraw.Draw(img)
    y = draw_brand(draw, x=64, y=36)
    y += 8
    draw.text((64, y), slide["title"], font=font(44, bold=True), fill=INK)
    y += 64

    left, right = slide["left"], slide["right"]
    for box, data, accent in (
        ((64, y, 920, 1000), left, LEAF),
        ((1000, y, 1856, 1000), right, HARVEST),
    ):
        draw.rounded_rectangle([box[:2], box[2:]], radius=28, fill=CARD)
        draw.rectangle([(box[0], box[1]), (box[2], box[1] + 14)], fill=accent)
        photo_bottom = box[1] + 300
        rounded_paste(
            img,
            load_photo(data["photo"]),
            (box[0] + 28, box[1] + 36, box[2] - 28, photo_bottom),
            18,
        )
        ty = photo_bottom + 28
        draw.text((box[0] + 40, ty), data["name"], font=font(32, bold=True), fill=INK)
        ty += 48
        ty = draw_wrapped(draw, (box[0] + 40, ty), data["blurb"], font(24), MUTED, width_chars=30, line_gap=8)
        ty += 18
        for point in data.get("points", []):
            draw.ellipse([(box[0] + 44, ty + 8), (box[0] + 62, ty + 26)], fill=accent)
            draw.text((box[0] + 78, ty), point, font=font(24), fill=INK)
            ty += 40
    img.save(out)


def render_verdict(slide: dict, out: Path) -> None:
    img = base_canvas(slide.get("photo"), darken=0.4)
    draw = ImageDraw.Draw(img)
    card = (160, 140, 1760, 940)
    draw.rounded_rectangle([card[:2], card[2:]], radius=32, fill=CARD)
    draw.rectangle([(card[0], card[1]), (card[2], card[1] + 14)], fill=HARVEST)

    y = draw_brand(draw, x=card[0] + 56, y=card[1] + 44)
    y += 24
    draw.text((card[0] + 56, y), slide["title"], font=font(50, bold=True), fill=INK)
    y += 72
    y = draw_wrapped(draw, (card[0] + 56, y), slide.get("body", ""), font(30), MUTED, width_chars=52, line_gap=12)
    y += 36
    for item in slide.get("picks", []):
        draw.rounded_rectangle([(card[0] + 56, y), (card[2] - 56, y + 78)], radius=16, fill=(236, 243, 234))
        draw.text((card[0] + 84, y + 22), item, font=font(28, bold=True), fill=LEAF_DEEP)
        y += 98
    draw.text((card[0] + 56, min(y + 10, card[3] - 70)), slide.get("cta", "sillgarden.com"), font=font(26), fill=HARVEST)
    img.save(out)


RENDERERS = {
    "title": render_title,
    "photo_bullets": render_photo_bullets,
    "chart": render_chart,
    "table": render_table,
    "split": render_split,
    "verdict": render_verdict,
}


async def synth(text: str, out_mp3: Path, voice: str, idx: int) -> None:
    import edge_tts

    # Prefer plain prosody args (more reliable than hand-rolled SSML).
    # Slight slowdown + soft pitch drift reads less "announcer".
    rates = ["-2%", "+0%", "-3%", "+0%", "-2%", "+1%"]
    pitches = ["+0Hz", "+2Hz", "-1Hz", "+0Hz", "+1Hz", "+0Hz"]
    # Light punctuation pacing: replace em dashes / dense lists with pauses via ellipsis
    spoken = (
        text.replace(" — ", "... ")
        .replace(" – ", "... ")
        .replace(" vs ", " versus ")
        .replace("  ", " ")
        .strip()
    )
    await edge_tts.Communicate(
        spoken,
        voice,
        rate=rates[idx % len(rates)],
        pitch=pitches[idx % len(pitches)],
    ).save(str(out_mp3))


def probe_duration(ffprobe: Path, path: Path) -> float:
    proc = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(proc.stdout.strip())


def make_segment(ffmpeg: Path, ffprobe: Path, png: Path, mp3: Path, out: Path, idx: int) -> None:
    dur = probe_duration(ffprobe, mp3) + 0.55
    zoom = 1.04 + (idx % 3) * 0.01
    vf = f"scale={W}:{H},zoompan=z='min(zoom+0.0012,{zoom})':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=25"
    subprocess.run(
        [
            str(ffmpeg),
            "-y",
            "-loop",
            "1",
            "-i",
            str(png),
            "-i",
            str(mp3),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-af",
            "apad=pad_dur=0.45",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            "-t",
            f"{dur:.2f}",
            str(out),
        ],
        check=True,
        capture_output=True,
    )


def concat(ffmpeg: Path, segments: list[Path], out: Path) -> None:
    lst = out.parent / "concat.txt"
    lst.write_text("\n".join(f"file '{s.resolve().as_posix()}'" for s in segments), encoding="utf-8")
    subprocess.run(
        [str(ffmpeg), "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)],
        check=True,
        capture_output=True,
    )


def write_notes(story: dict, out_dir: Path, mp4: Path, duration: float) -> None:
    chapters = []
    t = 0.0
    for i, slide in enumerate(story["slides"], 1):
        chapters.append(f"{int(t)//60}:{int(t)%60:02d} {slide.get('chapter') or slide['title']}")
        t += 12
    mins, secs = int(duration // 60), int(duration % 60)
    aff = story.get("affiliate_links") or [
        {
            "label": "AeroGarden Harvest-class",
            "url": "https://www.amazon.com/dp/B07CKNWHPQ?tag=sillgarden09-20&linkCode=ll1",
        },
        {
            "label": "Click & Grow Smart Garden 3",
            "url": "https://www.amazon.com/dp/B01MRVMKQH?tag=sillgarden09-20&linkCode=ll1",
        },
    ]
    aff_block = "\n".join(f"• {a['label']}: {a['url']}" for a in aff)
    body = f"""# YouTube upload — {story['title']}

## File to review
`{mp4}`

Duration (approx): {mins}:{secs:02d}

## Title
{story['title']}

## Description
{story.get('description', '')}

Product picks (Amazon Associates — tag sillgarden09-20):
{aff_block}

Full guide:
https://sillgarden.com/guides/aerogarden-vs-click-and-grow/

More apartment garden guides:
https://sillgarden.com/guides/

Disclosure: As an Amazon Associate I earn from qualifying purchases.

Production note: Slides use original site photography + charts; narration is synthetic (edge-tts) for draft review.

## Tags
{', '.join(story.get('tags', []))}

## Suggested chapters
{chr(10).join(chapters)}
"""
    (out_dir / "YOUTUBE-UPLOAD.md").write_text(body, encoding="utf-8")


async def build(story_path: Path) -> Path:
    story = json.loads(story_path.read_text(encoding="utf-8"))
    out_dir = story_path.parent
    build_dir = out_dir / "_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg, ffprobe = find_ffmpeg()
    voice = story.get("voice", "en-US-JennyNeural")
    segments: list[Path] = []

    for i, slide in enumerate(story["slides"]):
        kind = slide["type"]
        if kind not in RENDERERS:
            raise ValueError(f"Unknown slide type: {kind}")
        png = build_dir / f"slide_{i:02d}.png"
        mp3 = build_dir / f"slide_{i:02d}.mp3"
        seg = build_dir / f"seg_{i:02d}.mp4"
        RENDERERS[kind](slide, png)
        await synth(slide["narration"], mp3, voice, i)
        make_segment(ffmpeg, ffprobe, png, mp3, seg, i)
        segments.append(seg)
        print(f"  slide {i+1}/{len(story['slides'])}: {kind} OK")

    mp4 = out_dir / (story.get("filename") or "sill-garden-review.mp4")
    concat(ffmpeg, segments, mp4)
    duration = probe_duration(ffprobe, mp4)
    # thumbnail = first slide scaled
    thumb = Image.open(build_dir / "slide_00.png").resize((1280, 720), Image.Resampling.LANCZOS)
    thumb.save(out_dir / "thumbnail.png")
    write_notes(story, out_dir, mp4, duration)
    print(f"Wrote {mp4} ({duration:.1f}s)")
    return mp4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "storyboard",
        nargs="?",
        default=str(ROOT / "products/youtube/video-aerogarden-vs-click-grow/storyboard.json"),
    )
    args = parser.parse_args()
    path = Path(args.storyboard)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    print(f"Building {path}")
    asyncio.run(build(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
