"""O modo em lote: todos os pedidos (*.json) de uma pasta, com o modelo carregado uma vez só.

    bin/aigen_lote.sh pasta_de_pedidos pasta_de_saida

Cada pedido x.json vira pasta_de_saida/x.png (ou x_001.png ... com "quantidade"). Um pedido errado ou que falha não
para os outros; o resumo vai em pasta_de_saida/lote.aigen.json. Código de saída: 0 todos ok; 1 algum falhou; 2 o
pedido do lote está errado (pasta que não existe, sem pedidos, resumo que já existe).
"""
import json
import os
import sys
import time

from aigen import VERSAO, config, contrato, gerar, modelo

RESUMO = "lote.aigen.json"


def ler_args(argv):
    p = gerar._Opcoes(prog=contrato.comando("aigen_lote"),
                      description="Gera as imagens de todos os pedidos (*.json) de uma pasta.")
    p.add_argument("pedidos", help="a pasta com os pedidos (*.json, docs/contrato.md)")
    p.add_argument("saida", help="a pasta onde gravar os PNGs e o resumo lote.aigen.json")
    p.add_argument("--versao", action="version", version="AIGenerator " + VERSAO)
    return p.parse_args(argv)


def listar_pedidos(pasta):
    if not os.path.isdir(pasta):
        raise contrato.ErroPedido("pasta de pedidos não encontrada: " + pasta)
    nomes = sorted(n for n in os.listdir(pasta) if n.endswith(".json") and not n.endswith(".aigen.json"))
    if not nomes:
        raise contrato.ErroPedido("a pasta %s não tem pedidos (*.json)" % pasta)
    return [os.path.join(pasta, n) for n in nomes]


def _um(caminho, destino, sessao, cfg):
    nome = os.path.splitext(os.path.basename(caminho))[0]
    item = {"pedido": os.path.basename(caminho)}
    inicio = time.time()
    try:
        pedido = contrato.normalizar(contrato.ler_pedido(caminho), "o pedido " + os.path.basename(caminho))
        feitos = gerar.rodar(pedido, os.path.join(destino, nome + ".png"), sessao, cfg)
        item.update(ok=True, png=[os.path.basename(png) for png, _ in feitos])
    except contrato.ErroPedido as e:
        item.update(ok=False, erro="ERRO: %s" % e)
    except Exception as e:  # o lote continua: o próximo pedido pode dar certo
        item.update(ok=False, erro="ERRO: a geração falhou: %s: %s" % (type(e).__name__, e))
    item["segundos"] = round(time.time() - inicio, 2)
    print(("ok    " if item["ok"] else "falhou ") + item["pedido"] + ("" if item["ok"] else ": " + item["erro"]))
    return item


def principal(argv=None):
    a = ler_args(sys.argv[1:] if argv is None else argv)
    try:
        cfg = config.ler()
        lista = listar_pedidos(a.pedidos)
        resumo = os.path.join(a.saida, RESUMO)
        if os.path.exists(resumo):
            raise contrato.ErroPedido("o resumo já existe (nada é sobrescrito): " + resumo)
    except contrato.ErroPedido as e:
        print("ERRO: %s" % e, file=sys.stderr)
        return contrato.ERRO_PEDIDO
    os.makedirs(a.saida, exist_ok=True)
    sessao = modelo.Sessao(cfg)
    itens = [_um(c, a.saida, sessao, cfg) for c in lista]
    falhas = sum(1 for i in itens if not i["ok"])
    with open(resumo, "x", encoding="utf-8") as f:
        json.dump({"versao_formato": contrato.VERSAO_SAIDAS, "aigen": VERSAO, "pedidos": itens, "falhas": falhas},
                  f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("%d pedido(s), %d falha(s); resumo em %s" % (len(itens), falhas, resumo))
    return contrato.ERRO_GERACAO if falhas else contrato.OK


if __name__ == "__main__":
    sys.exit(principal())
