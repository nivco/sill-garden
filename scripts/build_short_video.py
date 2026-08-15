#!/usr/bin/env python3
"""Build a native 9:16 Sill Garden YouTube Short from a storyboard."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1080, 1920
LEAF = (52, 145, 83)
LEAF_DARK = (13, 36, 24)
CREAM = (247, 249, 241)
MUTED = (200, 216, 204)
GOLD = (229, 160, 74)


def find_media_tools() -> tuple[Path, Path]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe must be available on PATH")
    return Path(ffmpeg), Path(ffprobe)


def font(size: int, *, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_ratio = size[0] / size[1]
    ratio = image.width / image.height
    if ratio > target_ratio:
        new_h = size[1]
        new_w = round(new_h * ratio)
    else:
        new_w = size[0]
        new_h = round(new_w / ratio)
    image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - size[0]) // 2
    top = (new_h - size[1]) // 2
    return image.crop((left, top, left + size[0], top + size[1]))


def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, face, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            width = draw.textbbox((0, 0), candidate, font=face)[2]
            if width <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    y: int,
    face,
    fill,
    spacing: int,
    max_width: int,
) -> int:
    for line in lines:
        box = draw.textbbox((0, 0), line, font=face)
        width = box[2] - box[0]
        draw.text(((W - width) // 2, y), line, font=face, fill=fill)
        y += spacing
    return y


def render_slide(slide: dict, out: Path, index: int, total: int) -> None:
    source = ROOT / "public" / "images" / slide["photo"]
    if not source.is_file():
        raise FileNotFoundError(f"Missing Short photo: {source}")
    photo = Image.open(source).convert("RGB")
    photo = ImageEnhance.Color(photo).enhance(1.08)
    photo = ImageEnhance.Contrast(photo).enhance(1.05)
    canvas = cover(photo, (W, H)).filter(ImageFilter.GaussianBlur(radius=0.4)).convert("RGBA")

    # A soft full-frame shade plus a strong lower gradient keeps every caption readable.
    shade = Image.new("RGBA", (W, H), (7, 22, 14, 42))
    gradient = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pixels = gradient.load()
    for y in range(430, H):
        strength = min(242, round(35 + ((y - 430) / (H - 430)) * 220))
        for x in range(W):
            pixels[x, y] = (*LEAF_DARK, strength)
    canvas = Image.alpha_composite(canvas, shade)
    canvas = Image.alpha_composite(canvas, gradient)
    draw = ImageDraw.Draw(canvas)

    # Brand and slide counter.
    draw.rounded_rectangle((62, 68, 420, 148), radius=38, fill=(*LEAF_DARK, 225), outline=(*LEAF, 255), width=3)
    draw.text((92, 87), "SILL GARDEN", font=font(36, bold=True), fill=CREAM)
    counter = f"{index + 1}/{total}"
    counter_face = font(34, bold=True)
    counter_w = draw.textbbox((0, 0), counter, font=counter_face)[2]
    draw.text((W - 72 - counter_w, 91), counter, font=counter_face, fill=CREAM)

    eyebrow_face = font(38, bold=True)
    headline_face = font(104, bold=True)
    subhead_face = font(46)
    accent_face = font(34, bold=True)

    eyebrow = slide.get("eyebrow", "").upper()
    eyebrow_w = draw.textbbox((0, 0), eyebrow, font=eyebrow_face)[2]
    draw.text(((W - eyebrow_w) // 2, 775), eyebrow, font=eyebrow_face, fill=GOLD)

    headline = wrapped_lines(draw, slide["headline"], headline_face, 920)
    y = draw_lines(
        draw,
        headline,
        y=852,
        face=headline_face,
        fill=CREAM,
        spacing=122,
        max_width=920,
    )
    y += 32
    subhead = wrapped_lines(draw, slide.get("subhead", ""), subhead_face, 850)
    y = draw_lines(
        draw,
        subhead,
        y=y,
        face=subhead_face,
        fill=MUTED,
        spacing=62,
        max_width=850,
    )

    accent = slide.get("accent", "").upper()
    accent_w = draw.textbbox((0, 0), accent, font=accent_face)[2]
    pill_left = (W - accent_w) // 2 - 34
    pill_top = min(max(y + 70, 1560), 1680)
    draw.rounded_rectangle(
        (pill_left, pill_top, pill_left + accent_w + 68, pill_top + 72),
        radius=34,
        fill=(*LEAF, 235),
    )
    draw.text((pill_left + 34, pill_top + 16), accent, font=accent_face, fill=(255, 255, 255))

    draw.text((72, 1818), "Apartment garden decisions, without the hype.", font=font(29), fill=MUTED)
    canvas.convert("RGB").save(out, quality=95)


async def synth(text: str, out: Path, voice: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate="+4%", pitch="-2Hz")
    await communicate.save(str(out))


def duration(ffprobe: Path, media: Path) -> float:
    result = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def make_segment(ffmpeg: Path, ffprobe: Path, image: Path, audio: Path, out: Path) -> None:
    seconds = duration(ffprobe, audio) + 0.7
    fade_out = max(0.1, seconds - 0.25)
    subprocess.run(
        [
            str(ffmpeg),
            "-y",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(image),
            "-i",
            str(audio),
            "-t",
            f"{seconds:.3f}",
            "-vf",
            f"fade=t=in:st=0:d=0.2,fade=t=out:st={fade_out:.3f}:d=0.25,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "48000",
            "-shortest",
            str(out),
        ],
        capture_output=True,
        check=True,
    )


async def build(story_path: Path) -> Path:
    story = json.loads(story_path.read_text(encoding="utf-8"))
    out_dir = story_path.parent
    build_dir = out_dir / "_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg, ffprobe = find_media_tools()
    voice = story.get("voice", "en-US-AvaMultilingualNeural")
    segments: list[Path] = []

    for index, slide in enumerate(story["slides"]):
        png = build_dir / f"slide_{index:02d}.png"
        mp3 = build_dir / f"slide_{index:02d}.mp3"
        segment = build_dir / f"segment_{index:02d}.mp4"
        render_slide(slide, png, index, len(story["slides"]))
        await synth(slide["narration"], mp3, voice)
        make_segment(ffmpeg, ffprobe, png, mp3, segment)
        segments.append(segment)
        print(f"  short slide {index + 1}/{len(story['slides'])} OK")

    concat_file = build_dir / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{segment.resolve().as_posix()}'" for segment in segments),
        encoding="utf-8",
    )
    output = out_dir / story.get("filename", f"{story.get('id', 'sill-short')}.mp4")
    subprocess.run(
        [
            str(ffmpeg),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output),
        ],
        capture_output=True,
        check=True,
    )
    seconds = duration(ffprobe, output)
    if seconds > 60:
        raise RuntimeError(f"Short is {seconds:.1f}s; narration must remain under 60 seconds")
    print(f"Wrote {output} ({seconds:.1f}s, 9:16)")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("storyboard")
    args = parser.parse_args()
    path = Path(args.storyboard)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    asyncio.run(build(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
