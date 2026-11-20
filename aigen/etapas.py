"""As etapas declaram o que leem e o que gravam no trabalho (t, de gerar.py), e uma sequência é conferida antes de rodar.

    @etapas.declarar(le=("pedido", "ficha"), grava=("positivo", "negativo"))
    def etapa(t): ...

`conferir(sequencia)` percorre as etapas na ordem e recusa (ErroSequencia) a que não tem declaração e a que lê um
dado que nem a BASE (o que o Trabalho já traz ao nascer) nem uma etapa anterior grava: uma sequência errada para
antes de carregar qualquer coisa na placa de vídeo.

Módulo puro (só a biblioteca padrão): os testes o importam sem o torch.
"""
import os

# o que o Trabalho traz ao nascer (gerar.Trabalho.__init__)
BASE = frozenset(("pedido", "saida", "sessao", "cfg", "t_ini", "tempos"))


class ErroSequencia(Exception):
    """Uma sequência de etapas que não fecha: uma etapa sem declaração, ou que lê o que ninguém antes gravou."""


def declarar(le=(), grava=()):
    """Põe em f os conjuntos f.le e f.grava e devolve a mesma função."""
    def marcar(f):
        f.le, f.grava = frozenset(le), frozenset(grava)
        return f
    return marcar


def nome(f):
    """'<arquivo sem .py>.<função>': pelo arquivo, e não pelo __module__, que é '__main__' quando roda com -m."""
    return "%s.%s" % (os.path.splitext(os.path.basename(f.__code__.co_filename))[0], f.__name__)


def conferir(sequencia):
    """Recusa a sequência que não fecha, com o nome da etapa e do dado na mensagem; não roda nenhuma etapa."""
    gravados = set(BASE)
    for f in sequencia:
        if not (hasattr(f, "le") and hasattr(f, "grava")):
            raise ErroSequencia("a etapa '%s' não declara o que lê e o que grava" % nome(f))
        faltam = sorted(f.le - gravados)
        if faltam:
            raise ErroSequencia("sequência de etapas inválida: a etapa '%s' lê '%s', que nenhuma etapa anterior grava"
                                % (nome(f), faltam[0]))
        gravados |= f.grava
