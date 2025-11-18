from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Optional, Tuple

import qrcode
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageTk
import tkinter.font as tkfont
from pathlib import Path
from functools import lru_cache

from data_model import MainConfig

FONT_EXTENSIONS = (".ttf", ".otf", ".ttc", ".dfont")
FONT_DIRECTORIES = [
    "~/Library/Fonts",
    "/Library/Fonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "C:/Windows/Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "~/.fonts",
]


class PictureEditor:
    def __init__(self, parent: tk.Tk, base_image: Image.Image, config: MainConfig):
        self.parent = parent
        self.base_image = base_image.convert("RGBA")
        self.config = config
        self.window: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
        self.canvas_image: Optional[ImageTk.PhotoImage] = None
        self.text_item: Optional[int] = None
        self.qr_item: Optional[int] = None
        self.qr_photo: Optional[ImageTk.PhotoImage] = None
        self.qr_image: Optional[Image.Image] = None

        self.text_var = tk.StringVar(value=config.callsign)
        self.text_size_var = tk.IntVar(value=max(16, self.base_image.width // 8))
        self.text_color = "#ffffff"
        self.qr_enabled = tk.BooleanVar(value=bool(config.overlay_url))
        self.qr_size_var = tk.IntVar(value=max(40, min(self.base_image.size) // 4))

        self.active_item: Optional[int] = None
        self.drag_offset: Tuple[float, float] = (0.0, 0.0)
        self.result_image: Optional[Image.Image] = None
        self.current_font: Optional[tkfont.Font] = None
        self.text_font_family = self._default_font_family()

    def show(self) -> Optional[Image.Image]:
        self.window = tk.Toplevel(self.parent)
        self.window.title("Picture Editor")
        self.window.transient(self.parent)
        self.window.grab_set()

        self.canvas = tk.Canvas(
            self.window,
            width=self.base_image.width,
            height=self.base_image.height,
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.grid(row=0, column=0, rowspan=6, sticky="nsew", padx=10, pady=10)
        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(0, weight=1)

        self.canvas_image = ImageTk.PhotoImage(self.base_image)
        self.canvas.create_image(0, 0, image=self.canvas_image, anchor="nw")

        self.text_item = self.canvas.create_text(
            self.base_image.width // 2,
            self.base_image.height - 20,
            text=self.text_var.get(),
            fill=self.text_color,
            font=(self.text_font_family, self.text_size_var.get()),
            tags=("overlay", "text_overlay"),
        )
        self.current_font = tkfont.Font(root=self.parent, font=self.canvas.itemcget(self.text_item, "font"))
        self.text_font_family = self.current_font.actual("family")

        control_frame = ttk.Frame(self.window, padding=(5, 10))
        control_frame.grid(row=0, column=1, sticky="n")

        ttk.Label(control_frame, text="Text Overlay").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Entry(control_frame, textvariable=self.text_var, width=20).grid(row=1, column=0, columnspan=2, pady=2)
        ttk.Label(control_frame, text="Size").grid(row=2, column=0, sticky="e")
        size_scale = ttk.Scale(
            control_frame,
            from_=10,
            to=max(30, self.base_image.width // 4),
            orient="horizontal",
            variable=self.text_size_var,
            command=lambda *_: self._update_text_item(),
        )
        size_scale.grid(row=2, column=1, sticky="ew", padx=5)
        control_frame.columnconfigure(1, weight=1)

        ttk.Button(control_frame, text="Color", command=self._choose_color).grid(row=3, column=0, pady=5)
        ttk.Button(control_frame, text="Apply Text", command=self._update_text_item).grid(row=3, column=1, pady=5)

        ttk.Separator(control_frame, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(control_frame, text="QR Overlay").grid(row=5, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(
            control_frame,
            text="Enable (uses overlay URL)",
            variable=self.qr_enabled,
            command=self._toggle_qr,
        ).grid(row=6, column=0, columnspan=2, sticky="w")
        ttk.Label(control_frame, text="Size").grid(row=7, column=0, sticky="e")
        self.qr_scale = ttk.Scale(
            control_frame,
            from_=30,
            to=max(80, min(self.base_image.size)),
            orient="horizontal",
            variable=self.qr_size_var,
            command=lambda *_: self._update_qr_item(),
        )
        self.qr_scale.grid(row=7, column=1, sticky="ew", padx=5)

        self._create_qr_item()

        ttk.Button(control_frame, text="Save Overlay", command=self._save).grid(
            row=8, column=0, pady=(20, 0), sticky="ew"
        )
        ttk.Button(control_frame, text="Cancel", command=self._cancel).grid(
            row=8, column=1, pady=(20, 0), sticky="ew"
        )

        self.canvas.tag_bind("overlay", "<ButtonPress-1>", self._start_drag)
        self.canvas.tag_bind("overlay", "<B1-Motion>", self._drag)
        self.canvas.tag_bind("overlay", "<ButtonRelease-1>", self._end_drag)

        self.window.wait_window()
        return self.result_image

    # ------------------------------------------------------------------
    def _update_text_item(self) -> None:
        if not self.canvas or self.text_item is None:
            return
        value = self.text_var.get()
        family = self.text_font_family or self._default_font_family()
        self.canvas.itemconfigure(
            self.text_item, text=value, fill=self.text_color, font=(family, self.text_size_var.get())
        )
        self.current_font = tkfont.Font(root=self.parent, font=self.canvas.itemcget(self.text_item, "font"))
        self.text_font_family = self.current_font.actual("family")

    def _choose_color(self) -> None:
        color = colorchooser.askcolor(initialcolor=self.text_color, parent=self.window)
        if color and color[1]:
            self.text_color = color[1]
            self._update_text_item()

    def _create_qr_item(self) -> None:
        if not self.canvas:
            return
        if not self.config.overlay_url:
            self.qr_enabled.set(False)
        if self.qr_item:
            self.canvas.delete(self.qr_item)
            self.qr_item = None
        if not self.qr_enabled.get():
            return
        self._update_qr_image()
        self.qr_item = self.canvas.create_image(
            self.base_image.width - self.qr_size_var.get(),
            self.base_image.height - self.qr_size_var.get(),
            image=self.qr_photo,
            anchor="center",
            tags=("overlay", "qr_overlay"),
        )

    def _update_qr_image(self) -> None:
        if not self.config.overlay_url:
            self.qr_photo = None
            self.qr_image = None
            return
        qr = qrcode.QRCode(border=1)
        qr.add_data(self.config.overlay_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        target_size = self.qr_size_var.get()
        img = img.resize((target_size, target_size), Image.Resampling.NEAREST)
        self.qr_image = img
        self.qr_photo = ImageTk.PhotoImage(img)

    def _update_qr_item(self) -> None:
        if not self.canvas:
            return
        if not self.qr_enabled.get():
            return
        if not self.config.overlay_url:
            return
        self._update_qr_image()
        if self.qr_item is None:
            self._create_qr_item()
        else:
            self.canvas.itemconfigure(self.qr_item, image=self.qr_photo)

    def _toggle_qr(self) -> None:
        if not self.canvas:
            return
        if not self.qr_enabled.get():
            if self.qr_item:
                self.canvas.delete(self.qr_item)
                self.qr_item = None
        else:
            self._create_qr_item()

    # ------------------------------------------------------------------
    def _start_drag(self, event: tk.Event) -> None:
        if not self.canvas:
            return
        item = self.canvas.find_withtag("current")
        if not item:
            return
        item_id = item[0]
        if item_id not in (self.text_item, self.qr_item):
            return
        coords = self.canvas.coords(item_id)
        self.active_item = item_id
        self.drag_offset = (coords[0] - event.x, coords[1] - event.y)

    def _drag(self, event: tk.Event) -> None:
        if not self.canvas or not self.active_item:
            return
        new_x = event.x + self.drag_offset[0]
        new_y = event.y + self.drag_offset[1]
        self.canvas.coords(self.active_item, new_x, new_y)

    def _end_drag(self, _event: tk.Event) -> None:
        self.active_item = None

    # ------------------------------------------------------------------
    def _save(self) -> None:
        merged = self._merge_overlays()
        if merged:
            self.result_image = merged
        if self.window:
            self.window.destroy()

    def _cancel(self) -> None:
        self.result_image = None
        if self.window:
            self.window.destroy()

    def _merge_overlays(self) -> Optional[Image.Image]:
        image = self.base_image.copy()
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))

        if self.text_item and self.canvas:
            text = self.text_var.get().strip()
            if text:
                coords = self.canvas.coords(self.text_item)
                bbox = self.canvas.bbox(self.text_item)
                overlay = Image.alpha_composite(overlay, self._text_overlay_image(text, coords, bbox))

        if self.qr_item and self.qr_enabled.get() and self.qr_image is not None and self.canvas:
            coords = self.canvas.coords(self.qr_item)
            overlay = Image.alpha_composite(overlay, self._qr_overlay_image(coords))

        return Image.alpha_composite(image, overlay)

    def _text_overlay_image(
        self, text: str, coords: Tuple[float, float], bbox: Optional[Tuple[int, int, int, int]]
    ) -> Image.Image:
        temp = Image.new("RGBA", self.base_image.size, (0, 0, 0, 0))
        if not bbox:
            return temp
        target_width = max(1, bbox[2] - bbox[0])
        target_height = max(1, bbox[3] - bbox[1])
        oversample = 4
        font_size = max(10, self.text_size_var.get() * oversample)
        font_info = self._get_current_font_info()
        font = self._load_matching_font(font_info.get("family", self.text_font_family), font_size)
        dummy = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy)
        raw_bbox = draw.textbbox((0, 0), text, font=font)
        width = max(1, raw_bbox[2] - raw_bbox[0] + 8)
        height = max(1, raw_bbox[3] - raw_bbox[1] + 8)
        text_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)
        color = ImageColor.getrgb(self.text_color)
        text_draw.text((4 - raw_bbox[0], 4 - raw_bbox[1]), text, fill=color, font=font)
        scale = target_height / text_img.height
        scaled_width = max(1, int(text_img.width * scale))
        scaled = text_img.resize((scaled_width, target_height), Image.Resampling.LANCZOS)
        if scaled.width != target_width:
            canvas_img = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
            offset_x = (target_width - scaled.width) // 2
            canvas_img.alpha_composite(scaled, dest=(offset_x, 0))
        else:
            canvas_img = scaled
        pos_x = int(coords[0] - target_width / 2)
        pos_y = int(coords[1] - target_height / 2)
        temp.alpha_composite(canvas_img, dest=(pos_x, pos_y))
        return temp

    def _qr_overlay_image(self, coords: Tuple[float, float]) -> Image.Image:
        temp = Image.new("RGBA", self.base_image.size, (0, 0, 0, 0))
        if self.qr_image is None:
            return temp
        pos_x = int(coords[0] - self.qr_image.width / 2)
        pos_y = int(coords[1] - self.qr_image.height / 2)
        temp.alpha_composite(self.qr_image, dest=(pos_x, pos_y))
        return temp

    def _get_current_font_info(self) -> dict:
        if self.current_font is not None:
            return self.current_font.actual()
        try:
            return tkfont.nametofont("TkDefaultFont").actual()
        except tk.TclError:
            return {"family": self.text_font_family or "Arial"}

    def _default_font_family(self) -> str:
        try:
            return tkfont.nametofont("TkDefaultFont").actual("family")
        except tk.TclError:
            return "Arial"

    def _load_matching_font(self, family: str, size: int) -> ImageFont.ImageFont:
        font_path = _find_font_file(family)
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except OSError:
                pass
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()


@lru_cache(maxsize=64)
def _find_font_file(family: str) -> Optional[str]:
    target = _normalize_font_name(family)
    if not target:
        return None
    for directory in FONT_DIRECTORIES:
        dir_path = Path(directory).expanduser()
        if not dir_path.exists():
            continue
        try:
            for font_path in dir_path.rglob("*"):
                if font_path.suffix.lower() not in FONT_EXTENSIONS:
                    continue
                if target in _normalize_font_name(font_path.stem):
                    return str(font_path)
        except (OSError, PermissionError):
            continue
    return None


def _normalize_font_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())
