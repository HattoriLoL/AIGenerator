"""O hires fix: aumenta a imagem (com o modelo de upscale ou com Lanczos) e faz uma segunda passada de imagem para
imagem, que refaz os detalhes na resolução nova. Desligado por padrão ("hires" no pedido, --hires na linha de comando).
"""
import math

from aigen import contrato, etapas, geracao, modelo


def passos_totais(passos, forca):
    """O diffusers roda int(passos × força) dos passos que recebe; para rodar `passos`, pede passos / força."""
    return max(passos, int(math.ceil(passos / forca)))


def aumentar(sessao, imagem, largura, altura, upscaler):
    """A imagem no tamanho novo: o modelo de upscale (que aumenta 2 ou 4 vezes) e depois Lanczos até o tamanho exato,
    ou só Lanczos."""
    from PIL import Image
    if upscaler == "modelo":
        import numpy
        import torch
        rede = sessao.upscaler()
        x = torch.from_numpy(numpy.asarray(imagem.convert("RGB"), dtype=numpy.float32) / 255.0)
        x = x.permute(2, 0, 1).unsqueeze(0).to(modelo.dispositivo())
        with torch.inference_mode():
            y = rede(x).clamp(0, 1)
        arr = (y[0].permute(1, 2, 0).float().cpu().numpy() * 255.0).round().astype(numpy.uint8)
        imagem = Image.fromarray(arr)
    return imagem.resize((largura, altura), Image.LANCZOS)


@etapas.declarar(le=("imagem", "pipe", "sessao", "pedido", "positivo", "negativo", "loras_ativas", "rel"),
                 grava=("imagem",))
def etapa(t):
    """Aumenta a imagem pela escala do pedido e refaz os detalhes com a força pedida."""
    import torch
    p, h = t.pedido, t.pedido["hires"]
    largura, altura = contrato.lado_hires(p["largura"], h["escala"]), contrato.lado_hires(p["altura"], h["escala"])
    maior = aumentar(t.sessao, t.imagem, largura, altura, h["upscaler"])
    pipe = t.sessao.derivado("StableDiffusionXLImg2ImgPipeline")
    modelo.preparar_vae(pipe, largura, altura)
    with torch.inference_mode():
        saida = pipe(**geracao.codificar(t.sessao, t.positivo, t.negativo), image=maior, strength=h["forca"],
                     num_inference_steps=passos_totais(h["passos"], h["forca"]), guidance_scale=p["cfg"],
                     generator=modelo.gerador(p["seed"]))
    t.imagem = saida.images[0]
    t.rel["hires"] = {"largura": largura, "altura": altura, "upscaler": h["upscaler"], "forca": h["forca"]}
