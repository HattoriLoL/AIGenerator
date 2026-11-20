"""The face fix: finds the faces (an OpenCV cascade trained on anime faces), crops each one with a margin, redraws the
crop at 1024 px with the SDXL inpaint and pastes it back with a soft edge. Off by default ("face_fix" in the request,
--face-fix on the command line).

The box math is pure (tested without a GPU); the stage uses OpenCV, PIL and diffusers.
"""
from aigen import generation, hires, model, prompts, stages

INPAINT_SIDE = 1024     # the crop is redrawn at this size (the one SDXL was trained at)
FACE_MIN = 0.04         # a face smaller than 4 % of the image's shorter side is ignored (almost always a false find)
FEATHER = 0.08          # the soft edge of the mask, as a fraction of the crop side


def largest(boxes, n):
    """The n largest boxes (x, y, width, height), largest first; on a tie, the one at the top and to the left."""
    return sorted(boxes, key=lambda b: (-b[2] * b[3], b[1], b[0]))[:n]


def expanded_box(box, margin, width, height):
    """A square around the box, with `margin` (a fraction of the face side) on each side, inside the image."""
    x, y, w, h = box
    side = min(max(w, h) * (1 + 2 * margin), width, height)
    cx, cy = x + w / 2.0, y + h / 2.0
    x0 = min(max(cx - side / 2.0, 0.0), width - side)
    y0 = min(max(cy - side / 2.0, 0.0), height - side)
    side = int(round(side))
    return (int(round(x0)), int(round(y0)), side, side)


def box_in_crop(box, crop, new_side):
    """The face box in the crop's coordinates after it is resized to new_side × new_side."""
    x, y, w, h = box
    cx, cy, cs, _ = crop
    f = new_side / float(cs)
    return (int(round((x - cx) * f)), int(round((y - cy) * f)), int(round(w * f)), int(round(h * f)))


def find(session, image, max_faces):
    import cv2
    import numpy
    gray = cv2.equalizeHist(cv2.cvtColor(numpy.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY))
    minimum = max(24, int(min(image.size) * FACE_MIN))
    found = session.detector().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(minimum, minimum))
    return largest([tuple(int(v) for v in b) for b in found], max_faces)


def mask(crop_box, side):
    """The inpaint mask: the face rectangle in white, with a blurred edge."""
    from PIL import Image, ImageDraw, ImageFilter
    m = Image.new("L", (side, side), 0)
    x, y, w, h = crop_box
    ImageDraw.Draw(m).rectangle((x, y, x + w, y + h), fill=255)
    return m.filter(ImageFilter.GaussianBlur(max(1, int(side * FEATHER))))


@stages.declare(reads=("image", "pipe", "session", "request", "positive", "negative", "active_loras", "report"),
                writes=("image", "faces"))
def stage(t):
    """Redraws each face found (up to max_faces), from the largest to the smallest."""
    import torch
    from PIL import Image
    r, f = t.request, t.request["face_fix"]
    image = t.image.convert("RGB")
    boxes = find(t.session, image, f["max_faces"])
    pipe = t.session.derived("StableDiffusionXLInpaintPipeline") if boxes else None
    if pipe:
        model.prepare_vae(pipe, INPAINT_SIDE, INPAINT_SIDE)
    text = prompts.join_tags(t.positive, f["prompt"])
    for i, box in enumerate(boxes):
        crop = expanded_box(box, f["margin"], *image.size)
        x, y, side, _ = crop
        piece = image.crop((x, y, x + side, y + side)).resize((INPAINT_SIDE, INPAINT_SIDE), Image.LANCZOS)
        m = mask(box_in_crop(box, crop, INPAINT_SIDE), INPAINT_SIDE)
        with torch.inference_mode():
            new = pipe(**generation.encode(t.session, text, t.negative), image=piece, mask_image=m,
                       width=INPAINT_SIDE, height=INPAINT_SIDE, strength=f["strength"],
                       num_inference_steps=hires.total_steps(f["steps"], f["strength"]), guidance_scale=r["cfg"],
                       generator=model.generator(r["seed"] + i + 1)).images[0]
        back = new.resize((side, side), Image.LANCZOS)
        image.paste(back, (x, y), m.resize((side, side), Image.LANCZOS))
    t.image, t.faces = image, [list(b) for b in boxes]
    t.report["face_fix"] = {"found": len(boxes), "boxes": t.faces, "strength": f["strength"]}
