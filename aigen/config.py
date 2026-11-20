"""A configuração: onde estão o modelo, os LoRAs, o upscaler e o detector de rosto, e as pastas de fichas e de saída.

A ordem, do que vale mais para o que vale menos: a variável de ambiente (AIGEN_CHECKPOINT, ...), o config.local.ini
(fora do git: os caminhos de uma máquina) e o config.ini (versionado, só o modelo). Um caminho relativo é relativo à
raiz do repositório; "~" vale a pasta do usuário.

Módulo puro (só a biblioteca padrão).
"""
import configparser
import os

from aigen import contrato

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# atributo: (seção, chave, variável de ambiente, padrão, é caminho)
CHAVES = {
    "checkpoint": ("modelos", "checkpoint", "AIGEN_CHECKPOINT", "", True),
    "vae": ("modelos", "vae", "AIGEN_VAE", "", True),
    "pasta_loras": ("modelos", "pasta_loras", "AIGEN_LORAS", "models/loras", True),
    "upscaler": ("modelos", "upscaler", "AIGEN_UPSCALER", "models/upscalers/RealESRGAN_x4plus_anime_6B.pth", True),
    "detector_rosto": ("modelos", "detector_rosto", "AIGEN_DETECTOR_ROSTO",
                       "models/detectors/lbpcascade_animeface.xml", True),
    "pasta_fichas": ("pastas", "fichas", "AIGEN_FICHAS", "personagens", True),
    "pasta_saida": ("pastas", "saida", "AIGEN_SAIDA", "saida", True),
    "porta": ("web", "porta", "AIGEN_PORTA", "7860", False),
}


class Config:
    """Os valores já resolvidos (caminhos absolutos, ou "" quando não configurados)."""

    def __init__(self, valores):
        for nome, valor in valores.items():
            setattr(self, nome, valor)

    def __repr__(self):
        return "Config(%s)" % ", ".join("%s=%r" % (n, getattr(self, n)) for n in CHAVES)


def _caminho(valor, raiz):
    valor = os.path.expanduser(valor.strip())
    if not valor:
        return ""
    return os.path.normpath(valor if os.path.isabs(valor) else os.path.join(raiz, valor))


def _porta(texto):
    try:
        porta = int(texto)
    except ValueError:
        porta = -1
    if not 1 <= porta <= 65535:
        raise contrato.ErroPedido("a porta da interface web é %r; o esperado é um inteiro entre 1 e 65535" % texto)
    return porta


def ler(raiz=RAIZ, ambiente=None):
    """Lê config.ini e config.local.ini de `raiz` e as variáveis AIGEN_* de `ambiente` (padrão: os.environ)."""
    ambiente = os.environ if ambiente is None else ambiente
    ini = configparser.ConfigParser(interpolation=None)
    try:
        ini.read([os.path.join(raiz, "config.ini"), os.path.join(raiz, "config.local.ini")], encoding="utf-8")
    except configparser.Error as e:
        raise contrato.ErroPedido("o config.ini (ou o config.local.ini) não pôde ser lido: %s" % e)
    valores = {}
    for nome, (secao, chave, variavel, padrao, e_caminho) in CHAVES.items():
        valor = ambiente.get(variavel)
        if valor is None:
            valor = ini.get(secao, chave, fallback=padrao)
        valores[nome] = _caminho(valor, raiz) if e_caminho else valor.strip()
    valores["porta"] = _porta(valores["porta"])
    return Config(valores)
