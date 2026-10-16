"""Regenerates screenplay.pdf: a 2-page Courier screenplay with standard indents.

No PDF library needed.

Run: uv run python tests/fixtures/ingest/make_screenplay_pdf.py
"""

from pathlib import Path

LEFT, DIALOGUE, PAREN, CHARACTER, TRANSITION = 108, 180, 223, 266, 432

PAGES = [
    [
        (LEFT, "1."),
        (LEFT, "INT. HARBOR WAREHOUSE - NIGHT"),
        (LEFT, "Maya enters, flashlight sweeping the crates."),
        (CHARACTER, "MAYA"),
        (PAREN, "(whispering)"),
        (DIALOGUE, "Where is he?"),
        (DIALOGUE, "He said nine o'clock."),
        (CHARACTER, "LEO (O.S.)"),
        (DIALOGUE, "Behind you."),
        (TRANSITION, "CUT TO:"),
        (LEFT, "EXT. DOCK - DAY"),
        (LEFT, "Gulls wheel over the water."),
    ],
    [
        (LEFT, "2."),
        (CHARACTER, "MAYA"),
        (DIALOGUE, "That's the boat."),
        (CHARACTER, "MAYA (CONT'D)"),
        (DIALOGUE, "Come on."),
        (LEFT, "INT. SAFEHOUSE - CONTINUOUS"),
        (LEFT, "Ada waits by the window."),
        (TRANSITION, "FADE OUT."),
    ],
]


def build(pages: list[list[tuple[int, str]]]) -> bytes:
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font_id = 3 + 2 * len(pages)
    for i, lines in enumerate(pages):
        ops = ["BT /F1 12 Tf 14 TL"]
        y = 720
        for x, text in lines:
            esc = text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
            ops.append(f"1 0 0 1 {x} {y} Tm ({esc}) Tj")
            y -= 14
        ops.append("ET")
        stream = "\n".join(ops).encode()
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


if __name__ == "__main__":
    Path(__file__).with_name("screenplay.pdf").write_bytes(build(PAGES))
