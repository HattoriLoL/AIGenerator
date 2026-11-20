"""O programa: as opções, o trabalho e a sequência de etapas de uma geração.

    bin/aigen.sh saida.png [--pedido pedido.json] [--prompt "..."] [--ficha nome] [opções]

As opções da linha de comando valem sobre os campos do --pedido. Todas estão em docs/opcoes.md; o pedido, em
docs/contrato.md. Código de saída: 0 ok, 1 a imagem não saiu, 2 o pedido está errado e nada foi feito.
"""
import argparse
import os
import random
import sys
import time

from aigen import VERSAO, config, contrato, etapas, fichas, geracao, hires, loras, modelo, prompts, rosto, saida


class _Opcoes(argparse.ArgumentParser):
    """Um erro de opção termina com ERRO_PEDIDO e a mensagem começa com ERRO:, como todo erro do AIGenerator."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print("ERRO: " + message, file=sys.stderr)
        sys.exit(contrato.ERRO_PEDIDO)


def _opcoes_geracao(p):
    g = p.add_argument_group("geração")
    g.add_argument("--pedido", help="um pedido em JSON (docs/contrato.md); as opções abaixo valem sobre ele")
    g.add_argument("--prompt", help="as tags da cena, separadas por vírgula")
    g.add_argument("--negativo", help="as tags do negativo")
    g.add_argument("--ficha", help="uma ficha de personagem: o nome (na pasta de fichas) ou o caminho de um .toml")
    g.add_argument("--sem-qualidade", action="store_true", help="não põe as tags score_* do Pony no prompt")
    g.add_argument("--estilo", choices=list(contrato.ESTILOS) + ["nenhum"],
                   help="as tags de origem do Pony (padrão: anime); nenhum não põe nenhuma")
    g.add_argument("--permitir-explicito", action="store_true",
                   help="não põe as tags que bloqueiam a classificação explícita (rating_safe no positivo, ...)")
    g.add_argument("--largura", type=int)
    g.add_argument("--altura", type=int)
    g.add_argument("--passos", type=int)
    g.add_argument("--cfg", type=float)
    g.add_argument("--amostrador", choices=list(contrato.AMOSTRADORES))
    g.add_argument("--seed", type=int, help="-1 sorteia (o padrão)")
    g.add_argument("--quantidade", type=int, help="quantas imagens (seeds seguidas); saem x_001.png, x_002.png ...")
    g.add_argument("--lora", action="append", metavar="NOME[:PESO]",
                   help="um LoRA da pasta de LoRAs (repita para mais de um); soma-se aos do pedido e da ficha")


def _opcoes_extras(p):
    h = p.add_argument_group("hires fix (desligado por padrão)")
    h.add_argument("--hires", action="store_true", help="liga o hires fix")
    h.add_argument("--hires-escala", type=float)
    h.add_argument("--hires-forca", type=float)
    h.add_argument("--hires-passos", type=int)
    h.add_argument("--hires-upscaler", choices=list(contrato.UPSCALERS))
    r = p.add_argument_group("correção de rosto (desligada por padrão)")
    r.add_argument("--rosto", action="store_true", help="liga a correção de rosto")
    r.add_argument("--rosto-forca", type=float)
    r.add_argument("--rosto-passos", type=int)
    r.add_argument("--rosto-margem", type=float)
    r.add_argument("--rosto-prompt", help="tags a mais só para o rosto")
    r.add_argument("--rosto-max", type=int, help="quantos rostos no máximo")


def ler_args(argv, prog=None):
    p = _Opcoes(prog=prog or contrato.comando("aigen"),
                description="Gera imagens de personagens de anime com o Pony Diffusion XL.")
    p.add_argument("saida", help="o PNG a gravar (nunca sobrescrito); o relatório sai ao lado, em .aigen.json")
    p.add_argument("--versao", action="version", version="AIGenerator " + VERSAO)
    _opcoes_geracao(p)
    _opcoes_extras(p)
    return p.parse_args(argv)


SIMPLES = {"prompt": "prompt", "negativo": "negativo", "ficha": "ficha", "largura": "largura", "altura": "altura",
           "passos": "passos", "cfg": "cfg", "amostrador": "amostrador", "seed": "seed", "quantidade": "quantidade"}
HIRES = {"escala": "hires_escala", "forca": "hires_forca", "passos": "hires_passos", "upscaler": "hires_upscaler"}
ROSTO = {"forca": "rosto_forca", "passos": "rosto_passos", "margem": "rosto_margem", "prompt": "rosto_prompt",
         "max_rostos": "rosto_max"}


def _juntar_opcional(base, campo, ligar, valores):
    atual = base.get(campo)
    if ligar or valores:
        base[campo] = dict(atual if isinstance(atual, dict) else {}, **valores)


def pedido_dos_args(a):
    """O pedido normalizado: o do --pedido (ou um vazio), com as opções dadas por cima."""
    base = contrato.ler_pedido(a.pedido) if a.pedido else {}
    if not isinstance(base, dict):
        raise contrato.ErroPedido("o pedido %s não é um objeto JSON" % a.pedido)
    base = dict(base)
    for campo, opcao in SIMPLES.items():
        if getattr(a, opcao) is not None:
            base[campo] = getattr(a, opcao)
    if a.sem_qualidade:
        base["qualidade"] = False
    if a.estilo:
        base["estilo"] = None if a.estilo == "nenhum" else a.estilo
    if a.permitir_explicito:
        base["bloquear_explicito"] = False
    if a.lora:
        extra = loras.ler_lista(",".join(a.lora))
        base["loras"] = list(base.get("loras") or []) + extra
    _juntar_opcional(base, "hires", a.hires, {k: getattr(a, o) for k, o in HIRES.items() if getattr(a, o) is not None})
    _juntar_opcional(base, "rosto", a.rosto, {k: getattr(a, o) for k, o in ROSTO.items() if getattr(a, o) is not None})
    return contrato.normalizar(base, "o pedido" if not a.pedido else "o pedido " + os.path.basename(a.pedido))


class Trabalho:
    """O que as etapas leem e gravam numa geração (uma imagem). Ao nascer, só a etapas.BASE."""

    def __init__(self, pedido, saida_png, sessao, cfg):
        self.pedido, self.saida, self.sessao, self.cfg = pedido, saida_png, sessao, cfg
        self.t_ini, self.tempos = time.time(), {}


@etapas.declarar(le=("pedido", "cfg", "saida"), grava=("ficha", "rel"))
def conferir_pedido(t):
    """Tudo o que dá para conferir sem carregar o modelo: as bibliotecas, os arquivos dos modelos, a ficha, os LoRAs
    e a saída. Um problema aqui é um ErroPedido: nada foi carregado nem gravado."""
    p, cfg = t.pedido, t.cfg
    precisa = modelo.BIBLIOTECAS + (modelo.BIBLIOTECAS_HIRES if p["hires"] else ()) + \
        (modelo.BIBLIOTECAS_ROSTO if p["rosto"] else ())
    modelo.conferir_bibliotecas(precisa)
    if not cfg.checkpoint or not os.path.isfile(cfg.checkpoint):
        raise contrato.ErroPedido("checkpoint não encontrado (%s): configure [modelos] checkpoint no config.local.ini"
                                  " ou a variável AIGEN_CHECKPOINT" % (cfg.checkpoint or "nenhum configurado"))
    if p["hires"] and p["hires"]["upscaler"] == "modelo" and not os.path.isfile(cfg.upscaler):
        raise contrato.ErroPedido("modelo de upscale não encontrado: %s (ou use --hires-upscaler lanczos)"
                                  % cfg.upscaler)
    if p["rosto"] and not os.path.isfile(cfg.detector_rosto):
        raise contrato.ErroPedido("detector de rosto não encontrado: " + cfg.detector_rosto)
    t.ficha = fichas.ler_ficha(fichas.resolver(p["ficha"], cfg.pasta_fichas)) if p["ficha"] else None
    for lora in (t.ficha["loras"] if t.ficha else []) + p["loras"]:
        if not loras.arquivo(cfg.pasta_loras, lora["nome"]):
            raise contrato.ErroPedido("LoRA não encontrado: '%s' (na pasta %s)" % (lora["nome"], cfg.pasta_loras))
    saida.conferir_saidas([t.saida])
    t.rel = {"ficha": t.ficha["nome"] if t.ficha else None}


def sequencia(pedido):
    """As etapas de um pedido: o hires fix e a correção de rosto só quando pedidos."""
    s = [conferir_pedido, prompts.etapa, modelo.etapa, loras.etapa, geracao.etapa]
    if pedido["hires"]:
        s.append(hires.etapa)
    if pedido["rosto"]:
        s.append(rosto.etapa)
    s.append(saida.etapa)
    return tuple(s)


def rodar(pedido, saida_png, sessao, cfg, avisar=None):
    """Gera as imagens de um pedido normalizado e devolve [(png, relatório)]. As saídas são todas conferidas antes da
    primeira; com seed -1, uma é sorteada e as seguintes somam 1."""
    lista = saida.caminhos(saida_png, pedido["quantidade"])
    saida.conferir_saidas(lista)
    semente = pedido["seed"] if pedido["seed"] >= 0 else random.randrange(contrato.SEED_MAX + 1)
    feitos = []
    for i, png in enumerate(lista):
        um = dict(pedido, seed=(semente + i) % (contrato.SEED_MAX + 1), quantidade=1)
        seq = sequencia(um)
        etapas.conferir(seq)
        t = Trabalho(um, png, sessao, cfg)
        for f in seq:
            inicio = time.time()
            f(t)
            t.tempos[etapas.nome(f)] = round(time.time() - inicio, 3)
        feitos.append(t.arquivos)
        if avisar:
            avisar("%s (seed %d, %.1f s)" % (png, um["seed"], time.time() - t.t_ini))
    return feitos


def principal(argv=None):
    a = ler_args(sys.argv[1:] if argv is None else argv)
    try:
        cfg = config.ler()
        pedido = pedido_dos_args(a)
        rodar(pedido, os.path.abspath(a.saida), modelo.Sessao(cfg), cfg, avisar=print)
    except contrato.ErroPedido as e:
        print("ERRO: %s" % e, file=sys.stderr)
        return contrato.ERRO_PEDIDO
    except Exception as e:  # o modelo não carregou, faltou memória na placa, ...
        print("ERRO: a geração falhou: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        return contrato.ERRO_GERACAO
    return contrato.OK


if __name__ == "__main__":
    sys.exit(principal())
