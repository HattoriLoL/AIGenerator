"""A montagem do prompt: as tags de qualidade do Pony, a ficha de personagem e a cena, sem tags repetidas; e a
tradução dos pesos do AUTOMATIC1111 ("(tag:1.2)", "(tag)", "[tag]") para a sintaxe do compel ("(tag)1.2").

Módulo puro (só a biblioteca padrão), menos a etapa, que só mexe no trabalho.
"""
import re

from aigen import etapas

# As tags de qualidade do Pony Diffusion V6 XL (o modelo foi treinado com elas; sem elas a qualidade cai), postas na
# frente do prompt quando o pedido tem "qualidade": true. O negativo leva as notas baixas.
TAGS_QUALIDADE = "score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up"
TAGS_QUALIDADE_NEGATIVO = "score_6, score_5, score_4"
# Os estilos ("estilo" no pedido): as tags de origem do Pony, (positivo, negativo). Os nomes são os de contrato.ESTILOS.
ESTILOS = {
    "anime": ("source_anime", "source_cartoon, source_furry, source_pony, 3d, realistic, photorealistic"),
}
# "bloquear_explicito": true pede conteúdo sem classificação explícita, (positivo, negativo).
TAGS_SEGURO = ("rating_safe", "rating_questionable, rating_explicit")


def separar_tags(texto):
    """As tags de um texto, separadas pelas vírgulas que estão fora de parênteses e colchetes ("\\(" não conta)."""
    tags, atual, nivel, i = [], [], 0, 0
    while i < len(texto):
        c = texto[i]
        if c == "\\" and i + 1 < len(texto):
            atual.append(texto[i:i + 2])
            i += 2
            continue
        if c in "([":
            nivel += 1
        elif c in ")]" and nivel > 0:
            nivel -= 1
        if c == "," and nivel == 0:
            tags.append("".join(atual))
            atual = []
        else:
            atual.append(c)
        i += 1
    tags.append("".join(atual))
    return [t.strip() for t in tags if t.strip()]


def _chave(tag):
    return re.sub(r"\s+", " ", tag.strip().lower())


def juntar_tags(*partes):
    """Junta os textos numa lista de tags só, na ordem, sem repetir (a primeira vez vale; maiúsculas e espaços a mais
    não contam)."""
    vistas, saida = set(), []
    for parte in partes:
        for tag in separar_tags(parte or ""):
            if _chave(tag) not in vistas:
                vistas.add(_chave(tag))
                saida.append(tag)
    return ", ".join(saida)


def montar(pedido, ficha=None):
    """(positivo, negativo) de um pedido normalizado e de uma ficha (ou None), nesta ordem: qualidade, estilo,
    classificação, ficha e cena."""
    qualidade = (TAGS_QUALIDADE, TAGS_QUALIDADE_NEGATIVO) if pedido["qualidade"] else ("", "")
    estilo = ESTILOS[pedido["estilo"]] if pedido["estilo"] else ("", "")
    seguro = TAGS_SEGURO if pedido["bloquear_explicito"] else ("", "")
    da_ficha = (ficha["tags"], ficha["negativo"]) if ficha else ("", "")
    cena = (pedido["prompt"], pedido["negativo"])
    partes = (qualidade, estilo, seguro, da_ficha, cena)
    return juntar_tags(*(p[0] for p in partes)), juntar_tags(*(p[1] for p in partes))


def juntar_loras(da_ficha, do_pedido):
    """Os LoRAs da ficha e os do pedido, sem repetir o nome: o peso do pedido vale sobre o da ficha."""
    pesos = {}
    for lora in list(da_ficha) + list(do_pedido):
        pesos[lora["nome"]] = lora["peso"]
    return [{"nome": n, "peso": p} for n, p in pesos.items()]


# Os pedaços da sintaxe do AUTOMATIC1111 (o mesmo desenho do parse_prompt_attention dele).
_ATENCAO = re.compile(r"\\\(|\\\)|\\\[|\\\]|\\\\|\\|\(|\[|:\s*([+-]?[.\d]+)\s*\)|\)|\]|[^\\()\[\]:]+|:")
_MAIS, _MENOS = 1.1, 1 / 1.1


def _peso(texto):
    try:
        return float(texto)
    except ValueError:
        return None


def pesos(texto):
    """[(trecho, peso)] de um prompt na sintaxe do AUTOMATIC1111: "(x:1.3)" multiplica por 1,3, "(x)" por 1,1 e
    "[x]" divide por 1,1; aninhados, multiplicam; "\\(" é um parêntese de verdade. Trechos vizinhos com o mesmo peso
    viram um só."""
    res, abre_par, abre_col = [], [], []

    def multiplicar(inicio, fator):
        for p in range(inicio, len(res)):
            res[p][1] *= fator

    for m in _ATENCAO.finditer(texto):
        pedaco, numero = m.group(0), m.group(1)
        peso = _peso(numero) if numero is not None else None
        if pedaco.startswith("\\"):
            res.append([pedaco[1:] if len(pedaco) > 1 else pedaco, 1.0])
        elif pedaco == "(":
            abre_par.append(len(res))
        elif pedaco == "[":
            abre_col.append(len(res))
        elif peso is not None and abre_par:
            multiplicar(abre_par.pop(), peso)
        elif pedaco == ")" and abre_par:
            multiplicar(abre_par.pop(), _MAIS)
        elif pedaco == "]" and abre_col:
            multiplicar(abre_col.pop(), _MENOS)
        else:
            res.append([pedaco, 1.0])
    for inicio in abre_par:
        multiplicar(inicio, _MAIS)
    for inicio in abre_col:
        multiplicar(inicio, _MENOS)
    juntos = []
    for trecho, peso in res:
        if juntos and abs(juntos[-1][1] - peso) < 1e-9:
            juntos[-1][0] += trecho
        else:
            juntos.append([trecho, peso])
    return [(t, p) for t, p in juntos if t]


def _escapar_compel(trecho):
    return re.sub(r"([()\\])", r"\\\1", trecho)


def para_compel(texto):
    """O prompt na sintaxe do compel: cada trecho com peso diferente de 1 vira "(trecho)peso"."""
    partes = []
    for trecho, peso in pesos(texto):
        escapado = _escapar_compel(trecho)
        if abs(peso - 1.0) < 1e-6:
            partes.append(escapado)
        elif escapado.strip(" ,"):
            antes = escapado[:len(escapado) - len(escapado.lstrip(" ,"))]
            depois = escapado[len(escapado.rstrip(" ,")):]
            partes.append("%s(%s)%s%s" % (antes, escapado.strip(" ,"), ("%.4f" % peso).rstrip("0").rstrip("."), depois))
        else:
            partes.append(escapado)
    return "".join(partes)


@etapas.declarar(le=("pedido", "ficha", "rel"), grava=("positivo", "negativo", "loras"))
def etapa(t):
    """Monta o prompt final e a lista de LoRAs (os da ficha e os do pedido)."""
    t.positivo, t.negativo = montar(t.pedido, t.ficha)
    t.loras = juntar_loras(t.ficha["loras"] if t.ficha else [], t.pedido["loras"])
    t.rel["prompt"] = {"positivo": t.positivo, "negativo": t.negativo}
