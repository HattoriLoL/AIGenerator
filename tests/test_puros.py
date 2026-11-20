"""Testes dos módulos puros: o prompt, as fichas, os LoRAs, os metadados, a configuração, as sequências de etapas e as
contas da correção de rosto e da interface. Não precisam do torch nem da placa de vídeo e não geram nenhuma imagem.

    python3 tests/test_puros.py
"""
import datetime
import json
import os
import sys
import tempfile
import tomllib
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from aigen import (config, contrato, etapas, fichas, gerar, hires, loras, metadados, modelo, prompts,  # noqa: E402
                   rosto, saida, web)

FICHA_EXEMPLO = os.path.join(RAIZ, "examples", "personagens", "exemplo.toml")


def pedido(**campos):
    return contrato.normalizar(dict({"prompt": "1girl"}, **campos))


class Tags(unittest.TestCase):
    def test_separa_pelas_virgulas_de_fora(self):
        self.assertEqual(prompts.separar_tags("a, (b, c:1.2), [d,e], f"), ["a", "(b, c:1.2)", "[d,e]", "f"])
        self.assertEqual(prompts.separar_tags(r"artist \(style\), x"), [r"artist \(style\)", "x"])
        self.assertEqual(prompts.separar_tags(" , ,"), [])

    def test_junta_sem_repetir(self):
        self.assertEqual(prompts.juntar_tags("a, B", "b,  c", "A , d"), "a, B, c, d")
        self.assertEqual(prompts.juntar_tags("", None, "x"), "x")

    def test_montar_na_ordem_qualidade_estilo_classificacao_ficha_cena(self):
        ficha = {"tags": "1girl, silver hair", "negativo": "bad hands", "loras": []}
        pos, neg = prompts.montar(pedido(prompt="smile, 1girl", negativo="blurry"), ficha)
        anime, anime_neg = prompts.ESTILOS["anime"]
        seguro, seguro_neg = prompts.TAGS_SEGURO
        self.assertEqual(pos, ", ".join((prompts.TAGS_QUALIDADE, anime, seguro, "1girl, silver hair, smile")))
        self.assertEqual(neg, ", ".join((prompts.TAGS_QUALIDADE_NEGATIVO, anime_neg, seguro_neg, "bad hands, blurry")))

    def test_o_padrao_e_anime_sem_explicito(self):
        pos, neg = prompts.montar(pedido())
        for tag in ("source_anime", "rating_safe"):
            self.assertIn(tag, prompts.separar_tags(pos))
        for tag in ("source_furry", "3d", "rating_explicit", "rating_questionable"):
            self.assertIn(tag, prompts.separar_tags(neg))

    def test_tudo_desligado(self):
        pos, neg = prompts.montar(pedido(qualidade=False, estilo=None, bloquear_explicito=False))
        self.assertEqual((pos, neg), ("1girl", ""))

    def test_os_estilos_do_contrato_tem_tags(self):
        self.assertEqual(set(prompts.ESTILOS), set(contrato.ESTILOS))

    def test_loras_da_ficha_e_do_pedido(self):
        r = prompts.juntar_loras([{"nome": "a", "peso": 1.0}, {"nome": "b", "peso": 0.5}],
                                 [{"nome": "b", "peso": 0.8}, {"nome": "c", "peso": 1.0}])
        self.assertEqual(r, [{"nome": "a", "peso": 1.0}, {"nome": "b", "peso": 0.8}, {"nome": "c", "peso": 1.0}])


class Pesos(unittest.TestCase):
    def assertPesos(self, texto, esperado):
        achado = [(t, round(p, 4)) for t, p in prompts.pesos(texto)]
        self.assertEqual(achado, [(t, round(p, 4)) for t, p in esperado])

    def test_sem_peso(self):
        self.assertPesos("a, b", [("a, b", 1.0)])

    def test_numero_parenteses_e_colchetes(self):
        self.assertPesos("a, (b:1.3), c", [("a, ", 1.0), ("b", 1.3), (", c", 1.0)])
        self.assertPesos("(b)", [("b", 1.1)])
        self.assertPesos("((b))", [("b", 1.21)])
        self.assertPesos("[b]", [("b", 1 / 1.1)])
        self.assertPesos("(a, (b:2):0.5)", [("a, ", 0.5), ("b", 1.0)])

    def test_parentese_escapado_e_texto(self):
        self.assertPesos(r"artist \(style\)", [("artist (style)", 1.0)])

    def test_aberto_sem_fechar_vale_1_1(self):
        self.assertPesos("(b", [("b", 1.1)])

    def test_para_compel(self):
        self.assertEqual(prompts.para_compel("a, (b:1.3), c"), "a, (b)1.3, c")
        self.assertEqual(prompts.para_compel("(red eyes, smile:1.2)"), "(red eyes, smile)1.2")
        self.assertEqual(prompts.para_compel(r"artist \(style\)"), r"artist \(style\)")
        self.assertEqual(prompts.para_compel("score_9, 1girl"), "score_9, 1girl")
        self.assertEqual(prompts.para_compel(""), "")


class Fichas(unittest.TestCase):
    def test_o_exemplo_passa(self):
        f = fichas.ler_ficha(FICHA_EXEMPLO)
        self.assertEqual(f["versao_ficha"], 1)
        self.assertTrue(f["tags"])

    def test_gravar_e_ler_da_o_mesmo(self):
        ficha = {"nome": "Ana \"A\" Ü", "tags": "1girl, \\(x\\)\nlinha", "negativo": "", "notas": "ç",
                 "loras": [{"nome": "estilo/v1", "peso": 0.75}]}
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "ana.toml")
            fichas.gravar_ficha(ficha, caminho)
            self.assertEqual(fichas.ler_ficha(caminho), fichas.conferir_ficha(ficha))
            with self.assertRaises(contrato.ErroPedido):
                fichas.gravar_ficha(ficha, caminho)
            fichas.gravar_ficha(dict(ficha, notas="outra"), caminho, sobrescrever=True)
            self.assertEqual(fichas.ler_ficha(caminho)["notas"], "outra")
            self.assertEqual(fichas.listar(pasta), ["ana"])

    def test_recusas(self):
        for ruim, trecho in (({}, "'nome'"), ({"nome": "a", "cabelo": "x"}, "'cabelo'"),
                             ({"nome": "a", "versao_ficha": 2}, "versao_ficha"), ({"nome": "a", "tags": 3}, "'tags'"),
                             ({"nome": "a", "loras": [{"nome": "x", "peso": 9}]}, "'peso'")):
            with self.assertRaises(contrato.ErroPedido) as c:
                fichas.conferir_ficha(ruim)
            self.assertIn(trecho, str(c.exception))

    def test_toml_invalido(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "ruim.toml")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write("nome = \n")
            with self.assertRaises(contrato.ErroPedido) as c:
                fichas.ler_ficha(caminho)
            self.assertIn("não é um TOML válido", str(c.exception))

    def test_resolver_e_nome_de_arquivo(self):
        self.assertEqual(fichas.resolver("aiko", "/p"), os.path.join("/p", "aiko.toml"))
        self.assertTrue(fichas.resolver("x/aiko.toml", "/p").endswith(os.path.join("x", "aiko.toml")))
        self.assertEqual(fichas.nome_de_arquivo("Aikô Hoshino!"), "aiko_hoshino")
        with self.assertRaises(contrato.ErroPedido):
            fichas.nome_de_arquivo("!!!")


class Loras(unittest.TestCase):
    def test_ler_lista(self):
        self.assertEqual(loras.ler_lista("a:0.5\nb, c:-1"),
                         [{"nome": "a", "peso": 0.5}, {"nome": "b", "peso": 1.0}, {"nome": "c", "peso": -1.0}])
        self.assertEqual(loras.ler_lista(""), [])
        for ruim in ("a:muito", "a:9", ":1"):
            with self.assertRaises(contrato.ErroPedido):
                loras.ler_lista(ruim)

    def test_arquivo_e_listar(self):
        with tempfile.TemporaryDirectory() as pasta:
            os.makedirs(os.path.join(pasta, "estilos"))
            for n in ("a.safetensors", os.path.join("estilos", "b.safetensors"), "c.txt"):
                open(os.path.join(pasta, n), "w").close()
            self.assertEqual(loras.listar(pasta), ["a", "estilos/b"])
            self.assertEqual(loras.arquivo(pasta, "a"), os.path.join(pasta, "a.safetensors"))
            self.assertEqual(loras.arquivo(pasta, "a.safetensors"), os.path.join(pasta, "a.safetensors"))
            self.assertIsNone(loras.arquivo(pasta, "c.txt"))
            self.assertIsNone(loras.arquivo(pasta, "nao"))
        self.assertEqual(loras.listar("/nao/existe"), [])

    def test_nome_adaptador(self):
        self.assertEqual(loras.nome_adaptador("estilos/b.v2"), "lora_estilos_b_v2")


class Metadados(unittest.TestCase):
    def test_texto_parametros(self):
        p = pedido(seed=42, hires=True)
        texto = metadados.texto_parametros(p, "score_9, 1girl", "score_4", "pony", [{"nome": "x", "peso": 0.8}])
        linhas = texto.split("\n")
        self.assertEqual(linhas[0], "score_9, 1girl <lora:x:0.8>")
        self.assertEqual(linhas[1], "Negative prompt: score_4")
        for trecho in ("Steps: 25", "Sampler: Euler a", "CFG scale: 7", "Seed: 42", "Size: 1024x1024",
                       "Model: pony", "Hires upscale: 1.5", "Denoising strength: 0.4"):
            self.assertIn(trecho, linhas[2])

    def test_o_pedido_volta_do_bloco(self):
        p = pedido(seed=7, rosto=True, loras=[{"nome": "x", "peso": 0.5}])
        bloco = metadados.bloco_aigen(p, "pos", "neg", p["loras"])
        self.assertEqual(metadados.pedido_do_png({"aigen": bloco, "parameters": "..."}), p)

    def test_png_de_fora_e_recusado(self):
        for textos in ({}, {"aigen": "{"}, {"aigen": json.dumps({"versao_formato": 9, "pedido": {}})}):
            with self.assertRaises(contrato.ErroPedido):
                metadados.pedido_do_png(textos)


class Config(unittest.TestCase):
    def test_padroes_local_e_variavel(self):
        with tempfile.TemporaryDirectory() as raiz:
            with open(os.path.join(raiz, "config.ini"), "w", encoding="utf-8") as f:
                f.write("[modelos]\ncheckpoint =\n[web]\nporta = 7860\n")
            c = config.ler(raiz, {})
            self.assertEqual(c.checkpoint, "")
            self.assertEqual(c.pasta_loras, os.path.join(raiz, "models", "loras"))
            with open(os.path.join(raiz, "config.local.ini"), "w", encoding="utf-8") as f:
                f.write("[modelos]\ncheckpoint = models/pony.safetensors\n")
            self.assertEqual(config.ler(raiz, {}).checkpoint, os.path.join(raiz, "models", "pony.safetensors"))
            c = config.ler(raiz, {"AIGEN_CHECKPOINT": "/outro/x.safetensors", "AIGEN_PORTA": "8000"})
            self.assertEqual((c.checkpoint, c.porta), ("/outro/x.safetensors", 8000))
            with self.assertRaises(contrato.ErroPedido):
                config.ler(raiz, {"AIGEN_PORTA": "porta"})

    def test_o_config_ini_do_repositorio_nao_tem_caminho_de_maquina(self):
        c = config.ler(RAIZ, {})
        self.assertTrue(c.pasta_fichas.startswith(RAIZ))
        if not os.path.isfile(os.path.join(RAIZ, "config.local.ini")):
            self.assertEqual(c.checkpoint, "")


@etapas.declarar(grava=("ficha", "rel"))
def _pedido(t):
    pass


@etapas.declarar(le=("ficha",), grava=("positivo",))
def _prompt(t):
    pass


def _sem_declaracao(t):
    pass


class Sequencia(unittest.TestCase):
    def test_a_sequencia_certa_passa(self):
        etapas.conferir((_pedido, _prompt))

    def test_ler_antes_de_quem_grava_e_recusado(self):
        with self.assertRaises(etapas.ErroSequencia) as c:
            etapas.conferir((_prompt, _pedido))
        self.assertIn("'test_puros._prompt' lê 'ficha'", str(c.exception))

    def test_a_etapa_sem_declaracao_e_recusada(self):
        with self.assertRaises(etapas.ErroSequencia) as c:
            etapas.conferir((_pedido, _sem_declaracao))
        self.assertIn("não declara", str(c.exception))

    def test_as_sequencias_de_cada_modo(self):
        nomes = lambda p: [etapas.nome(f) for f in gerar.sequencia(p)]  # noqa: E731
        base = ["gerar.conferir_pedido", "prompts.etapa", "modelo.etapa", "loras.etapa", "geracao.etapa"]
        self.assertEqual(nomes(pedido()), base + ["saida.etapa"])
        self.assertEqual(nomes(pedido(hires=True)), base + ["hires.etapa", "saida.etapa"])
        self.assertEqual(nomes(pedido(rosto=True, hires=True)), base + ["hires.etapa", "rosto.etapa", "saida.etapa"])

    def test_tirar_a_conferencia_do_pedido_e_recusado(self):
        with self.assertRaises(etapas.ErroSequencia):
            etapas.conferir(gerar.sequencia(pedido())[1:])


class Rosto(unittest.TestCase):
    def test_maiores(self):
        caixas = [(0, 0, 10, 10), (5, 5, 30, 30), (50, 0, 20, 20), (0, 50, 20, 20)]
        self.assertEqual(rosto.maiores(caixas, 3), [(5, 5, 30, 30), (50, 0, 20, 20), (0, 50, 20, 20)])

    def test_caixa_expandida_fica_dentro_da_imagem(self):
        self.assertEqual(rosto.caixa_expandida((100, 100, 50, 50), 0.5, 1024, 1024), (75, 75, 100, 100))
        self.assertEqual(rosto.caixa_expandida((0, 0, 50, 50), 0.5, 1024, 1024), (0, 0, 100, 100))
        self.assertEqual(rosto.caixa_expandida((1000, 1000, 24, 24), 1, 1024, 1024), (952, 952, 72, 72))
        self.assertEqual(rosto.caixa_expandida((0, 0, 600, 600), 1, 1024, 768), (0, 0, 768, 768))

    def test_caixa_no_recorte(self):
        self.assertEqual(rosto.caixa_no_recorte((100, 100, 50, 50), (75, 75, 100, 100), 1000),
                         (250, 250, 500, 500))


class Vae(unittest.TestCase):
    def test_os_tamanhos_do_pony_nao_usam_blocos(self):
        for largura, altura in ((1024, 1024), (832, 1216), (1216, 832), (896, 1152), (768, 1344), (1344, 768)):
            self.assertFalse(modelo.usa_blocos(largura, altura), (largura, altura))

    def test_os_grandes_usam(self):
        for largura, altura in ((1536, 1536), (2048, 2048), (1248, 1824)):
            self.assertTrue(modelo.usa_blocos(largura, altura), (largura, altura))

    def test_preparar_vae_liga_e_desliga(self):
        chamadas = []

        class Vae:
            def enable_tiling(self):
                chamadas.append("liga")

            def disable_tiling(self):
                chamadas.append("desliga")

        class Pipe:
            vae = Vae()
        modelo.preparar_vae(Pipe(), 2048, 2048)
        modelo.preparar_vae(Pipe(), 1024, 1024)
        self.assertEqual(chamadas, ["liga", "desliga"])


class Contas(unittest.TestCase):
    def test_passos_do_hires(self):
        self.assertEqual(hires.passos_totais(15, 0.4), 38)
        self.assertEqual(int(hires.passos_totais(15, 0.4) * 0.4), 15)
        self.assertEqual(hires.passos_totais(20, 1.0), 20)

    def test_caminhos_da_saida(self):
        self.assertEqual(saida.caminhos("/x/a.png", 1), ["/x/a.png"])
        self.assertEqual(saida.caminhos("/x/a.png", 2), ["/x/a_001.png", "/x/a_002.png"])
        self.assertEqual(saida.relatorio_de("/x/a.png"), "/x/a.aigen.json")

    def test_saida_que_existe_e_recusada(self):
        with tempfile.TemporaryDirectory() as pasta:
            png = os.path.join(pasta, "a.png")
            saida.conferir_saidas([png])
            open(saida.relatorio_de(png), "w").close()
            with self.assertRaises(contrato.ErroPedido):
                saida.conferir_saidas([png])
            with self.assertRaises(contrato.ErroPedido):
                saida.conferir_saidas([os.path.join(pasta, "b.jpg")])


class LinhaDeComando(unittest.TestCase):
    def test_estilo_e_explicito_pelas_opcoes(self):
        p = gerar.pedido_dos_args(gerar.ler_args(["x.png", "--prompt", "1girl"]))
        self.assertEqual((p["estilo"], p["bloquear_explicito"]), ("anime", True))
        p = gerar.pedido_dos_args(gerar.ler_args(["x.png", "--prompt", "1girl", "--estilo", "nenhum",
                                                  "--permitir-explicito"]))
        self.assertEqual((p["estilo"], p["bloquear_explicito"]), (None, False))

    def test_opcoes_de_hires_ligam_o_hires(self):
        p = gerar.pedido_dos_args(gerar.ler_args(["x.png", "--prompt", "1girl", "--hires-escala", "2"]))
        self.assertEqual(p["hires"]["escala"], 2.0)
        self.assertIsNone(p["rosto"])


class Tela(unittest.TestCase):
    def test_ida_e_volta(self):
        p = pedido(ficha="aiko", seed=3, hires={"escala": 2.0}, loras=[{"nome": "x", "peso": 0.5}], estilo=None,
                   bloquear_explicito=False)
        v = web.tela_do_pedido(p)
        self.assertEqual(set(v), set(web.CAMPOS))
        self.assertEqual(web.pedido_da_tela(v), p)

    def test_desligados_e_sem_ficha(self):
        v = web.tela_do_pedido(pedido())
        self.assertEqual((v["ficha"], v["hires"], v["rosto"]), (web.NENHUMA, False, False))
        self.assertEqual((v["estilo"], v["bloquear_explicito"]), ("anime", True))
        self.assertEqual(web.pedido_da_tela(v), pedido())

    def test_o_registro_de_falhas_acrescenta(self):
        with tempfile.TemporaryDirectory() as pasta:
            agora = datetime.datetime(2026, 1, 2, 3, 4, 5)
            caminho = web.registrar_falha(pasta, {"prompt": "1girl"}, "Traceback ...\nErro: x\n", agora)
            web.registrar_falha(pasta, {"prompt": "2"}, "Outro", agora)
            with open(caminho, encoding="utf-8") as f:
                texto = f.read()
            self.assertEqual(os.path.basename(caminho), web.REGISTRO)
            self.assertEqual(texto.count("=== 2026-01-02T03:04:05"), 2)
            self.assertIn('pedido: {"prompt": "1girl"}', texto)
            self.assertIn("Erro: x", texto)

    def test_caminho_novo_nao_repete(self):
        agora = datetime.datetime(2026, 1, 2, 3, 4, 5)
        with tempfile.TemporaryDirectory() as pasta:
            primeiro = web.caminho_novo(pasta, agora)
            self.assertEqual(primeiro, os.path.join(pasta, "2026-01-02", "030405.png"))
            os.makedirs(os.path.dirname(primeiro))
            open(primeiro, "w").close()
            self.assertEqual(web.caminho_novo(pasta, agora), os.path.join(pasta, "2026-01-02", "030405_2.png"))


class Exemplos(unittest.TestCase):
    def test_o_pyproject_le(self):
        with open(os.path.join(RAIZ, "pyproject.toml"), "rb") as f:
            self.assertIn("dependencies", tomllib.load(f)["project"])


if __name__ == "__main__":
    resultado = unittest.main(argv=["test_puros"], exit=False, verbosity=2).result
    sys.stdout.flush()
    sys.exit(0 if resultado.wasSuccessful() else 1)
