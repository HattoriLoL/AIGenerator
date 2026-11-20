"""O contrato de entrada e saída do AIGenerator: as versões dos formatos, os códigos de saída e a conferência do pedido
de geração. A descrição completa, para quem chama o programa, está em docs/contrato.md.

Módulo puro (só a biblioteca padrão): os testes o usam direto (tests/test_contrato.py).
"""
import json
import math
import os

# Versões dos formatos. Uma versão nova só quando um campo muda de sentido ou some; campo novo e opcional não muda.
VERSAO_PEDIDO = 1    # o pedido de geração (JSON), campo "versao_pedido"; sem o campo, é a 1
VERSAO_FICHA = 1     # a ficha de personagem (TOML), campo "versao_ficha"; sem o campo, é a 1
VERSAO_SAIDAS = 1    # o relatório .aigen.json, o resumo lote.aigen.json e o bloco "aigen" do PNG, campo "versao_formato"

# Códigos de saída (iguais no gerar.py e no lote.py).
OK = 0
ERRO_GERACAO = 1     # uma imagem não pôde ser feita (o modelo não carregou, a geração falhou; no lote, algum pedido)
ERRO_PEDIDO = 2      # o pedido está errado e nada foi carregado nem gravado (opção, campo, ficha, LoRA, modelo, saída)

# Os amostradores e o nome que o AUTOMATIC1111 dá a cada um (o que vai no texto "parameters" do PNG). A classe do
# diffusers de cada um fica no modelo.py.
AMOSTRADORES = {
    "euler_a": "Euler a",
    "euler": "Euler",
    "dpmpp_2m": "DPM++ 2M",
    "dpmpp_2m_karras": "DPM++ 2M Karras",
    "dpmpp_2m_sde_karras": "DPM++ 2M SDE Karras",
    "ddim": "DDIM",
}
UPSCALERS = ("modelo", "lanczos")
ESTILOS = ("anime",)                # as tags de cada estilo ficam no prompts.py

LADO_MIN, LADO_MAX = 256, 2048      # largura e altura da primeira passada, múltiplos de 8
LADO_MAX_HIRES = 4096               # largura e altura depois do hires fix
SEED_MAX = 2 ** 32 - 1
PESO_LORA = 4.0                     # o peso de um LoRA fica entre -4 e 4


OBRIGATORIO = object()             # o "padrão" de um campo que não pode faltar


class ErroPedido(Exception):
    """O pedido não dá para começar: termina com ERRO_PEDIDO, antes de carregar o modelo e de gravar qualquer coisa."""


def comando(nome):
    """Como o usuário chama o programa, para as mensagens de uso e de erro."""
    return "bin/%s.sh" % nome


def _numero(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:  # inteiro do JSON grande demais para um float
        return False


def _inteiro(minimo, maximo):
    def ok(v):
        return isinstance(v, int) and not isinstance(v, bool) and minimo <= v <= maximo
    return ok


def _intervalo(minimo, maximo, abre_min=False):
    def ok(v):
        if not _numero(v):
            return False
        return (v > minimo if abre_min else v >= minimo) and v <= maximo
    return ok


def _lado(v):
    return _inteiro(LADO_MIN, LADO_MAX)(v) and v % 8 == 0


def _texto(v):
    return isinstance(v, str)


def _seed(v):
    return isinstance(v, int) and not isinstance(v, bool) and (v == -1 or 0 <= v <= SEED_MAX)


def _ficha(v):
    return v is None or (isinstance(v, str) and v.strip() != "")


# Campos do pedido, na versão 1: (conferência, o que se espera, padrão ou OBRIGATORIO). "loras", "hires" e "rosto"
# têm conferência própria (abaixo).
CAMPOS_PEDIDO = {
    "prompt": (_texto, "um texto (tags separadas por vírgula)", ""),
    "negativo": (_texto, "um texto", ""),
    "ficha": (_ficha, "o nome de uma ficha, o caminho de um .toml ou null", None),
    "qualidade": (lambda v: isinstance(v, bool), "true ou false", True),
    "estilo": (lambda v: v is None or v in ESTILOS, " ou ".join('"%s"' % e for e in ESTILOS) + " ou null", "anime"),
    "bloquear_explicito": (lambda v: isinstance(v, bool), "true ou false", True),
    "largura": (_lado, "um múltiplo de 8 entre %d e %d" % (LADO_MIN, LADO_MAX), 1024),
    "altura": (_lado, "um múltiplo de 8 entre %d e %d" % (LADO_MIN, LADO_MAX), 1024),
    "passos": (_inteiro(1, 150), "um inteiro entre 1 e 150", 25),
    "cfg": (_intervalo(1.0, 30.0), "um número entre 1 e 30", 7.0),
    "amostrador": (lambda v: v in AMOSTRADORES, "um de: " + ", ".join(AMOSTRADORES), "euler_a"),
    "seed": (_seed, "-1 (sorteada) ou um inteiro entre 0 e %d" % SEED_MAX, -1),
    "quantidade": (_inteiro(1, 64), "um inteiro entre 1 e 64", 1),
}
CAMPOS_HIRES = {
    "escala": (_intervalo(1.0, 4.0, abre_min=True), "um número maior que 1 e até 4", 1.5),
    "forca": (_intervalo(0.0, 1.0, abre_min=True), "um número maior que 0 e até 1", 0.4),
    "passos": (_inteiro(1, 150), "um inteiro entre 1 e 150", 15),
    "upscaler": (lambda v: v in UPSCALERS, "\"modelo\" ou \"lanczos\"", "modelo"),
}
CAMPOS_ROSTO = {
    "forca": (_intervalo(0.0, 1.0, abre_min=True), "um número maior que 0 e até 1", 0.4),
    "passos": (_inteiro(1, 150), "um inteiro entre 1 e 150", 20),
    "margem": (_intervalo(0.0, 2.0), "um número entre 0 e 2", 0.3),
    "prompt": (_texto, "um texto (tags a mais para o rosto)", ""),
    "max_rostos": (_inteiro(1, 16), "um inteiro entre 1 e 16", 4),
}
CAMPOS_LORA = {
    "nome": (lambda v: isinstance(v, str) and v.strip() != "", "o nome de um arquivo da pasta de LoRAs", OBRIGATORIO),
    "peso": (_intervalo(-PESO_LORA, PESO_LORA), "um número entre -%g e %g" % (PESO_LORA, PESO_LORA), 1.0),
}


def _valor(v):
    return json.dumps(v, ensure_ascii=False)


def conferir_campos(info, campos, onde):
    """Confere um objeto contra uma tabela de campos e devolve uma cópia com os padrões dos campos ausentes. Um campo
    que a tabela não conhece é recusado (quase sempre é um erro de digitação)."""
    if not isinstance(info, dict):
        raise ErroPedido("%s não é um objeto JSON" % onde)
    for campo in info:
        if campo not in campos:
            raise ErroPedido("%s tem o campo desconhecido '%s'; os campos são: %s" % (onde, campo, ", ".join(campos)))
    saida = {}
    for campo, (ok, esperado, padrao) in campos.items():
        if campo not in info:
            if padrao is OBRIGATORIO:
                raise ErroPedido("%s não tem o campo obrigatório '%s' (%s)" % (onde, campo, esperado))
            saida[campo] = padrao
            continue
        if not ok(info[campo]):
            raise ErroPedido("%s tem '%s' = %s; o esperado é %s" % (onde, campo, _valor(info[campo]), esperado))
        saida[campo] = info[campo]
    return saida


def conferir_loras(loras, onde):
    """Uma lista de {"nome", "peso"}; devolve a lista com o peso padrão (1) onde faltar."""
    if not isinstance(loras, list):
        raise ErroPedido("%s tem 'loras' = %s; o esperado é uma lista de {\"nome\", \"peso\"}" % (onde, _valor(loras)))
    saida = []
    for i, lora in enumerate(loras, 1):
        item = conferir_campos(lora, CAMPOS_LORA, "%s: o LoRA %d" % (onde, i))
        item["nome"] = item["nome"].strip()
        item["peso"] = float(item["peso"])
        saida.append(item)
    return saida


def _opcional(valor, campos, nome, onde):
    """hires e rosto: ausente, null ou false é desligado; true é ligado com os padrões; um objeto é ligado."""
    if valor is None or valor is False:
        return None
    if valor is True:
        valor = {}
    return conferir_campos(valor, campos, "%s: '%s'" % (onde, nome))


def normalizar(info, origem="o pedido"):
    """Confere o pedido contra a versão 1 e devolve uma cópia completa (com os padrões). Não muda o dicionário dado.
    Levanta ErroPedido dizendo qual campo e o que se espera."""
    if not isinstance(info, dict):
        raise ErroPedido("%s não é um objeto JSON" % origem)
    info = dict(info)
    versao = info.pop("versao_pedido", VERSAO_PEDIDO)
    if isinstance(versao, bool) or not isinstance(versao, (int, float)) or versao != VERSAO_PEDIDO:
        raise ErroPedido("%s tem versao_pedido %s; esta versão do AIGenerator conhece só a %d"
                         % (origem, _valor(versao), VERSAO_PEDIDO))
    loras = info.pop("loras", [])
    hires = info.pop("hires", None)
    rosto = info.pop("rosto", None)
    pedido = conferir_campos(info, CAMPOS_PEDIDO, origem)
    pedido["cfg"] = float(pedido["cfg"])
    pedido["loras"] = conferir_loras(loras, origem)
    pedido["hires"] = _opcional(hires, CAMPOS_HIRES, "hires", origem)
    pedido["rosto"] = _opcional(rosto, CAMPOS_ROSTO, "rosto", origem)
    if not pedido["prompt"].strip() and pedido["ficha"] is None:
        raise ErroPedido("%s não tem o que gerar: 'prompt' está vazio e não há 'ficha'" % origem)
    if pedido["hires"]:
        lado = max(pedido["largura"], pedido["altura"]) * pedido["hires"]["escala"]
        if lado > LADO_MAX_HIRES:
            raise ErroPedido("%s: com o hires fix, o lado maior chegaria a %d px; o máximo é %d"
                             % (origem, round(lado), LADO_MAX_HIRES))
    return dict(pedido, versao_pedido=VERSAO_PEDIDO)


def ler_pedido(caminho):
    """Lê um pedido de um arquivo JSON, sem conferir (quem chama junta as opções e chama normalizar)."""
    if not os.path.isfile(caminho):
        raise ErroPedido("pedido não encontrado: " + caminho)
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise ErroPedido("o pedido %s não é um JSON válido: %s" % (os.path.basename(caminho), e))


def lado_hires(lado, escala):
    """O lado depois do hires fix: lado × escala, arredondado para o múltiplo de 8 mais próximo."""
    return max(8, int(round(lado * escala / 8.0)) * 8)
