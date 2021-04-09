from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
from contextlib import contextmanager


class Color:
    # fmt: off
    RED    = (255, 0, 0)
    GREEN  = (0, 255, 0)
    BLUE   = (0, 0, 255)
    ORANGE = (255, 128, 0)
    YELLOW = (255, 255, 0)
    GREEN  = (0, 255, 0)
    BLUE   = (0, 0, 255)
    PURPLE = (128, 0, 255)
    PINK   = (255, 0, 255)
    WHITE  = (255, 255, 255)
    GRAY   = (128, 128, 128)
    BLACK  = (0, 0, 0)
    TRNASPARENT = (0, 0, 0, 0)
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

    @classmethod
    def new(cls, size, color=Color.WHITE):
        return cls(Image.new('RGBA', size, color))

    @classmethod
    def open(cls, path):
        return cls(Image.open(path))

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
            self.img.thumbnail(size, Image.ANTIALIAS)
        else:
            self.img = self.img.resize(size, Image.ANTIALIAS)

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
        color=(255, 255, 255),
        font=None,
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
            color=color,
            stroke_width=stroke,
            stroke_fill=stroke_color,
        )

    def paste(self, im, pos):
        if isinstance(im, MakeImage):
            im = im.img
        self.img.paste(im, pos, im)

    def create_circle_mask(self):
        w, h = self.size
        bigsize = w * 3, h * 3
        mask = Image.new('L', bigsize, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + bigsize, fill=255)
        return mask.resize(self.size, Image.ANTIALIAS)

    def add_mask(self, mask):
        self.img.putalpha(mask)
        ImageOps.fit(self.img, mask.size, centering=(0.5, 0.5)).putalpha(mask)

    @contextmanager
    def antialiasing(self, quantity=2):
        w, h = self.size
        self.resize((w * quantity, h * quantity))
        yield
        self.resize((w, h))

    def add_border(
        self, size, color=Color.WHITE, type_='circle', antialiasing=2
    ):
        W, H = self.size
        with self.antialiasing(antialiasing):
            if type_ == 'circle':
                ImageDraw.Draw(self.img).arc(
                    (0, 0, *self.size), 0, 360, fill=color, width=size
                )
            elif type_ == 'square':
                ImageDraw.Draw(self.img).line(
                    (0, -1 + size // 2, W, -1 + size // 2),
                    fill=color,
                    width=size,
                )
                ImageDraw.Draw(self.img).line(
                    (W - size // 2, H, W - size // 2, 0), fill=color, width=size
                )
                ImageDraw.Draw(self.img).line(
                    (0, H - 1 - size // 2, W, H - 1 - size // 2),
                    fill=color,
                    width=size,
                )
                ImageDraw.Draw(self.img).line(
                    (0 + size // 2, H, 0 + size // 2, 0), fill=color, width=size
                )
            else:
                raise Exception(f'Invalid type: "{type_}"')

    def show(self):
        self.img.show()
