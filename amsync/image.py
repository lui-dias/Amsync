from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from typing import Tuple
from pathlib import Path
from filetype import guess_mime


__all__ = [
    'Color',
    'MakeImage',
    'ProgressBar'
]

Size = Tuple[int, int]
RGBA = Tuple[int, int, int, int]

class Color:
    RED    = (255, 0, 0, 255)
    GREEN  = (0, 255, 0, 255)
    BLUE   = (0, 0, 255, 255)
    CYAN   = (0, 255, 255, 255)
    ORANGE = (255, 128, 0, 255)
    YELLOW = (255, 255, 0, 255)
    GREEN  = (0, 255, 0, 255)
    BLUE   = (0, 0, 255, 255)
    PURPLE = (128, 0, 255, 255)
    PINK   = (255, 0, 255, 255)
    WHITE  = (255, 255, 255, 255)
    GRAY   = (128, 128, 128, 255)
    BLACK  = (0, 0, 0, 255)
    TRANSPARENT = (0, 0, 0, 0)

    PRETTY_BLACK = (26, 26, 26, 255)


class MakeImage:
    def __init__(self, img) -> None:
        if isinstance(img, bytes):
            img = Image.open(BytesIO(img))

        self.img: Image.Image = img

    @property
    def size(self) -> tuple(int, int):
        return self.img.size

    @property
    def bytes(self) -> bytes:
        arr = BytesIO()
        self.save(arr)
        return arr.getvalue()

    @staticmethod
    def type(b) -> str:
        # Only first 261 bytes representing the max file header is required
        #
        # https://github.com/h2non/filetype.py#features
        return guess_mime(b[:261]).split('/')[1]

    @classmethod
    def new(
        cls,
        size: Size,
        color: RGBA | Color = Color.WHITE
    ) -> MakeImage:
        return cls(Image.new('RGBA', size, color))

    @classmethod
    def from_path(cls, path) -> MakeImage:
        return cls(Image.open(path))

    @classmethod
    def convert(cls, im: Image.Image) -> MakeImage:
        return cls(im)

    def get_text_pos(
        self,
        draw: ImageDraw.Draw,
        text: str,
        font: ImageFont.truetype
    ) -> Size:

        w, h = draw.textsize(text, font=font)
        W, H = self.size
        return W-w, H-h

    def get_image_pos(self, im: Image.Image) -> Size:
        W, H = self.size
        w, h = im.size
        return W-w, H-h

    def resize(
        self,
        size:            Size,
        preserve_aspect: bool = False
    ) -> None:

        if preserve_aspect:
            self.img.thumbnail(size, Image.BICUBIC)
        else:
            self.img = self.img.resize(size, Image.BICUBIC)

    def crop(self, size: Size) -> None:
        W, H   = self.size
        cw, ch = W//2, H//2
        w, h   = size

        left   = cw - w//2
        top    = ch - h//2
        right  = cw + w//2
        bottom = ch + h//2

        self.img = self.img.crop((left, top, right, bottom))

    def save(
        self,
        path:    str,
        format:  str        = 'webp',
        quality: int | None = None
    ) -> None:

        format = format.lower()
        if format in ('jpg', 'jpeg', 'png'):
            self.img.save(path, format, quality=quality or 80)
        elif format == 'webp':
            self.img.save(path, format, quality=quality or 90)
        else:
            self.img.save(path, format, quality=quality)

    @staticmethod
    def calc(
        size:     Size, 
        position: str | None = None, 
        move:     Size       = (0, 0)
    ) -> Size:

        w, h = size
        if position == 'center':
            return tuple(map(sum, zip((w//2, h//2), move)))
        if position == 'top':
            return tuple(map(sum, zip((w//2, 0), move)))
        if position == 'right':
            return tuple(map(sum, zip((w, h//2), move)))
        if position == 'bottom':
            return tuple(map(sum, zip((w//2, h), move)))
        if position == 'left':
            return tuple(map(sum, zip((0, h//2), move)))
        return move

    def text(
        self,
        text:         str,
        position:     str | None   = None,
        move:         Size         = (0, 0),
        font:         str | None   = None,
        color:        RGBA | Color = Color.WHITE,
        stroke:       int          = 0,
        stroke_color: RGBA | Color = Color.BLACK,
    ) -> None:

        draw = ImageDraw.Draw(self.img)
        if font:
            if not font[0] or not font[1]:
                raise Exception('No font-file or font-size')
            font = ImageFont.truetype(*font)

        w, h = self.get_text_pos(draw, text, font)
        draw.text(
            self.calc((w, h), move=move, position=position),
            text,
            font         = font,
            fill         = color,
            stroke_width = stroke,
            stroke_fill  = stroke_color,
        )

    def paste(
        self,
        im:       MakeImage | Image.Image,
        position: str | None               = None,
        move:     Size                     = (0, 0)
    ) -> None:

        if isinstance(im, MakeImage):
            im = im.img
            
        self.img.paste(
            im, self.calc(self.get_image_pos(im), position, move), im
        )

    def circular_thumbnail(self) -> None:
        w, h = self.size
        w, h = w*3, h*3
        mask = Image.new('L', (w, h), 0)

        # Place the entire mask in the center of the image,
        # without the 5, part of the mask's edges is slightly cut
        ImageDraw.Draw(mask).ellipse((5, 5, w-5, h-5), fill=255)
        mask = mask.resize(self.size, Image.BICUBIC)
        self.img = ImageOps.fit(self.img, mask.size, Image.BICUBIC)
        self.img.putalpha(mask)

    def to_img(self, n_frame: int = 0) -> MakeImage:
        self.img.seek(n_frame)
        self.save('tmp.webp')
        with open('tmp.webp', 'rb') as tmp:
            tmp = MakeImage.from_bytes(tmp.read())
        Path('tmp.webp').unlink(missing_ok=True)
        return tmp

    def add_border(
        self,
        size:  Size, 
        color: RGBA | Color = Color.WHITE
    ) -> None:

        W, H = self.size

        mask = self.img.copy().resize((W + size*2, H + size*2))
        fill = Image.new('RGBA', (W + size*2, H + size*2), color)
        bg = Image.new('RGBA', (W + size*2, H + size*2), Color.TRANSPARENT)

        w, h = bg.size

        bg.paste(fill, mask=mask)
        bg.paste(self.img, ((w-W)//2, (h-H)//2), self.img)

        self.img = bg

    def show(self) -> None:
        self.img.show()


class ProgressBar(MakeImage):
    def __init__(
        self,
        size:     Size, 
        radius:   int          = 30, 
        color:    RGBA | Color = Color.WHITE, 
        bg_color: RGBA | Color = Color.PRETTY_BLACK
    ):
    
        self.img = Image.new('RGBA', size, Color.TRANSPARENT)
        self.radius = radius
        self.color = color
        self.bg = bg_color

        ImageDraw.Draw(self.img).rounded_rectangle(
            (0, 0, *size), radius, bg_color
        )

    def fill(self, px: int) -> None:
        w, h = self.img.size

        bg_fill = self.img.copy()
        bg = self.img.copy()

        pixdata = bg_fill.load()

        for y in range(bg_fill.size[1]):
            for x in range(bg_fill.size[0]):
                if pixdata[x, y] == self.bg:
                    pixdata[x, y] = self.color

        bg_fill = bg_fill.crop((0, 0, px*2, h))
        bg.paste(bg_fill, mask=bg_fill)
        self.img = bg.resize((w, h), Image.BICUBIC)
