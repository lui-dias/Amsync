from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
from pathlib import Path
from imghdr import what


class Color:
    # fmt: off
    RED    = (255, 0, 0)
    GREEN  = (0, 255, 0)
    BLUE   = (0, 0, 255)
    CYAN   = (0, 255, 255)
    ORANGE = (255, 128, 0)
    YELLOW = (255, 255, 0)
    GREEN  = (0, 255, 0)
    BLUE   = (0, 0, 255)
    PURPLE = (128, 0, 255)
    PINK   = (255, 0, 255)
    WHITE  = (255, 255, 255)
    GRAY   = (128, 128, 128)
    BLACK  = (0, 0, 0)
    TRANSPARENT = (0, 0, 0, 0)

    PRETTY_BLACK = (26, 26, 26)
    # fmt: on


class MakeImage:
    def __init__(self, img):
        self.img: Image.Image = img

    @property
    def size(self):
        return self.img.size

    @property
    def bytes(self):
        arr = BytesIO()
        self.save(arr)
        return arr.getvalue()

    @staticmethod
    def type(b):
        return what('', b)

    @classmethod
    def new(cls, size, color=Color.WHITE):
        return cls(Image.new('RGBA', size, color))

    @classmethod
    def open(cls, path):
        return cls(Image.open(path))

    @classmethod
    def from_bytes(cls, b):
        return cls(Image.open(BytesIO(b)))

    @classmethod
    def convert(cls, im):
        return cls(im)

    def get_text_pos(self, draw, text, font):
        w, h = draw.textsize(text, font=font)
        W, H = self.size
        return W - w, H - h

    def get_image_pos(self, im):
        W, H = self.size
        w, h = im.size
        return W - w, H - h

    def resize(self, size, preserve_aspect=False):
        if preserve_aspect:
            self.img.thumbnail(size, Image.BICUBIC)
        else:
            self.img = self.img.resize(size, Image.BICUBIC)

    def crop(self, size):
        W, H = self.size
        cw, ch = W // 2, H // 2
        w, h = size

        left = cw - w // 2
        top = ch - h // 2
        right = cw + w // 2
        bottom = ch + h // 2

        self.img = self.img.crop((left, top, right, bottom))

    def save(self, path, format='webp', quality=None):
        format = format.lower()
        if format in ('jpg', 'jpeg', 'png'):
            self.img.save(path, format, quality=quality or 80)
        elif format == 'webp':
            self.img.save(path, format, quality=quality or 90)
        else:
            self.img.save(path, format, quality=quality)

    @staticmethod
    def calc(size, position=None, move=(0, 0)):
        w, h = size
        if position == 'center':
            return tuple(map(sum, zip((w // 2, h // 2), move)))
        if position == 'top':
            return tuple(map(sum, zip((w // 2, 0), move)))
        if position == 'right':
            return tuple(map(sum, zip((w, h // 2), move)))
        if position == 'bottom':
            return tuple(map(sum, zip((w // 2, h), move)))
        if position == 'left':
            return tuple(map(sum, zip((0, h // 2), move)))
        return move

    def text(
        self,
        text,
        position=None,
        move=(0, 0),
        font=None,
        color=Color.WHITE,
        stroke=0,
        stroke_color=Color.BLACK,
    ):
        draw = ImageDraw.Draw(self.img)
        if font:
            if not font[0] or not font[1]:
                raise Exception('No font-file or font-size')
            font = ImageFont.truetype(*font)

        w, h = self.get_text_pos(draw, text, font)
        draw.text(
            self.calc((w, h), move=move, position=position),
            text,
            font=font,
            fill=color,
            stroke_width=stroke,
            stroke_fill=stroke_color,
        )

    def paste(self, im, position=None, move=(0, 0)):
        if isinstance(im, MakeImage):
            im = im.img
        self.img.paste(
            im, self.calc(self.get_image_pos(im), position, move), im
        )

    def circular_thumbnail(self):
        w, h = self.size
        w, h = w * 3, h * 3
        mask = Image.new('L', (w, h), 0)

        # Place the entire mask in the center of the image, without the 5, part of the mask's edges is slightly cut
        ImageDraw.Draw(mask).ellipse((5, 5, w - 5, h - 5), fill=255)
        mask = mask.resize(self.size, Image.BICUBIC)
        self.img = ImageOps.fit(self.img, mask.size, Image.BICUBIC)
        self.img.putalpha(mask)

    def to_img(self, n_frame=0):
        self.img.seek(n_frame)
        self.save('tmp.webp')
        with open('tmp.webp', 'rb') as tmp:
            tmp = self.__class__.from_bytes(tmp.read())
        Path('tmp.webp').unlink(missing_ok=True)
        return tmp

    def add_border(self, size, color=Color.WHITE):
        # The border size must be an even number
        size += size % 2
        W, H = self.size

        mask = self.img.copy().resize((W + size, H + size))
        fill = Image.new('RGBA', (W + size, H + size), color)
        bg = Image.new('RGBA', (W + size, H + size), Color.TRANSPARENT)

        w, h = bg.size

        bg.paste(fill, mask=mask)
        bg.paste(self.img, ((w - W) // 2, (h - H) // 2), self.img)

        self.img = bg

    def show(self):
        self.img.show()


class ProgressBar(MakeImage):
    def __init__(
        self, size, radius=30, color=Color.WHITE, bg_color=Color.PRETTY_BLACK
    ):
        w, h = size
        self.img = Image.new('RGBA', (w, h), Color.TRANSPARENT)
        self.radius = radius
        self.color = color
        self.bg = bg_color

        ImageDraw.Draw(self.img).rounded_rectangle((0, 0, w, h), radius, color)

    def update(self, px):
        w, h = self.img.size

        bg_fill = self.img.copy()
        bg = self.img.copy()

        pixdata = bg_fill.load()

        for y in range(bg_fill.size[1]):
            for x in range(bg_fill.size[0]):
                if pixdata[x, y] == (*self.color, 255):
                    pixdata[x, y] = (*self.bg, 255)

        bg_fill = bg_fill.crop((0, 0, px * 2, h))
        bg.paste(bg_fill, mask=bg_fill)
        self.img = bg.resize((w, h), Image.BICUBIC)
