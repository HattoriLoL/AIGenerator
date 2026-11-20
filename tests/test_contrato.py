"""Testes do contrato (aigen/contrato.py) e das regras do repositório: uma regra, um caso. Não precisam do torch nem da
placa de vídeo e não geram nenhuma imagem (AGENTS.md, "Testing").

    python3 tests/test_contrato.py
"""
import ast
import glob
import os
import re
import sys
import tomllib
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from aigen import contrato, etapas, gerar, modelo  # noqa: E402

EXEMPLO = os.path.join(RAIZ, "examples", "pedido.json")


class Pedido(unittest.TestCase):
    def recusa(self, info, *trechos):
        with self.assertRaises(contrato.ErroPedido) as c:
            contrato.normalizar(info)
        for t in trechos:
            self.assertIn(t, str(c.exception))
        return str(c.exception)

    def test_o_exemplo_passa(self):
        p = contrato.normalizar(contrato.ler_pedido(EXEMPLO))
        self.assertEqual(p["versao_pedido"], 1)

    def test_os_padroes(self):
        p = contrato.normalizar({"prompt": "1girl"})
        self.assertEqual((p["largura"], p["altura"], p["passos"], p["cfg"], p["amostrador"], p["seed"]),
                         (1024, 1024, 25, 7.0, "euler_a", -1))
        self.assertTrue(p["qualidade"])
        self.assertEqual((p["estilo"], p["bloquear_explicito"]), ("anime", True))
        self.assertEqual((p["loras"], p["hires"], p["rosto"], p["ficha"], p["quantidade"]), ([], None, None, None, 1))

    def test_nao_muda_o_dicionario_dado(self):
        info = {"prompt": "1girl", "hires": True}
        contrato.normalizar(info)
        self.assertEqual(info, {"prompt": "1girl", "hires": True})

    def test_normalizar_duas_vezes_da_o_mesmo(self):
        p = contrato.normalizar({"prompt": "1girl", "hires": {"escala": 2}, "rosto": True,
                                 "loras": [{"nome": "x", "peso": 0.5}]})
        self.assertEqual(contrato.normalizar(p), p)

    def test_sem_versao_e_a_versao_1(self):
        contrato.normalizar({"prompt": "x"})
        contrato.normalizar({"prompt": "x", "versao_pedido": 1.0})

    def test_versao_desconhecida_e_recusada(self):
        for v in (2, 0, "1", True, None):
            self.recusa({"prompt": "x", "versao_pedido": v}, "versao_pedido")

    def test_sem_prompt_nem_ficha_e_recusado(self):
        self.recusa({}, "não tem o que gerar")
        self.recusa({"prompt": "   "}, "não tem o que gerar")
        contrato.normalizar({"ficha": "aiko"})

    def test_campo_desconhecido_e_recusado(self):
        self.recusa({"prompt": "x", "passo": 20}, "campo desconhecido 'passo'")
        self.recusa({"prompt": "x", "hires": {"scale": 2}}, "'hires'", "'scale'")

    def test_valores_fora_do_intervalo(self):
        ruins = {"largura": [255, 1000 + 1, 2056, 1024.0, "1024", True], "altura": [0, -8],
                 "passos": [0, 151, 2.5], "cfg": [0.5, 31, float("nan"), "7"], "amostrador": ["Euler a", ""],
                 "seed": [-2, 2 ** 32, 1.0], "quantidade": [0, 65], "qualidade": [1, "sim"],
                 "ficha": ["", "  ", 3], "prompt": [None, 1], "negativo": [None],
                 "estilo": ["manga", "", "nenhum"], "bloquear_explicito": [1, None, "true"]}
        for campo, valores in ruins.items():
            for v in valores:
                self.recusa({"prompt": "x", campo: v}, "'%s'" % campo)

    def test_valores_no_limite_passam(self):
        contrato.normalizar({"prompt": "x", "largura": 256, "altura": 2048, "passos": 150, "cfg": 30, "seed": 0,
                             "quantidade": 64})
        contrato.normalizar({"prompt": "x", "seed": 2 ** 32 - 1, "cfg": 1})
        self.assertIsNone(contrato.normalizar({"prompt": "x", "estilo": None})["estilo"])

    def test_hires_e_rosto_desligados_ligados_e_com_campos(self):
        for desligado in (None, False):
            self.assertIsNone(contrato.normalizar({"prompt": "x", "hires": desligado})["hires"])
        h = contrato.normalizar({"prompt": "x", "hires": True})["hires"]
        self.assertEqual(h, {"escala": 1.5, "forca": 0.4, "passos": 15, "upscaler": "modelo"})
        r = contrato.normalizar({"prompt": "x", "rosto": {"forca": 0.3}})["rosto"]
        self.assertEqual((r["forca"], r["max_rostos"]), (0.3, 4))
        self.recusa({"prompt": "x", "hires": {"escala": 1}}, "'escala'")
        self.recusa({"prompt": "x", "hires": {"upscaler": "esrgan"}}, "'upscaler'")
        self.recusa({"prompt": "x", "rosto": {"forca": 0}}, "'forca'")
        self.recusa({"prompt": "x", "hires": "sim"}, "não é um objeto")

    def test_hires_alem_do_maximo_e_recusado(self):
        self.recusa({"prompt": "x", "largura": 2048, "hires": {"escala": 2.5}}, "o máximo é 4096")
        contrato.normalizar({"prompt": "x", "largura": 2048, "hires": {"escala": 2}})

    def test_loras(self):
        p = contrato.normalizar({"prompt": "x", "loras": [{"nome": " estilo "}, {"nome": "b", "peso": -1}]})
        self.assertEqual(p["loras"], [{"nome": "estilo", "peso": 1.0}, {"nome": "b", "peso": -1.0}])
        self.recusa({"prompt": "x", "loras": [{"peso": 1}]}, "o LoRA 1", "obrigatório 'nome'")
        self.recusa({"prompt": "x", "loras": [{"nome": "a", "peso": 5}]}, "'peso'")
        self.recusa({"prompt": "x", "loras": "a:1"}, "'loras'")

    def test_lado_hires_e_multiplo_de_8(self):
        self.assertEqual(contrato.lado_hires(1024, 1.5), 1536)
        self.assertEqual(contrato.lado_hires(832, 1.3) % 8, 0)


class Arquivo(unittest.TestCase):
    def test_que_nao_existe(self):
        with self.assertRaises(contrato.ErroPedido) as c:
            contrato.ler_pedido(os.path.join(RAIZ, "examples", "nao_existe.json"))
        self.assertIn("pedido não encontrado", str(c.exception))


class Codigos(unittest.TestCase):
    def test_codigos_e_versoes(self):
        self.assertEqual((contrato.OK, contrato.ERRO_GERACAO, contrato.ERRO_PEDIDO), (0, 1, 2))
        self.assertEqual((contrato.VERSAO_PEDIDO, contrato.VERSAO_FICHA, contrato.VERSAO_SAIDAS), (1, 1, 1))

    def test_opcao_errada_sai_com_2_e_erro(self):
        with self.assertRaises(SystemExit) as c:
            gerar.ler_args(["--passos", "muitos", "x.png"])
        self.assertEqual(c.exception.code, contrato.ERRO_PEDIDO)

    def test_os_amostradores_do_contrato_sao_os_do_modelo(self):
        self.assertEqual(set(contrato.AMOSTRADORES), set(modelo.AGENDADORES))


def _modulos():
    mods = {}
    for f in sorted(glob.glob(os.path.join(RAIZ, "aigen", "*.py"))):
        with open(f, encoding="utf-8") as arq:
            mods[os.path.basename(f)[:-3]] = ast.parse(arq.read())
    return mods


class Estrutura(unittest.TestCase):
    """As regras do código de aigen/: funções curtas, nenhum ciclo de importação e nenhuma biblioteca pesada importada
    no topo de um módulo (AGENTS.md, "Rules")."""

    PESADAS = {"torch", "diffusers", "transformers", "accelerate", "safetensors", "compel", "PIL", "numpy", "cv2",
               "spandrel", "gradio"}

    @classmethod
    def setUpClass(cls):
        cls.mods = _modulos()

    def test_nenhuma_funcao_passa_de_80_linhas(self):
        longas = ["%s.%s (%d linhas)" % (m, n.name, n.end_lineno - n.lineno + 1)
                  for m, t in self.mods.items() for n in ast.walk(t)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.end_lineno - n.lineno + 1 > 80]
        self.assertEqual(longas, [])

    def test_nenhum_modulo_importa_outro_em_ciclo(self):
        grafo = {m: set() for m in self.mods}
        for m, t in self.mods.items():
            for n in ast.walk(t):
                if isinstance(n, ast.ImportFrom) and n.module == "aigen":
                    grafo[m] |= {a.name for a in n.names if a.name in self.mods}
                elif isinstance(n, ast.ImportFrom) and (n.module or "").startswith("aigen."):
                    grafo[m].add(n.module.split(".", 1)[1])

        def ciclo(m, caminho):
            for d in sorted(grafo[m]):
                if d in caminho:
                    return caminho[caminho.index(d):] + [d]
                c = ciclo(d, caminho + [d])
                if c:
                    return c
            return None
        for m in self.mods:
            self.assertIsNone(ciclo(m, [m]), "ciclo de importação")

    def test_nenhuma_biblioteca_pesada_no_topo(self):
        achados = []
        for m, t in self.mods.items():
            topo = [n for n in t.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.If, ast.Try))]
            for no in topo:
                for n in ast.walk(no):
                    if isinstance(n, ast.Import):
                        nomes = [a.name for a in n.names]
                    elif isinstance(n, ast.ImportFrom):
                        nomes = [n.module or ""]
                    else:
                        continue
                    achados += ["%s: %s" % (m, x) for x in nomes if x.split(".")[0] in self.PESADAS]
        self.assertEqual(achados, [])

    def test_toda_etapa_da_sequencia_declara(self):
        for hires in (None, True):
            for rosto in (None, True):
                p = contrato.normalizar({"prompt": "x", "hires": hires, "rosto": rosto})
                etapas.conferir(gerar.sequencia(p))


class Lancadores(unittest.TestCase):
    """Os lançadores de bin/: todos acham o Python pelo bin/_python.sh (a busca num lugar só) e param com 2 sem ele."""

    QUE_CHAMAM = ("aigen.sh", "aigen_lote.sh", "aigen_web.sh")

    def ler(self, nome):
        with open(os.path.join(RAIZ, "bin", nome), encoding="utf-8") as f:
            return f.read()

    def test_a_busca_num_lugar_so(self):
        for nome in self.QUE_CHAMAM:
            texto = self.ler(nome)
            self.assertIn('/_python.sh"', texto, nome)
            self.assertIn('[ -n "$PY" ] || exit 2', texto, nome)
            self.assertNotIn(".venv", texto, nome + ": a busca é a do bin/_python.sh")

    def test_o_atalho_acha_o_python_igual_e_abre_o_navegador(self):
        texto = self.ler("abrir_web.sh")
        self.assertIn('/_python.sh"', texto)
        self.assertIn("-m aigen.web --abrir", texto)
        self.assertIn("abrir_web.sh", self.ler("instalar_atalho.sh"))

    def test_cada_lancador_chama_o_seu_modulo(self):
        for nome, mod in zip(self.QUE_CHAMAM, ("gerar", "lote", "web")):
            self.assertIn("-m aigen.%s " % mod, self.ler(nome), nome)
            self.assertTrue(os.path.isfile(os.path.join(RAIZ, "aigen", mod + ".py")))

    def test_sao_executaveis(self):
        for nome in self.QUE_CHAMAM + ("abrir_web.sh", "instalar.sh", "instalar_atalho.sh", "baixar_auxiliares.sh"):
            self.assertTrue(os.access(os.path.join(RAIZ, "bin", nome), os.X_OK), nome)


class Documentos(unittest.TestCase):
    """O que os documentos dizem do código é conferido contra o código."""

    def ler(self, nome):
        with open(os.path.join(RAIZ, nome), encoding="utf-8") as f:
            return f.read()

    def test_toda_dependencia_tem_a_licenca_listada(self):
        with open(os.path.join(RAIZ, "pyproject.toml"), "rb") as f:
            deps = tomllib.load(f)["project"]["dependencies"]
        licencas = self.ler(os.path.join("docs", "licencas.md")).lower()
        for d in deps:
            nome = re.match(r"[A-Za-z0-9_.\-]+", d).group(0).lower()
            self.assertIn("| %s |" % nome, licencas, "docs/licencas.md não lista " + nome)

    def test_a_tabela_das_etapas_e_a_que_as_etapas_declaram(self):
        p = contrato.normalizar({"prompt": "x", "hires": True, "rosto": True})
        esperado = [(etapas.nome(f), ", ".join(sorted(f.le)), ", ".join(sorted(f.grava))) for f in gerar.sequencia(p)]
        secao = self.ler("docs/como-funciona.md").split("## The stages in the code", 1)[1].split("\n## ", 1)[0]
        linhas = re.findall(r"^\| `([a-z_]+\.[a-z_]+)` \| ([^|]*) \| ([^|]*) \|", secao, re.M)
        achado = [(n, le.strip().replace("`", ""), grava.strip().replace("`", "")) for n, le, grava in linhas]
        self.assertEqual(achado, esperado)

    def test_todo_campo_do_pedido_esta_no_contrato(self):
        texto = self.ler(os.path.join("docs", "contrato.md"))
        for campo in list(contrato.CAMPOS_PEDIDO) + ["loras", "hires", "rosto", "versao_pedido"]:
            self.assertTrue("`%s`" % campo in texto, "docs/contrato.md não cita o campo " + campo)
        for campos in (contrato.CAMPOS_HIRES, contrato.CAMPOS_ROSTO):
            for campo in campos:
                self.assertTrue("`%s`" % campo in texto, "docs/contrato.md não cita o campo " + campo)


class Isolamento(unittest.TestCase):
    """Nada de um projeto privado do dono do clone entra no repositório público. Os termos ficam numa lista local,
    fora do git (.aigen-proibidos: um termo por linha, sem diferença de maiúsculas, # comenta); sem ela, os casos são
    pulados. Confere o nome e o texto de todo arquivo versionado e, nos commits que nenhum remoto tem ainda, o autor,
    a mensagem e cada linha acrescentada. No gancho pre-push o teste roda numa cópia da árvore: AIGEN_GIT_RAIZ é o
    repositório (onde está a lista) e AIGEN_REV, o commit que sobe; sem eles, este repositório e o índice."""

    LISTA = ".aigen-proibidos"
    REPO = os.environ.get("AIGEN_GIT_RAIZ", RAIZ)
    REV = os.environ.get("AIGEN_REV")

    @classmethod
    def git(cls, *args):
        import subprocess
        try:
            r = subprocess.run(["git", "-C", cls.REPO, "-c", "core.quotePath=false"] + list(args),
                               capture_output=True, check=False)
        except OSError:
            return None
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None

    def termos(self):
        caminho = os.path.join(self.REPO, self.LISTA)
        if not os.path.isfile(caminho):
            self.skipTest("sem a lista local " + self.LISTA)
        with open(caminho, encoding="utf-8") as f:
            termos = [t.strip().lower() for t in f if t.strip() and not t.strip().startswith("#")]
        if not termos:
            self.skipTest("a lista local %s está vazia" % self.LISTA)
        return termos

    def versionados(self):
        ls = self.git("ls-tree", "-r", "-z", "--name-only", self.REV) if self.REV else self.git("ls-files", "-z")
        if ls is None:
            self.skipTest("sem o git")
        return [c for c in ls.split("\0") if c]

    @staticmethod
    def achar(termos, texto):
        baixo = texto.lower()
        return [t for t in termos if t in baixo]

    def test_a_lista_nao_e_versionada(self):
        self.termos()
        self.assertNotIn(self.LISTA, self.versionados())

    def test_nenhum_arquivo_cita_um_termo(self):
        termos, achados = self.termos(), []
        for c in self.versionados():
            achados += ["%s (no nome): %s" % (c, t) for t in self.achar(termos, c)]
            f = os.path.join(RAIZ, c)
            if not os.path.isfile(f):
                continue
            with open(f, "rb") as arq:
                dados = arq.read()
            if b"\0" in dados[:8192]:
                continue  # binário
            for i, linha in enumerate(dados.decode("utf-8", "replace").splitlines(), 1):
                achados += ["%s:%d: %s" % (c, i, t) for t in self.achar(termos, linha)]
        self.assertEqual(achados, [])

    def test_nenhum_commit_novo_cita_um_termo(self):
        termos = self.termos()
        log = self.git("log", "-p", "--unified=0", "--no-color", "--no-ext-diff", "--no-renames",
                       "--format=%x01%h %an <%ae> %cn <%ce>%n%B", self.REV or "HEAD", "--not", "--remotes")
        if log is None:
            self.skipTest("sem o git ou sem commits")
        achados, commit = [], "?"
        for linha in log.splitlines():
            if linha.startswith("\x01"):
                commit = linha[1:].split()[0]
                linha = linha[1:]
            elif linha.startswith(("-", "@@")):
                continue  # o que sai e o contexto do trecho são do que já existia
            achados += ["commit %s: %s" % (commit, t) for t in self.achar(termos, linha)]
        self.assertEqual(achados, [])


if __name__ == "__main__":
    resultado = unittest.main(argv=["test_contrato"], exit=False, verbosity=2).result
    sys.stdout.flush()
    sys.exit(0 if resultado.wasSuccessful() else 1)
