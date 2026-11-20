"""As fichas de personagem: um arquivo TOML por personagem, com as tags que o descrevem, o negativo, os LoRAs e notas.
O formato está em docs/fichas.md.

Módulo puro (só a biblioteca padrão: o tomllib lê, e a gravação é feita aqui, só para os campos da ficha).
"""
import json
import os
import re
import tomllib
import unicodedata

from aigen import contrato

_texto = (lambda v: isinstance(v, str))
CAMPOS_FICHA = {
    "nome": (lambda v: isinstance(v, str) and v.strip() != "", "um texto não vazio", contrato.OBRIGATORIO),
    "tags": (_texto, "um texto (tags separadas por vírgula)", ""),
    "negativo": (_texto, "um texto (tags separadas por vírgula)", ""),
    "notas": (_texto, "um texto", ""),
}


def conferir_ficha(info, origem="a ficha"):
    """Confere a ficha contra a versão 1 e devolve uma cópia completa (com os padrões)."""
    if not isinstance(info, dict):
        raise contrato.ErroPedido("%s não é uma tabela TOML" % origem)
    info = dict(info)
    versao = info.pop("versao_ficha", contrato.VERSAO_FICHA)
    if isinstance(versao, bool) or not isinstance(versao, int) or versao != contrato.VERSAO_FICHA:
        raise contrato.ErroPedido("%s tem versao_ficha %r; esta versão do AIGenerator conhece só a %d"
                                  % (origem, versao, contrato.VERSAO_FICHA))
    loras = info.pop("loras", [])
    ficha = contrato.conferir_campos(info, CAMPOS_FICHA, origem)
    ficha["nome"] = ficha["nome"].strip()
    ficha["loras"] = contrato.conferir_loras(loras, origem)
    return dict(ficha, versao_ficha=contrato.VERSAO_FICHA)


def ler_ficha(caminho):
    """Lê e confere uma ficha. Levanta ErroPedido se não der."""
    if not os.path.isfile(caminho):
        raise contrato.ErroPedido("ficha não encontrada: " + caminho)
    try:
        with open(caminho, "rb") as f:
            info = tomllib.load(f)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise contrato.ErroPedido("a ficha %s não é um TOML válido: %s" % (os.path.basename(caminho), e))
    return conferir_ficha(info, "a ficha " + os.path.basename(caminho))


def resolver(valor, pasta):
    """O arquivo de uma ficha: um caminho (termina em .toml ou tem uma barra) vale como está; um nome é procurado na
    pasta de fichas (`pasta`/<nome>.toml)."""
    if valor.endswith(".toml") or "/" in valor or os.sep in valor:
        return os.path.abspath(os.path.expanduser(valor))
    return os.path.join(pasta, valor + ".toml")


def listar(pasta):
    """Os nomes (sem .toml) das fichas da pasta, em ordem; [] se a pasta não existe."""
    if not os.path.isdir(pasta):
        return []
    return sorted(os.path.splitext(n)[0] for n in os.listdir(pasta) if n.endswith(".toml"))


def nome_de_arquivo(nome):
    """O nome de arquivo de uma ficha a partir do nome do personagem: minúsculas, sem acento, só [a-z0-9_-]."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    limpo = re.sub(r"[^a-z0-9_-]+", "_", sem_acento.lower()).strip("_")
    if not limpo:
        raise contrato.ErroPedido("o nome %r não dá um nome de arquivo (use letras ou números)" % nome)
    return limpo


def _toml_texto(v):
    # uma string JSON é uma string básica válida do TOML (as mesmas aspas e os mesmos escapes)
    return json.dumps(v, ensure_ascii=False)


def texto_toml(ficha):
    """O TOML de uma ficha conferida (o que gravar_ficha escreve e ler_ficha lê de volta igual)."""
    ficha = conferir_ficha(ficha)
    linhas = ["versao_ficha = %d" % contrato.VERSAO_FICHA]
    for campo in CAMPOS_FICHA:
        linhas.append("%s = %s" % (campo, _toml_texto(ficha[campo])))
    for lora in ficha["loras"]:
        linhas += ["", "[[loras]]", "nome = %s" % _toml_texto(lora["nome"]), "peso = %r" % float(lora["peso"])]
    return "\n".join(linhas) + "\n"


def gravar_ficha(ficha, caminho, sobrescrever=False):
    """Grava a ficha em `caminho`; sem `sobrescrever`, uma ficha que já existe é recusada."""
    texto = texto_toml(ficha)
    if os.path.exists(caminho) and not sobrescrever:
        raise contrato.ErroPedido("a ficha já existe: " + caminho)
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return caminho
