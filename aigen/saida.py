"""A gravação: o PNG (com os blocos "parameters" e "aigen") e o relatório .aigen.json ao lado. Nenhum arquivo que já
existe é sobrescrito.
"""
import json
import os
import time

from aigen import VERSAO, contrato, etapas, metadados

SUFIXO_RELATORIO = ".aigen.json"


def relatorio_de(png):
    """O caminho do relatório de um PNG: x.png → x.aigen.json."""
    return os.path.splitext(png)[0] + SUFIXO_RELATORIO


def caminhos(saida, quantidade):
    """Os PNGs de um pedido: o próprio `saida` para uma imagem; x_001.png, x_002.png ... para várias."""
    if quantidade == 1:
        return [saida]
    base, ext = os.path.splitext(saida)
    return ["%s_%03d%s" % (base, i, ext) for i in range(1, quantidade + 1)]


def conferir_saidas(lista):
    """Recusa (ErroPedido) um PNG que não termina em .png e um PNG ou relatório que já existe."""
    for png in lista:
        if not png.lower().endswith(".png"):
            raise contrato.ErroPedido("a saída precisa terminar em .png: " + png)
        for c in (png, relatorio_de(png)):
            if os.path.exists(c):
                raise contrato.ErroPedido("a saída já existe (nada é sobrescrito): " + c)


def relatorio(t, nome_png):
    """O dicionário do relatório .aigen.json."""
    return {"versao_formato": contrato.VERSAO_SAIDAS, "aigen": VERSAO, "png": nome_png, "pedido": t.pedido,
            "modelo": os.path.basename(t.cfg.checkpoint), "segundos": round(time.time() - t.t_ini, 2),
            "tempos": dict(t.tempos), **t.rel}


def _gravar_novo(caminho, escrever):
    """Cria o arquivo só se ele não existe (modo "x"): duas gerações ao mesmo tempo nunca gravam uma por cima da outra."""
    with open(caminho, "xb") as f:
        escrever(f)


@etapas.declarar(le=("imagem", "pedido", "positivo", "negativo", "loras_ativas", "saida", "cfg", "rel"),
                 grava=("arquivos",))
def etapa(t):
    """Grava o PNG com os metadados e o relatório."""
    from PIL.PngImagePlugin import PngInfo
    modelo = os.path.splitext(os.path.basename(t.cfg.checkpoint))[0]
    info = PngInfo()
    info.add_text(metadados.CHAVE_A1111, metadados.texto_parametros(t.pedido, t.positivo, t.negativo, modelo,
                                                                    t.loras_ativas))
    info.add_text(metadados.CHAVE_AIGEN, metadados.bloco_aigen(t.pedido, t.positivo, t.negativo, t.loras_ativas))
    pasta = os.path.dirname(os.path.abspath(t.saida))
    os.makedirs(pasta, exist_ok=True)
    _gravar_novo(t.saida, lambda f: t.imagem.save(f, format="PNG", pnginfo=info))
    texto = json.dumps(relatorio(t, os.path.basename(t.saida)), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    caminho_json = relatorio_de(t.saida)
    _gravar_novo(caminho_json, lambda f: f.write(texto.encode("utf-8")))
    t.arquivos = (t.saida, caminho_json)
