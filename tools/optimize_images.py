"""Converte as imagens originais (src/img-original) em WebP otimizado (src/assets/img).

Uso:  .venv/Scripts/python tools/optimize_images.py
Requer Pillow (pip install Pillow). Também gera favicon, apple-touch-icon e imagem Open Graph.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "img-original"
OUT = ROOT / "src" / "assets" / "img"

BRAND = (0, 45, 178)          # azul do logo (#002DB2)
NAVY = (11, 22, 51)

# nome de saída -> (arquivo original, largura máxima)
# (teclado-notebook.jpg e fan-notebook-led.jpg ficaram de fora: mostram teclado mecânico e base
#  de refrigeração, não peças de notebook)
PHOTOS = {
    "bancada-notebook-aberto": ("manutencao-notebook-aberto.jpg", 1200),
    "teclado-desmontado": ("teclado-demontado-notebook.jpg", 900),
    "macbook-aberto": ("macbook-aberto.jpg", 1000),
    "reparo-hd": ("reparo-hd.jpg", 900),
    "ssd-notebook": ("ssd.webp", 800),
    "memoria-ram": ("memoria-ram-notebook.jpg", 700),
    "bateria-notebook": ("bateria-notebook.webp", 700),
    "carregador-notebook": ("carregador-notebook.jpg", 800),
    "troca-de-tela": ("troca-de-tela.jpg", 900),
    "tela-notebook": ("tela-trocando.webp", 800),
    "assistencia-dell": ("assistencia-dell-notebook-orcamento.png", 900),
    "tecnico-solda": ("banner-quem-somos.jpg", 1400),
}


def save_webp(im: Image.Image, name: str, max_w: int, quality: int = 74) -> None:
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    if im.width > max_w:
        h = round(im.height * max_w / im.width)
        im = im.resize((max_w, h), Image.LANCZOS)
    path = OUT / f"{name}.webp"
    im.save(path, "WEBP", quality=quality, method=6)
    print(f"{path.name:32} {im.width}x{im.height}  {path.stat().st_size // 1024} KB")


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for f in (["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]):
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{f}", size)
        except OSError:
            continue
    return ImageFont.load_default()


def logo_white() -> Image.Image:
    logo = Image.open(SRC / "logo.png").convert("RGBA")
    white = Image.new("RGBA", logo.size, (255, 255, 255, 0))
    white.putalpha(logo.getchannel("A"))
    return white


def make_icons() -> None:
    # Ícone: "M" branco sobre quadrado azul arredondado
    for size, name in ((180, "apple-touch-icon.png"), (48, "favicon-48.png")):
        scale = 4
        s = size * scale
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=BRAND + (255,))
        f = font(int(s * 0.62))
        bbox = d.textbbox((0, 0), "M", font=f)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((s - w) / 2 - bbox[0], (s - h) / 2 - bbox[1] - s * 0.02), "M", font=f, fill="white")
        im.resize((size, size), Image.LANCZOS).save(OUT / name)
        print(name)


def make_og() -> None:
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    d.rectangle((0, H - 16, W, H), fill=BRAND)
    logo = logo_white()
    logo = logo.resize((logo.width * 2, logo.height * 2), Image.LANCZOS)
    im.paste(logo, (80, 90), logo)
    d.text((80, 250), "Assistência técnica", font=font(76), fill="white")
    d.text((80, 340), "de notebook em Moema, SP", font=font(76), fill="white")
    d.text((80, 470), "Diagnóstico e orçamento grátis  ·  Desde 2001", font=font(36, bold=False), fill=(190, 205, 240))
    im.save(OUT / "og-magitronic.jpg", "JPEG", quality=85, optimize=True)
    print("og-magitronic.jpg")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, (src, max_w) in PHOTOS.items():
        im = Image.open(SRC / src)
        if im.mode == "RGBA":
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.getchannel("A"))
            im = bg
        save_webp(im, name, max_w)
        manifest[name] = list(Image.open(OUT / f"{name}.webp").size)
    # dimensões usadas pelo build.py para width/height das <img> (evita salto de layout)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # logo original (azul) e versão branca, em PNG pequeno
    logo = Image.open(SRC / "logo.png").convert("RGBA")
    logo.save(OUT / "logo-magitronic.png", optimize=True)
    logo_white().save(OUT / "logo-magitronic-branco.png", optimize=True)
    make_icons()
    make_og()


if __name__ == "__main__":
    main()
