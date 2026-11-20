"""Os LoRAs: achar o arquivo na pasta, ler a lista "nome:peso" da linha de comando e da tela, e ligar no pipeline.

Só a etapa usa o diffusers (pelo pipeline que recebe); o resto é puro.
"""
import os
import re

from aigen import contrato, etapas

EXTENSAO = ".safetensors"


def arquivo(pasta, nome):
    """O arquivo do LoRA `nome` na pasta (com ou sem a extensão .safetensors), ou None."""
    for candidato in (nome, nome + EXTENSAO):
        caminho = os.path.join(pasta, candidato)
        if candidato.endswith(EXTENSAO) and os.path.isfile(caminho):
            return caminho
    return None


def listar(pasta):
    """Os nomes (sem .safetensors) dos LoRAs da pasta e das subpastas, em ordem; [] se a pasta não existe."""
    if not os.path.isdir(pasta):
        return []
    nomes = []
    for dirpath, _, arquivos in os.walk(pasta):
        for n in arquivos:
            if n.endswith(EXTENSAO):
                relativo = os.path.relpath(os.path.join(dirpath, n), pasta)
                nomes.append(relativo[:-len(EXTENSAO)].replace(os.sep, "/"))
    return sorted(nomes)


def ler_lista(texto):
    """A lista de LoRAs de um texto "nome:peso", um por linha ou separados por vírgula; sem ":peso", o peso é 1."""
    loras = []
    for item in re.split(r"[\n,]", texto or ""):
        item = item.strip()
        if not item:
            continue
        nome, _, peso = item.rpartition(":") if ":" in item else (item, "", "1")
        try:
            valor = float(peso)
        except ValueError:
            raise contrato.ErroPedido("o LoRA '%s' tem o peso '%s'; o esperado é um número (nome:peso)" % (item, peso))
        loras.append({"nome": nome.strip(), "peso": valor})
    return contrato.conferir_loras(loras, "a lista de LoRAs")


def nome_adaptador(nome):
    """Um nome de adaptador que o diffusers aceita (sem pontos nem barras)."""
    return "lora_" + re.sub(r"[^0-9A-Za-z_]", "_", nome)


@etapas.declarar(le=("pipe", "loras", "sessao", "cfg", "rel"), grava=("loras_ativas",))
def etapa(t):
    """Liga os LoRAs pedidos com os seus pesos. Os carregados ficam na sessão: só recarrega quando a lista muda."""
    pipe, sessao = t.pipe, t.sessao
    nomes = [l["nome"] for l in t.loras]
    if sorted(nomes) != sorted(sessao.loras_carregadas):
        if sessao.loras_carregadas:
            pipe.unload_lora_weights()
            sessao.loras_carregadas = ()
        for nome in nomes:
            caminho = arquivo(t.cfg.pasta_loras, nome)
            pipe.load_lora_weights(os.path.dirname(caminho), weight_name=os.path.basename(caminho),
                                   adapter_name=nome_adaptador(nome))
        sessao.loras_carregadas = tuple(nomes)
    if nomes:
        pipe.set_adapters([nome_adaptador(n) for n in nomes], adapter_weights=[l["peso"] for l in t.loras])
    t.loras_ativas = [dict(l) for l in t.loras]
    t.rel["loras"] = t.loras_ativas
