"""Full-resolution logo with browser-side theme colors."""
import base64
import struct
from pathlib import Path


def logo_markup(path: Path, width: int = 240) -> str:
    """Use a CSS alpha mask that follows the inherited app text color."""
    image = path.read_bytes()
    if image[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("The brand logo must be a PNG.")
    source_width, source_height = struct.unpack(">II", image[16:24])
    height = width * source_height / source_width
    encoded = base64.b64encode(image).decode("ascii")
    uri = f"data:image/png;base64,{encoded}"
    return f"""<div role="img" aria-label="EcoRoute"
    style="width:{width}px;height:{height:.2f}px;max-width:100%;
    background-color:currentColor;
    -webkit-mask-image:url('{uri}');mask-image:url('{uri}');
    -webkit-mask-size:contain;mask-size:contain;
    -webkit-mask-position:left center;mask-position:left center;
    -webkit-mask-repeat:no-repeat;mask-repeat:no-repeat"></div>"""

