"""O que vai dentro do PNG: o texto "parameters" no formato do AUTOMATIC1111 (que outros programas e sites leem) e o
bloco "aigen", um JSON com o pedido completo, de onde a imagem pode ser refeita.

Módulo puro (só a biblioteca padrão): quem grava e lê os blocos do PNG é o saida.py e o web.py.
"""
import json

from aigen import VERSAO, contrato

CHAVE_A1111 = "parameters"
CHAVE_AIGEN = "aigen"


def texto_parametros(pedido, positivo, negativo, modelo, loras=()):
    """O texto "parameters": o prompt, o negativo e uma linha "Campo: valor, ...". Os LoRAs vão no prompt como
    <lora:nome:peso>, como o AUTOMATIC1111 escreve."""
    linha_prompt = positivo + "".join(" <lora:%s:%g>" % (l["nome"], l["peso"]) for l in loras)
    campos = [("Steps", pedido["passos"]), ("Sampler", contrato.AMOSTRADORES[pedido["amostrador"]]),
              ("CFG scale", "%g" % pedido["cfg"]), ("Seed", pedido["seed"]),
              ("Size", "%dx%d" % (pedido["largura"], pedido["altura"]))]
    if modelo:
        campos.append(("Model", modelo))
    h = pedido["hires"]
    if h:
        campos += [("Denoising strength", "%g" % h["forca"]), ("Hires upscale", "%g" % h["escala"]),
                   ("Hires steps", h["passos"]), ("Hires upscaler", h["upscaler"])]
    if pedido["rosto"]:
        campos.append(("Face fix strength", "%g" % pedido["rosto"]["forca"]))
    campos.append(("Version", "aigen " + VERSAO))
    linhas = [linha_prompt]
    if negativo:
        linhas.append("Negative prompt: " + negativo)
    linhas.append(", ".join("%s: %s" % (k, v) for k, v in campos))
    return "\n".join(linhas)


def bloco_aigen(pedido, positivo, negativo, loras=()):
    """O JSON do bloco "aigen": o pedido (com a seed usada), o prompt final e os LoRAs."""
    return json.dumps({"versao_formato": contrato.VERSAO_SAIDAS, "pedido": pedido, "positivo": positivo,
                       "negativo": negativo, "loras": list(loras)}, ensure_ascii=False, sort_keys=True)


def pedido_do_png(textos):
    """O pedido (normalizado) guardado nos blocos de texto de um PNG ({chave: texto}). Levanta ErroPedido se o PNG
    não foi feito pelo AIGenerator."""
    if CHAVE_AIGEN not in textos:
        raise contrato.ErroPedido("o PNG não tem o bloco '%s': não foi feito pelo AIGenerator" % CHAVE_AIGEN)
    try:
        info = json.loads(textos[CHAVE_AIGEN])
    except ValueError as e:
        raise contrato.ErroPedido("o bloco '%s' do PNG não é um JSON válido: %s" % (CHAVE_AIGEN, e))
    if not isinstance(info, dict) or info.get("versao_formato") != contrato.VERSAO_SAIDAS:
        raise contrato.ErroPedido("o bloco '%s' do PNG tem uma versao_formato que esta versão não conhece"
                                  % CHAVE_AIGEN)
    return contrato.normalizar(info.get("pedido"), "o pedido do PNG")
