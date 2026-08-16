from pathlib import Path

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
ASSETS = ROOT / "assets"
MARKER = "PROJECTION_ARTWORK_INDIVIDUAL_V5"

NAMES = [
    "projection_k.webp",
    "projection_k_plus.webp",
    "projection_outs.webp",
    "projection_outs_plus.webp",
    "projection_hits.webp",
    "projection_hits_plus.webp",
]


def _load_valid_sprite() -> Image.Image:
    candidates = [
        ASSETS / "projection_summary_emblems_v2.webp",
        ASSETS / "projection_summary_emblems.webp",
    ]
    errors = []
    for sprite_path in candidates:
        if not sprite_path.exists():
            continue
        try:
            image = Image.open(sprite_path)
            image.load()
            image = image.convert("RGBA")
            width, height = image.size
            if width < height * 3:
                errors.append(f"{sprite_path.name}: unexpected {width}x{height}")
                continue
            print(f"Using valid Projection artwork source: {sprite_path.name} ({width}x{height})")
            return image
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            errors.append(f"{sprite_path.name}: {exc}")
            print(f"Skipping invalid Projection artwork source {sprite_path.name}: {exc}")
    raise RuntimeError("No valid Projection artwork sprite found. " + " | ".join(errors))


def _split_sprite() -> None:
    image = _load_valid_sprite()
    width, height = image.size
    cell_width = width // 6
    if cell_width <= 0:
        raise RuntimeError("Invalid Projection artwork cell width")

    for idx, name in enumerate(NAMES):
        left = idx * cell_width
        right = width if idx == 5 else (idx + 1) * cell_width
        cell = image.crop((left, 0, right, height))
        alpha_box = cell.getchannel("A").getbbox()
        if alpha_box is not None:
            cell = cell.crop(alpha_box)
        side = max(cell.size)
        pad = max(4, int(side * 0.035))
        canvas = Image.new("RGBA", (side + 2 * pad, side + 2 * pad), (0, 0, 0, 0))
        canvas.alpha_composite(cell, ((side - cell.width) // 2 + pad, (side - cell.height) // 2 + pad))
        canvas.thumbnail((256, 256), Image.Resampling.LANCZOS)
        canvas.save(ASSETS / name, "WEBP", quality=92, method=6)
        print(f"Wrote {name}: {canvas.size[0]}x{canvas.size[1]}")


def _patch_app() -> None:
    text = APP.read_text(encoding="utf-8")
    if MARKER in text:
        print("Individual Projection artwork CSS already installed")
        return

    anchor = "</style>\"\"\", unsafe_allow_html=True)"
    if anchor not in text:
        raise RuntimeError("Could not find main Projection style close")

    base = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets"
    css = f'''\n/* {MARKER} · one real image per Summary emblem, no runtime sprite */\n.cc-card-icon.cc-emblem{{\n    width:64px!important;height:64px!important;flex:0 0 64px!important;\n    display:block!important;visibility:visible!important;opacity:1!important;\n    border:0!important;border-radius:0!important;background-color:transparent!important;\n    background-repeat:no-repeat!important;background-position:center!important;background-size:contain!important;\n    box-shadow:none!important;overflow:visible!important;\n    filter:drop-shadow(0 4px 8px rgba(0,0,0,.32)) drop-shadow(0 0 6px rgba(236,22,56,.22))!important;\n}}\n.cc-card-icon.cc-emblem::before,.cc-card-icon.cc-emblem::after{{display:none!important;content:none!important}}\n.metric-card .cc-emblem.whiff{{background-image:url("{base}/projection_k.webp?v=5")!important}}\n.reco-card .cc-emblem.whiff{{background-image:url("{base}/projection_k_plus.webp?v=5")!important}}\n.metric-card .cc-emblem.glove{{background-image:url("{base}/projection_outs.webp?v=5")!important}}\n.reco-card .cc-emblem.glove{{background-image:url("{base}/projection_outs_plus.webp?v=5")!important}}\n.metric-card .cc-emblem.contact{{background-image:url("{base}/projection_hits.webp?v=5")!important}}\n.reco-card .cc-emblem.contact{{background-image:url("{base}/projection_hits_plus.webp?v=5")!important}}\n@media (max-width:900px){{.cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{{width:56px!important;height:56px!important;flex-basis:56px!important}}}}\n'''
    text = text.replace(anchor, css + anchor, 1)
    APP.write_text(text, encoding="utf-8")


def main() -> None:
    _split_sprite()
    _patch_app()
    print("Installed six individual Projection Summary artwork files")


if __name__ == "__main__":
    main()
