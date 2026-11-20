"""A correção de rosto: acha os rostos (uma cascata do OpenCV treinada em rostos de anime), recorta cada um com uma
margem, refaz o recorte em 1024 px com o inpaint do SDXL e cola de volta com a borda suave. Desligada por padrão
("rosto" no pedido, --rosto na linha de comando).

As contas das caixas são puras (testadas sem placa); a etapa usa o OpenCV, o PIL e o diffusers.
"""
from aigen import etapas, geracao, hires, modelo, prompts

LADO_INPAINT = 1024     # o recorte é refeito nesse tamanho (o do treino do SDXL)
ROSTO_MIN = 0.04        # um rosto menor que 4 % do lado menor da imagem é ignorado (quase sempre um falso achado)
BORDA = 0.08            # a borda suave da máscara, em fração do lado do recorte


def maiores(caixas, n):
    """As n maiores caixas (x, y, largura, altura), da maior para a menor; no empate, a de cima e à esquerda."""
    return sorted(caixas, key=lambda c: (-c[2] * c[3], c[1], c[0]))[:n]


def caixa_expandida(caixa, margem, largura, altura):
    """Um quadrado em volta da caixa, com `margem` (fração do lado do rosto) de cada lado, dentro da imagem."""
    x, y, w, h = caixa
    lado = min(max(w, h) * (1 + 2 * margem), largura, altura)
    cx, cy = x + w / 2.0, y + h / 2.0
    x0 = min(max(cx - lado / 2.0, 0.0), largura - lado)
    y0 = min(max(cy - lado / 2.0, 0.0), altura - lado)
    lado = int(round(lado))
    return (int(round(x0)), int(round(y0)), lado, lado)


def caixa_no_recorte(caixa, recorte, lado_novo):
    """A caixa do rosto em coordenadas do recorte depois de redimensionado para lado_novo × lado_novo."""
    x, y, w, h = caixa
    rx, ry, rl, _ = recorte
    f = lado_novo / float(rl)
    return (int(round((x - rx) * f)), int(round((y - ry) * f)), int(round(w * f)), int(round(h * f)))


def achar(sessao, imagem, max_rostos):
    import cv2
    import numpy
    cinza = cv2.equalizeHist(cv2.cvtColor(numpy.asarray(imagem.convert("RGB")), cv2.COLOR_RGB2GRAY))
    minimo = max(24, int(min(imagem.size) * ROSTO_MIN))
    achadas = sessao.detector().detectMultiScale(cinza, scaleFactor=1.1, minNeighbors=5, minSize=(minimo, minimo))
    return maiores([tuple(int(v) for v in c) for c in achadas], max_rostos)


def mascara(caixa_recorte, lado):
    """A máscara do inpaint: o retângulo do rosto em branco, com a borda desfocada."""
    from PIL import Image, ImageDraw, ImageFilter
    m = Image.new("L", (lado, lado), 0)
    x, y, w, h = caixa_recorte
    ImageDraw.Draw(m).rectangle((x, y, x + w, y + h), fill=255)
    return m.filter(ImageFilter.GaussianBlur(max(1, int(lado * BORDA))))


@etapas.declarar(le=("imagem", "pipe", "sessao", "pedido", "positivo", "negativo", "loras_ativas", "rel"),
                 grava=("imagem", "rostos"))
def etapa(t):
    """Refaz cada rosto achado (até max_rostos), do maior para o menor."""
    import torch
    from PIL import Image
    p, r = t.pedido, t.pedido["rosto"]
    imagem = t.imagem.convert("RGB")
    caixas = achar(t.sessao, imagem, r["max_rostos"])
    pipe = t.sessao.derivado("StableDiffusionXLInpaintPipeline") if caixas else None
    if pipe:
        modelo.preparar_vae(pipe, LADO_INPAINT, LADO_INPAINT)
    texto = prompts.juntar_tags(t.positivo, r["prompt"])
    for i, caixa in enumerate(caixas):
        recorte = caixa_expandida(caixa, r["margem"], *imagem.size)
        x, y, lado, _ = recorte
        pedaco = imagem.crop((x, y, x + lado, y + lado)).resize((LADO_INPAINT, LADO_INPAINT), Image.LANCZOS)
        m = mascara(caixa_no_recorte(caixa, recorte, LADO_INPAINT), LADO_INPAINT)
        with torch.inference_mode():
            novo = pipe(**geracao.codificar(t.sessao, texto, t.negativo), image=pedaco, mask_image=m,
                        width=LADO_INPAINT, height=LADO_INPAINT, strength=r["forca"],
                        num_inference_steps=hires.passos_totais(r["passos"], r["forca"]), guidance_scale=p["cfg"],
                        generator=modelo.gerador(p["seed"] + i + 1)).images[0]
        volta = novo.resize((lado, lado), Image.LANCZOS)
        imagem.paste(volta, (x, y), m.resize((lado, lado), Image.LANCZOS))
    t.imagem, t.rostos = imagem, [list(c) for c in caixas]
    t.rel["rosto"] = {"achados": len(caixas), "caixas": t.rostos, "forca": r["forca"]}
