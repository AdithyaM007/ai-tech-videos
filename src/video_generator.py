"""Stage 3: turn a script + voiceover into an MP4 video.

Pipeline: slides / code-typing frames / diagrams are rendered as PNG images,
timed against the voiceover length, and assembled with MoviePy.
"""

from __future__ import annotations

import json
import logging
import os
import textwrap
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from pygments import lex  # noqa: E402
from pygments.lexers import PythonLexer  # noqa: E402
from pygments.styles import get_style_by_name  # noqa: E402

import config  # noqa: E402

logger = logging.getLogger(__name__)

# (image path, seconds on screen)
Segment = Tuple[str, float]

MONO_FONTS = ("DejaVuSansMono.ttf", "consola.ttf", "Menlo.ttc", "LiberationMono-Regular.ttf")
SANS_FONTS = ("DejaVuSans.ttf", "segoeui.ttf", "arial.ttf", "Arial.ttf", "Helvetica.ttc")
SANS_BOLD_FONTS = ("DejaVuSans-Bold.ttf", "segoeuib.ttf", "arialbd.ttf", "Arial Bold.ttf")

DEFAULT_COMPARISON: List[Tuple[str, float]] = [
    ("Python", 9.5),
    ("JavaScript", 7.5),
    ("Java", 6.0),
    ("C++", 4.0),
]
DEFAULT_INSTALL_STEPS: List[str] = [
    "Go to python.org",
    "Download the installer",
    "Tick 'Add Python to PATH'",
    "Run the installer",
    "Verify: python --version",
]


def load_font(size: int, candidates: Sequence[str] = SANS_FONTS) -> ImageFont.FreeTypeFont:
    """Load the first available TrueType font from ``candidates``."""
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)  # type: ignore[return-value]


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def frames_to_segments(frames: Sequence[str], fps: int) -> List[Segment]:
    """Collapse consecutive identical frame paths into ``(path, duration)`` runs."""
    segments: List[Segment] = []
    for path in frames:
        if segments and segments[-1][0] == path:
            segments[-1] = (path, segments[-1][1] + 1.0 / fps)
        else:
            segments.append((path, 1.0 / fps))
    return segments


class CodeAnimationGenerator:
    """Renders a "typing" animation of syntax-highlighted Python code."""

    def __init__(
        self,
        width: int = config.VIDEO_WIDTH,
        height: int = config.VIDEO_HEIGHT,
        fps: int = config.VIDEO_FPS,
        typing_speed: int = config.CODE_TYPING_SPEED,
        font_size: int = config.CODE_FONT_SIZE,
    ) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.typing_speed = max(1, typing_speed)
        self.font_size = font_size
        self.style = get_style_by_name("monokai")

    def generate_code_animation(
        self,
        code_text: str,
        output_dir: str,
        duration_seconds: float = config.CODE_ANIMATION_SECONDS,
        prefix: str = "code_frame",
        title: str = "",
    ) -> List[str]:
        """Return one frame path per video frame for ``duration_seconds``.

        Only distinct frames are rendered; frames where the visible text does
        not change reuse the previous image path, so the list length always
        equals ``duration_seconds * fps`` while disk usage stays small.
        """
        os.makedirs(output_dir, exist_ok=True)
        total_frames = max(1, int(round(duration_seconds * self.fps)))
        # Leave at least a third of the clip to hold the finished code.
        typing_frames = min(
            -(-len(code_text) // self.typing_speed), max(1, (total_frames * 2) // 3)
        )
        chars_per_frame = max(self.typing_speed, -(-len(code_text) // max(1, typing_frames)))

        frames: List[str] = []
        last_visible = -1
        last_path = ""
        for index in range(total_frames):
            visible = min(len(code_text), (index + 1) * chars_per_frame)
            if visible != last_visible:
                last_path = os.path.join(output_dir, f"{prefix}_{index:04d}.png")
                self._render_code_frame(
                    code_text[:visible], last_path, title=title, cursor=visible < len(code_text)
                )
                last_visible = visible
            frames.append(last_path)
        return frames

    def render_static_code(self, code_text: str, output_path: str, title: str = "") -> str:
        """Render the full code block as a single image."""
        self._render_code_frame(code_text, output_path, title=title, cursor=False)
        return output_path

    def _render_code_frame(
        self, code_text: str, output_path: str, title: str = "", cursor: bool = False
    ) -> None:
        """Draw syntax-highlighted ``code_text`` onto a slide-sized PNG."""
        theme = config.THEME
        image = Image.new("RGB", (self.width, self.height), _hex_to_rgb(theme["background"]))
        draw = ImageDraw.Draw(image)
        font = load_font(self.font_size, MONO_FONTS)
        margin = 60
        top = margin

        if title:
            draw.text(
                (margin, top), title, font=load_font(34, SANS_BOLD_FONTS), fill=theme["accent"]
            )
            top += 70

        # Editor panel.
        draw.rounded_rectangle(
            (margin - 20, top - 20, self.width - margin + 20, self.height - margin + 20),
            radius=16,
            fill=_hex_to_rgb(theme["surface"]),
        )
        line_height = int(self.font_size * 1.45)
        x, y = margin, top
        fallback = "#f8f8f2"
        lexer = PythonLexer(stripnl=False, ensurenl=False)

        for token_type, value in lex(code_text, lexer) if code_text else []:
            color = self.style.style_for_token(token_type).get("color")
            fill = f"#{color}" if color else fallback
            for part_index, part in enumerate(value.split("\n")):
                if part_index > 0:
                    x, y = margin, y + line_height
                if part:
                    draw.text((x, y), part, font=font, fill=fill)
                    x += int(draw.textlength(part, font=font))
        if cursor:
            draw.rectangle((x + 2, y + 2, x + 4, y + self.font_size), fill=theme["accent"])
        image.save(output_path)


class DiagramGenerator:
    """Creates explanatory diagrams with matplotlib."""

    def __init__(self, width: int = config.VIDEO_WIDTH, height: int = config.VIDEO_HEIGHT) -> None:
        self.width = width
        self.height = height
        self.dpi = 100

    def _figure(self) -> Tuple[Any, Any]:
        fig, ax = plt.subplots(
            figsize=(self.width / self.dpi, self.height / self.dpi), dpi=self.dpi
        )
        fig.patch.set_facecolor(config.THEME["background"])
        ax.set_facecolor(config.THEME["background"])
        return fig, ax

    def _save(self, fig: Any, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fig.savefig(output_path, dpi=self.dpi, facecolor=fig.get_facecolor())
        plt.close(fig)
        return output_path

    def generate_comparison_chart(
        self,
        title: str,
        items: Optional[Sequence[Any]],
        output_path: str,
        value_label: str = "Beginner friendliness (0-10)",
    ) -> str:
        """Horizontal bar chart. ``items`` is ``[(label, value)]`` or ``[{label, value}]``."""
        pairs: List[Tuple[str, float]] = []
        for item in items or []:
            if isinstance(item, dict):
                pairs.append((str(item.get("label", "")), float(item.get("value", 0))))
            else:
                pairs.append((str(item[0]), float(item[1])))
        if not pairs:
            pairs = list(DEFAULT_COMPARISON)

        theme = config.THEME
        fig, ax = self._figure()
        labels = [label for label, _ in pairs][::-1]
        values = [value for _, value in pairs][::-1]
        colors = [theme["accent2"]] * len(values)
        colors[-1] = theme["accent"]
        ax.barh(labels, values, color=colors, height=0.6)
        for idx, value in enumerate(values):
            ax.text(value + 0.1, idx, f"{value:g}", va="center", color=theme["text"], fontsize=16)
        ax.set_title(title, color=theme["text"], fontsize=28, pad=24, fontweight="bold")
        ax.set_xlabel(value_label, color=theme["muted"], fontsize=14)
        ax.tick_params(colors=theme["text"], labelsize=18)
        for spine in ax.spines.values():
            spine.set_visible(False)
        fig.tight_layout(pad=2.5)
        return self._save(fig, output_path)

    def generate_flowchart(self, title: str, steps: Sequence[str], output_path: str) -> str:
        """Left-to-right (wrapping) flowchart of ``steps``."""
        theme = config.THEME
        steps = list(steps) or ["Start", "Finish"]
        fig, ax = self._figure()
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis("off")
        ax.text(
            50,
            92,
            title,
            ha="center",
            va="center",
            color=theme["text"],
            fontsize=28,
            fontweight="bold",
        )

        per_row = 3 if len(steps) > 4 else len(steps)
        rows = -(-len(steps) // per_row)
        box_w, box_h = 24.0, 14.0
        positions: List[Tuple[float, float]] = []
        for index in range(len(steps)):
            row, col = divmod(index, per_row)
            if row % 2 == 1:  # snake layout keeps arrows short
                col = per_row - 1 - col
            spacing = 100 / per_row
            cx = spacing * col + spacing / 2
            cy = 70 - row * (60 / max(1, rows))
            positions.append((cx, cy))

        for index, (step, (cx, cy)) in enumerate(zip(steps, positions)):
            color = theme["accent"] if index in (0, len(steps) - 1) else theme["accent2"]
            ax.add_patch(
                FancyBboxPatch(
                    (cx - box_w / 2, cy - box_h / 2),
                    box_w,
                    box_h,
                    boxstyle="round,pad=0.6,rounding_size=2",
                    facecolor=color,
                    edgecolor="none",
                )
            )
            text_color = theme["background"] if color == theme["accent"] else theme["text"]
            ax.text(
                cx,
                cy,
                "\n".join(textwrap.wrap(step, 18)),
                ha="center",
                va="center",
                color=text_color,
                fontsize=15,
                fontweight="bold",
            )
            if index > 0:
                (px, py) = positions[index - 1]
                ax.add_patch(
                    FancyArrowPatch(
                        _edge(px, py, cx, cy, box_w, box_h),
                        _edge(cx, cy, px, py, box_w, box_h),
                        arrowstyle="-|>",
                        mutation_scale=24,
                        color=theme["muted"],
                        linewidth=2,
                    )
                )
        return self._save(fig, output_path)

    def generate_installation_flow(self, output_path: str) -> str:
        """Flowchart of the Python installation steps."""
        return self.generate_flowchart("Installing Python", DEFAULT_INSTALL_STEPS, output_path)

    def generate_concept_card(self, title: str, description: str, output_path: str) -> str:
        """Fallback diagram: a titled card with the description text."""
        theme = config.THEME
        fig, ax = self._figure()
        ax.axis("off")
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.add_patch(
            FancyBboxPatch(
                (8, 12),
                84,
                70,
                boxstyle="round,pad=0.5,rounding_size=3",
                facecolor=theme["surface"],
                edgecolor=theme["accent2"],
                linewidth=3,
            )
        )
        ax.text(
            50,
            90,
            title,
            ha="center",
            va="center",
            color=theme["accent"],
            fontsize=28,
            fontweight="bold",
        )
        ax.text(
            50,
            47,
            "\n".join(textwrap.wrap(description or title, 50)),
            ha="center",
            va="center",
            color=theme["text"],
            fontsize=20,
        )
        return self._save(fig, output_path)


def _edge(x1: float, y1: float, x2: float, y2: float, w: float, h: float) -> Tuple[float, float]:
    """Point on the box centred at (x1, y1) facing (x2, y2)."""
    if abs(x2 - x1) * h >= abs(y2 - y1) * w:
        return (x1 + (w / 2 + 1) * (1 if x2 > x1 else -1), y1)
    return (x1, y1 + (h / 2 + 2) * (1 if y2 > y1 else -1))


class SlideGenerator:
    """Creates title, content and closing slides with Pillow."""

    def __init__(self, width: int = config.VIDEO_WIDTH, height: int = config.VIDEO_HEIGHT) -> None:
        self.width = width
        self.height = height

    def _canvas(self) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
        image = Image.new("RGB", (self.width, self.height), _hex_to_rgb(config.THEME["background"]))
        draw = ImageDraw.Draw(image)
        # Accent bar along the top.
        draw.rectangle((0, 0, self.width, 10), fill=config.THEME["accent2"])
        draw.rectangle((0, 10, self.width, 16), fill=config.THEME["accent"])
        return image, draw

    def _centered(
        self, draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.FreeTypeFont, fill: str
    ) -> int:
        """Draw centred text (wrapped) starting at ``y``; return the next y."""
        max_chars = max(10, int(self.width / (font.size * 0.55)))
        for line in textwrap.wrap(text, max_chars) or [""]:
            width = draw.textlength(line, font=font)
            draw.text(((self.width - width) / 2, y), line, font=font, fill=fill)
            y += int(font.size * 1.3)
        return y

    def create_title_slide(
        self, series_title: str, episode_number: Any, title: str, subtitle: str, output_path: str
    ) -> str:
        """Episode title card."""
        theme = config.THEME
        image, draw = self._canvas()
        y = int(self.height * 0.25)
        y = self._centered(
            draw,
            y,
            f"{series_title} · Episode {episode_number}",
            load_font(32, SANS_FONTS),
            theme["accent"],
        )
        y = self._centered(draw, y + 30, title, load_font(72, SANS_BOLD_FONTS), theme["text"])
        if subtitle:
            self._centered(draw, y + 20, subtitle, load_font(34, SANS_FONTS), theme["muted"])
        image.save(output_path)
        return output_path

    def create_content_slide(self, title: str, bullets: Sequence[str], output_path: str) -> str:
        """Section slide with a heading and bullet points."""
        theme = config.THEME
        image, draw = self._canvas()
        margin = 90
        draw.text((margin, 70), title, font=load_font(54, SANS_BOLD_FONTS), fill=theme["accent"])
        font = load_font(34, SANS_FONTS)
        y = 190
        max_chars = int((self.width - margin * 2 - 40) / (font.size * 0.52))
        for bullet in list(bullets)[:6]:
            lines = textwrap.wrap(str(bullet), max_chars) or [""]
            draw.ellipse((margin, y + 14, margin + 14, y + 28), fill=theme["accent2"])
            for line in lines[:2]:
                draw.text((margin + 36, y), line, font=font, fill=theme["text"])
                y += int(font.size * 1.3)
            y += 18
            if y > self.height - 80:
                break
        image.save(output_path)
        return output_path

    def create_closing_slide(
        self, key_learnings: Sequence[str], next_title: str, output_path: str
    ) -> str:
        """Recap slide with a call to action."""
        theme = config.THEME
        image, draw = self._canvas()
        y = self._centered(
            draw, 60, "What you learned", load_font(56, SANS_BOLD_FONTS), theme["accent"]
        )
        font = load_font(32, SANS_FONTS)
        y += 20
        for item in list(key_learnings)[:5]:
            y = self._centered(draw, y, f"✓ {item}", font, theme["text"])
        cta = "Subscribe so you don't miss the next episode!"
        if next_title:
            cta = f"Next up: {next_title} — subscribe so you don't miss it!"
        self._centered(
            draw, self.height - 140, cta, load_font(30, SANS_BOLD_FONTS), theme["accent2"]
        )
        image.save(output_path)
        return output_path


class AdvancedVideoGenerator:
    """Builds the full episode video from a script JSON and voiceover MP3."""

    def __init__(
        self,
        width: int = config.VIDEO_WIDTH,
        height: int = config.VIDEO_HEIGHT,
        fps: int = config.VIDEO_FPS,
    ) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.code_animator = CodeAnimationGenerator(width, height, fps)
        self.diagrams = DiagramGenerator(width, height)
        self.slides = SlideGenerator(width, height)
        self.images_dir = config.IMAGES_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_episode_video(
        self,
        script_path: str,
        audio_path: str,
        output_path: str,
        images_dir: Optional[str] = None,
    ) -> str:
        """Render all visuals, time them to the audio and write ``output_path``."""
        with open(script_path, encoding="utf-8") as f:
            script: Dict[str, Any] = json.load(f)

        episode = int(script.get("episode", 0) or 0)
        self.images_dir = images_dir or os.path.join(config.IMAGES_DIR, f"ep{episode:02d}")
        os.makedirs(self.images_dir, exist_ok=True)

        audio_duration = self._get_audio_duration(audio_path)
        plan = self.build_timeline(script, audio_duration)
        logger.info("Timeline: %d segments over %.1fs", len(plan), audio_duration)
        return self._assemble_video(plan, audio_path, output_path)

    def build_timeline(self, script: Dict[str, Any], total_seconds: float) -> List[Segment]:
        """Render every visual and return ``(image, seconds)`` segments.

        Durations are distributed proportionally to each part's scripted
        length and scaled so they sum to ``total_seconds``.
        """
        weights = [weight for _, weight in part_weights(script)]
        parts: List[Tuple[List[Segment], float]] = [
            ([(self._create_title_slide(script), 1.0)], weights[0])
        ]
        for index, section in enumerate(script.get("sections", [])):
            parts.append((self._create_section_slides(section, script, index), weights[index + 1]))
        parts.append(([(self._create_closing_slide(script), 1.0)], weights[-1]))

        total_weight = sum(weight for _, weight in parts) or 1.0
        timeline: List[Segment] = []
        for segments, weight in parts:
            budget = total_seconds * weight / total_weight
            timeline.extend(_scale_segments(segments, budget))
        return timeline

    # ------------------------------------------------------------------
    # Visual builders
    # ------------------------------------------------------------------
    def _path(self, name: str) -> str:
        return os.path.join(self.images_dir, name)

    def _create_title_slide(self, script: Dict[str, Any]) -> str:
        episode = script.get("episode", "")
        series = config.SERIES.get(script.get("series", "python_basics"), {})
        subtitle = ""
        for ep in series.get("episodes", []):
            if ep.get("episode") == episode:
                subtitle = ep.get("subtitle", "")
        return self.slides.create_title_slide(
            series.get("title", "Python Basics"),
            episode,
            script.get("episode_title", ""),
            subtitle,
            self._path(f"title_{_as_int(episode):02d}.png"),
        )

    def _create_section_slides(
        self, section: Dict[str, Any], script: Dict[str, Any], index: int = 0
    ) -> List[Segment]:
        """Content slide, then code animations, then diagrams for one section.

        Returned durations are relative weights (scaled later).
        """
        segments: List[Segment] = [(self._create_content_slide(section, index), 3.0)]

        for block_index, block in enumerate(section.get("code_blocks", []) or []):
            code = str(block.get("code", "")).rstrip()
            if not code:
                continue
            weight = float(block.get("timing_seconds") or 20)
            prefix = f"code_s{index:02d}_b{block_index:02d}"
            if config.CODE_ANIMATION_ENABLED:
                frames = self.code_animator.generate_code_animation(
                    code,
                    self.images_dir,
                    config.CODE_ANIMATION_SECONDS,
                    prefix=prefix,
                    title=block.get("explanation", ""),
                )
                typing = frames_to_segments(frames, self.fps)
                # Typing plays in real time; the final frame absorbs the rest.
                segments.append(("__fixed__", 0.0))
                segments.extend(typing[:-1])
                segments.append((typing[-1][0], max(weight, 1.0)))
                segments.append(("__endfixed__", 0.0))
            else:
                path = self.code_animator.render_static_code(
                    code, self._path(f"{prefix}.png"), title=block.get("explanation", "")
                )
                segments.append((path, max(weight, 1.0)))

        for diagram_index, diagram in enumerate(section.get("diagrams", []) or []):
            diagram_path = self._generate_diagram(diagram, f"s{index:02d}_d{diagram_index:02d}")
            if diagram_path:
                segments.append((diagram_path, 10.0))
        return segments

    def _create_content_slide(self, section: Dict[str, Any], index: int = 0) -> str:
        bullets = section.get("key_points") or _summarize(section.get("script", ""))
        return self.slides.create_content_slide(
            section.get("title", f"Part {index + 1}"),
            bullets,
            self._path(f"section_{index:02d}.png"),
        )

    def _generate_diagram(self, diagram: Any, suffix: str = "") -> Optional[str]:
        """Dispatch a diagram spec to the right generator; ``None`` on failure."""
        if isinstance(diagram, str):
            diagram = {"name": diagram}
        name = str(diagram.get("name", "diagram"))
        kind = str(diagram.get("type", "")).lower()
        description = str(diagram.get("description", ""))
        path = self._path(f"diagram_{name}_{suffix}.png" if suffix else f"diagram_{name}.png")
        title = name.replace("_", " ").title()
        try:
            if "install" in name:
                return self.diagrams.generate_installation_flow(path)
            if name == "python_vs_languages" or kind == "chart":
                return self.diagrams.generate_comparison_chart(
                    description or "Python vs Other Languages", diagram.get("items"), path
                )
            if kind == "flowchart" and diagram.get("steps"):
                return self.diagrams.generate_flowchart(title, diagram["steps"], path)
            return self.diagrams.generate_concept_card(title, description, path)
        except Exception:  # a broken diagram should not kill the whole video
            logger.exception("Failed to render diagram %s", name)
            return None

    def _create_closing_slide(self, script: Dict[str, Any]) -> str:
        episode = _as_int(script.get("episode", 0))
        next_title = ""
        series = config.SERIES.get(script.get("series", "python_basics"), {})
        for ep in series.get("episodes", []):
            if ep.get("episode") == episode + 1:
                next_title = ep.get("title", "")
        return self.slides.create_closing_slide(
            script.get("key_learnings", []), next_title, self._path(f"closing_{episode:02d}.png")
        )

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------
    @staticmethod
    def _get_audio_duration(audio_path: str) -> float:
        from compat import patch_pil_antialias

        patch_pil_antialias()
        from moviepy.editor import AudioFileClip

        clip = AudioFileClip(audio_path)
        try:
            return float(clip.duration)
        finally:
            clip.close()

    def _assemble_video(
        self, image_paths: Sequence[Segment], audio_path: str, output_path: str
    ) -> str:
        """Concatenate timed image segments, add the audio track and encode."""
        from compat import patch_pil_antialias

        patch_pil_antialias()
        from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        audio = AudioFileClip(audio_path)
        clips = [
            ImageClip(path).set_duration(duration) for path, duration in image_paths if duration > 0
        ]
        video = concatenate_videoclips(clips, method="chain").set_audio(audio)
        video = video.set_duration(audio.duration)
        try:
            video.write_videofile(
                output_path,
                fps=self.fps,
                codec=config.VIDEO_CODEC,
                audio_codec=config.AUDIO_CODEC,
                threads=os.cpu_count() or 2,
                preset="medium",
                logger=None,
            )
        finally:
            audio.close()
            video.close()
        logger.info("Wrote video to %s", output_path)
        return output_path


# ----------------------------------------------------------------------
# Timing helpers
# ----------------------------------------------------------------------
def part_weights(script: Dict[str, Any]) -> List[Tuple[str, float]]:
    """``(chapter title, relative weight)`` for intro, each section and outro.

    Shared by :meth:`AdvancedVideoGenerator.build_timeline` and
    :func:`compute_chapters` so chapter timestamps match the rendered video.
    """
    intro = _word_seconds(script.get("hook", "")) + _word_seconds(script.get("intro", ""))
    parts: List[Tuple[str, float]] = [("Introduction", max(intro, 5.0))]
    for index, section in enumerate(script.get("sections", []) or []):
        weight = float(section.get("duration_seconds") or _word_seconds(section.get("script", "")))
        parts.append((str(section.get("title") or f"Part {index + 1}"), max(weight, 5.0)))
    parts.append(("Recap", max(_word_seconds(script.get("outro", "")), 5.0)))
    return parts


def compute_chapters(script: Dict[str, Any], total_seconds: float) -> List[Tuple[str, float]]:
    """Return ``(title, start_seconds)`` for each part of the video."""
    parts = part_weights(script)
    total_weight = sum(weight for _, weight in parts) or 1.0
    chapters: List[Tuple[str, float]] = []
    start = 0.0
    for title, weight in parts:
        chapters.append((title, start))
        start += total_seconds * weight / total_weight
    return chapters


def _word_seconds(text: str, words_per_second: float = 2.5) -> float:
    return len(str(text).split()) / words_per_second


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _summarize(text: str, max_points: int = 4) -> List[str]:
    """Pick the first few sentences of narration as slide bullets."""
    sentences = [s.strip() for s in str(text).replace("\n", " ").split(". ") if s.strip()]
    return [textwrap.shorten(s.rstrip("."), 90, placeholder="…") for s in sentences[:max_points]]


def _scale_segments(segments: Sequence[Segment], budget: float) -> List[Segment]:
    """Scale relative durations to fill ``budget`` seconds.

    Segments between ``__fixed__`` / ``__endfixed__`` markers keep their real
    durations (typing animation), except the last one in each block which is
    scaled like any other segment.
    """
    fixed: List[Segment] = []
    flexible_weight = 0.0
    in_fixed = False
    marked: List[Tuple[str, float, bool]] = []
    for path, duration in segments:
        if path == "__fixed__":
            in_fixed = True
            continue
        if path == "__endfixed__":
            in_fixed = False
            # Last typed frame is the "hold" frame: flexible.
            last_path, last_duration, _ = marked[-1]
            marked[-1] = (last_path, last_duration, False)
            continue
        marked.append((path, duration, in_fixed))

    fixed = [(p, d) for p, d, is_fixed in marked if is_fixed]
    fixed_total = sum(d for _, d in fixed)
    flexible_weight = sum(d for _, d, is_fixed in marked if not is_fixed) or 1.0
    remaining = max(budget - fixed_total, 0.5 * len(marked))

    return [
        (path, duration if is_fixed else remaining * duration / flexible_weight)
        for path, duration, is_fixed in marked
    ]
