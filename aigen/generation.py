"""The first pass: text to image, with the prompt encoded by compel (weights and prompts longer than 77 tokens).

diffusers' SDXL uses the penultimate layer of the text encoders, which is the "CLIP skip 2" recommended for Pony:
there is nothing to adjust.
"""
from aigen import model, prompts, stages


def encode(session, positive, negative):
    """The pipeline's prompt arguments (prompt_embeds, pooled and the two of the negative), of the same length."""
    r = session.compel()(prompts.to_compel(positive), negative_prompt=prompts.to_compel(negative))
    return {"prompt_embeds": r.embeds, "pooled_prompt_embeds": r.pooled_embeds,
            "negative_prompt_embeds": r.negative_embeds, "negative_pooled_prompt_embeds": r.negative_pooled_embeds}


@stages.declare(reads=("pipe", "session", "request", "positive", "negative", "active_loras", "report"),
                writes=("image",))
def stage(t):
    """Generates the image at the request's width and height."""
    import torch
    r = t.request
    model.prepare_vae(t.pipe, r["width"], r["height"])
    with torch.inference_mode():
        result = t.pipe(**encode(t.session, t.positive, t.negative), width=r["width"], height=r["height"],
                        num_inference_steps=r["steps"], guidance_scale=r["cfg"], generator=model.generator(r["seed"]))
    t.image = result.images[0]
    t.report["generation"] = {"width": r["width"], "height": r["height"], "seed": r["seed"]}
