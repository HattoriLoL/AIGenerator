"""The hires fix: enlarges the image (with the upscaler model or with Lanczos) and runs a second image-to-image pass,
which redraws the details at the new resolution. Off by default ("hires" in the request, --hires on the command line).
"""
import math

from aigen import contract, generation, model, stages


def total_steps(steps, strength):
    """diffusers runs int(steps × strength) of the steps it receives; to run `steps`, it asks for steps / strength."""
    return max(steps, int(math.ceil(steps / strength)))


def upscale(session, image, width, height, upscaler):
    """The image at the new size: the upscaler model (which enlarges 2 or 4 times) and then Lanczos to the exact size,
    or Lanczos only."""
    from PIL import Image
    if upscaler == "model":
        import numpy
        import torch
        net = session.upscaler()
        x = torch.from_numpy(numpy.asarray(image.convert("RGB"), dtype=numpy.float32) / 255.0)
        x = x.permute(2, 0, 1).unsqueeze(0).to(model.device())
        with torch.inference_mode():
            y = net(x).clamp(0, 1)
        arr = (y[0].permute(1, 2, 0).float().cpu().numpy() * 255.0).round().astype(numpy.uint8)
        image = Image.fromarray(arr)
    return image.resize((width, height), Image.LANCZOS)


@stages.declare(reads=("image", "pipe", "session", "request", "positive", "negative", "active_loras", "report"),
                writes=("image",))
def stage(t):
    """Enlarges the image by the request's scale and redraws the details with the requested strength."""
    import torch
    r, h = t.request, t.request["hires"]
    width, height = contract.hires_side(r["width"], h["scale"]), contract.hires_side(r["height"], h["scale"])
    larger = upscale(t.session, t.image, width, height, h["upscaler"])
    pipe = t.session.derived("StableDiffusionXLImg2ImgPipeline")
    model.prepare_vae(pipe, width, height)
    with torch.inference_mode():
        result = pipe(**generation.encode(t.session, t.positive, t.negative), image=larger, strength=h["strength"],
                      num_inference_steps=total_steps(h["steps"], h["strength"]), guidance_scale=r["cfg"],
                      generator=model.generator(r["seed"]))
    t.image = result.images[0]
    t.report["hires"] = {"width": width, "height": height, "upscaler": h["upscaler"], "strength": h["strength"]}
