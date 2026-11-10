"""packaging/kafekamera.ico ve açılış görseli (splash.png) çizer; depoda ikili görsel tutulmaz."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BURASI = Path(__file__).parent
SARI, KOYU, KART = (253, 224, 53), (11, 16, 32), (20, 27, 48)


def kamera(d: ImageDraw.ImageDraw, x: float, y: float, s: float) -> None:
    """(x, y) sol üst, s ölçek (256 px karede 1.0)."""
    # gövde
    d.rounded_rectangle((x + 40 * s, y + 92 * s, x + 176 * s, y + 164 * s), radius=18 * s, fill=(232, 236, 245))
    # mercek
    d.ellipse((x + 136 * s, y + 104 * s, x + 184 * s, y + 152 * s), fill=KOYU)
    d.ellipse((x + 148 * s, y + 116 * s, x + 172 * s, y + 140 * s), fill=SARI)
    # duvar ayağı
    d.rectangle((x + 92 * s, y + 164 * s, x + 108 * s, y + 196 * s), fill=(232, 236, 245))
    d.rounded_rectangle((x + 64 * s, y + 192 * s, x + 136 * s, y + 206 * s), radius=6 * s, fill=(232, 236, 245))
    # kayıt ışığı
    d.ellipse((x + 56 * s, y + 106 * s, x + 72 * s, y + 122 * s), fill=(240, 70, 60))


def ikon() -> Path:
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, S - 8, S - 8), radius=56, fill=KART, outline=SARI, width=10)
    kamera(d, 8, -12, 0.95)
    # fincan buharı gibi üç çizgi: kafe
    for i, x in enumerate((84, 112, 140)):
        d.arc((x - 10, 40 + 4 * (i % 2), x + 10, 76 + 4 * (i % 2)), 250, 110, fill=SARI, width=7)
    out = BURASI / "kafekamera.ico"
    img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return out


def font(boyut: int, kalin: bool = True):
    for ad in (["seguisb.ttf", "segoeuib.ttf"] if kalin else ["segoeui.ttf"]) + ["arial.ttf"]:
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{ad}", boyut)
        except OSError:
            continue
    return ImageFont.load_default()


def splash() -> Path:
    W, H = 520, 240
    img = Image.new("RGB", (W, H), KOYU)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=0, outline=SARI, width=4)
    kamera(d, 18, 10, 0.8)
    d.text((220, 62), "Kafe Kamera", font=font(40), fill=(232, 236, 245))
    d.text((222, 116), "Hazırlanıyor…", font=font(22, False), fill=SARI)
    d.text((222, 148), "Açılış birkaç saniye sürebilir.", font=font(17, False), fill=(147, 160, 189))
    out = BURASI / "splash.png"
    img.save(out)
    return out


if __name__ == "__main__":
    print(ikon())
    print(splash())
