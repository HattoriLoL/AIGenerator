"""A primeira passada: texto para imagem, com o prompt codificado pelo compel (pesos e prompts de mais de 77 tokens).

O SDXL do diffusers usa a penúltima camada dos codificadores de texto, que é o "CLIP skip 2" recomendado para o Pony:
não há o que ajustar.
"""
from aigen import etapas, modelo, prompts


def codificar(sessao, positivo, negativo):
    """Os argumentos de prompt do pipeline (prompt_embeds, pooled e os dois do negativo), do mesmo comprimento."""
    r = sessao.compel()(prompts.para_compel(positivo), negative_prompt=prompts.para_compel(negativo))
    return {"prompt_embeds": r.embeds, "pooled_prompt_embeds": r.pooled_embeds,
            "negative_prompt_embeds": r.negative_embeds, "negative_pooled_prompt_embeds": r.negative_pooled_embeds}


@etapas.declarar(le=("pipe", "sessao", "pedido", "positivo", "negativo", "loras_ativas", "rel"), grava=("imagem",))
def etapa(t):
    """Gera a imagem na largura e na altura do pedido."""
    import torch
    p = t.pedido
    modelo.preparar_vae(t.pipe, p["largura"], p["altura"])
    with torch.inference_mode():
        saida = t.pipe(**codificar(t.sessao, t.positivo, t.negativo), width=p["largura"], height=p["altura"],
                       num_inference_steps=p["passos"], guidance_scale=p["cfg"], generator=modelo.gerador(p["seed"]))
    t.imagem = saida.images[0]
    t.rel["geracao"] = {"largura": p["largura"], "altura": p["altura"], "seed": p["seed"]}
