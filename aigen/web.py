"""A interface web (Gradio): uma camada sobre o gerar.rodar, que escuta só em 127.0.0.1.

    bin/aigen_web.sh [--porta N]

Abas: Gerar (o pedido, as fichas, os LoRAs, o hires fix e a correção de rosto), Fichas (criar e editar), Galeria (as
imagens da pasta de saída) e Ler PNG (refaz o pedido a partir de uma imagem do AIGenerator). Uma geração por vez.
Cada falha vai, com o erro completo e o pedido, para o registro <pasta de saída>/aigen-web.log.
O gradio e o PIL só são importados dentro das funções.
"""
import datetime
import json
import os
import sys
import threading
import traceback

from aigen import VERSAO, config, contrato, fichas, gerar, loras, metadados, modelo

NENHUMA = "(nenhuma)"
SEM_ESTILO = "nenhum"
CAMPOS = ("ficha", "prompt", "negativo", "qualidade", "estilo", "bloquear_explicito", "largura", "altura", "passos",
          "cfg", "amostrador", "seed", "quantidade", "loras", "hires", "hires_escala", "hires_forca", "hires_passos", "hires_upscaler", "rosto",
          "rosto_forca", "rosto_passos", "rosto_margem", "rosto_prompt", "rosto_max")
GALERIA_MAX = 60
REGISTRO = "aigen-web.log"


def registrar_falha(pasta, pedido, texto_erro, agora=None):
    """Acrescenta ao registro da pasta de saída a hora, o pedido e o erro completo (o traceback); devolve o caminho."""
    agora = agora or datetime.datetime.now()
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, REGISTRO)
    with open(caminho, "a", encoding="utf-8") as f:
        f.write("=== %s\npedido: %s\n%s\n" % (agora.isoformat(timespec="seconds"),
                                            json.dumps(pedido, ensure_ascii=False, sort_keys=True), texto_erro.rstrip()))
    return caminho


def pedido_da_tela(v):
    """O pedido normalizado a partir dos valores da tela ({campo de CAMPOS: valor})."""
    pedido = {"prompt": v["prompt"] or "", "negativo": v["negativo"] or "",
              "ficha": None if v["ficha"] in (None, "", NENHUMA) else v["ficha"], "qualidade": bool(v["qualidade"]),
              "estilo": None if v["estilo"] in (None, "", SEM_ESTILO) else v["estilo"],
              "bloquear_explicito": bool(v["bloquear_explicito"]), "largura": int(v["largura"]),
              "altura": int(v["altura"]), "passos": int(v["passos"]),
              "cfg": float(v["cfg"]), "amostrador": v["amostrador"], "seed": int(v["seed"]),
              "quantidade": int(v["quantidade"]), "loras": loras.ler_lista(v["loras"])}
    if v["hires"]:
        pedido["hires"] = {"escala": float(v["hires_escala"]), "forca": float(v["hires_forca"]),
                           "passos": int(v["hires_passos"]), "upscaler": v["hires_upscaler"]}
    if v["rosto"]:
        pedido["rosto"] = {"forca": float(v["rosto_forca"]), "passos": int(v["rosto_passos"]),
                           "margem": float(v["rosto_margem"]), "prompt": v["rosto_prompt"] or "",
                           "max_rostos": int(v["rosto_max"])}
    return contrato.normalizar(pedido, "o pedido da tela")


def tela_do_pedido(pedido):
    """Os valores da tela ({campo: valor}) de um pedido normalizado (o contrário de pedido_da_tela)."""
    h = pedido["hires"] or {k: c[2] for k, c in contrato.CAMPOS_HIRES.items()}
    r = pedido["rosto"] or {k: c[2] for k, c in contrato.CAMPOS_ROSTO.items()}
    v = {k: pedido[k] for k in ("prompt", "negativo", "qualidade", "largura", "altura", "passos", "cfg", "amostrador",
                                "seed", "quantidade")}
    v.update(estilo=pedido["estilo"] or SEM_ESTILO, bloquear_explicito=pedido["bloquear_explicito"])
    v.update(ficha=pedido["ficha"] or NENHUMA, hires=bool(pedido["hires"]), rosto=bool(pedido["rosto"]),
             loras="\n".join("%s:%g" % (l["nome"], l["peso"]) for l in pedido["loras"]))
    v.update({"hires_" + k: h[k] for k in ("escala", "forca", "passos", "upscaler")})
    v.update({"rosto_" + k: r[k] for k in ("forca", "passos", "margem", "prompt")}, rosto_max=r["max_rostos"])
    return v


def caminho_novo(pasta, agora):
    """pasta/AAAA-MM-DD/HHMMSS.png, com _2, _3 ... se já existe um PNG (ou uma série x_001.png) com esse nome."""
    dia = os.path.join(pasta, agora.strftime("%Y-%m-%d"))
    base = os.path.join(dia, agora.strftime("%H%M%S"))
    n, candidato = 1, base
    while any(os.path.exists(candidato + s) for s in (".png", "_001.png")):
        n += 1
        candidato = "%s_%d" % (base, n)
    return candidato + ".png"


def recentes(pasta, n=GALERIA_MAX):
    """Os n PNGs mais novos da pasta de saída (e das subpastas)."""
    achados = []
    for dirpath, _, nomes in os.walk(pasta):
        achados += [os.path.join(dirpath, x) for x in nomes if x.lower().endswith(".png")]
    return sorted(achados, key=os.path.getmtime, reverse=True)[:n]


def textos_do_png(caminho):
    from PIL import Image
    with Image.open(caminho) as im:
        return dict(getattr(im, "text", {}) or im.info)


class App:
    """O estado da interface: a configuração, a sessão (o modelo carregado) e a trava de uma geração por vez."""

    def __init__(self, cfg):
        self.cfg, self.sessao, self.trava = cfg, modelo.Sessao(cfg), threading.Lock()

    def fichas(self):
        return [NENHUMA] + fichas.listar(self.cfg.pasta_fichas)

    def gerar(self, *valores):
        import gradio as gr
        try:
            pedido = pedido_da_tela(dict(zip(CAMPOS, valores)))
        except contrato.ErroPedido as e:
            raise gr.Error(str(e))
        if not self.trava.acquire(blocking=False):
            raise gr.Error("já há uma geração rodando; espere ela terminar")
        try:
            feitos = gerar.rodar(pedido, caminho_novo(self.cfg.pasta_saida, datetime.datetime.now()), self.sessao,
                                 self.cfg)
        except contrato.ErroPedido as e:
            raise gr.Error(str(e))
        except Exception as e:  # o modelo não carregou, faltou memória na placa, ...
            texto = traceback.format_exc()
            print(texto, file=sys.stderr)
            registro = registrar_falha(self.cfg.pasta_saida, pedido, texto)
            modelo.esvaziar_cache()  # depois de faltar memória, a próxima geração começa com a placa limpa
            raise gr.Error("a geração falhou: %s: %s (detalhes em %s)" % (type(e).__name__, e, registro))
        finally:
            self.trava.release()
        pngs = [png for png, _ in feitos]
        return pngs, "Gravado: " + ", ".join("`%s`" % os.path.relpath(p, self.cfg.pasta_saida) for p in pngs)

    def ler_png(self, caminho):
        import gradio as gr
        if not caminho:
            raise gr.Error("escolha um PNG")
        try:
            v = tela_do_pedido(metadados.pedido_do_png(textos_do_png(caminho)))
        except contrato.ErroPedido as e:
            raise gr.Error(str(e))
        except OSError as e:
            raise gr.Error("o arquivo não abriu como PNG: %s" % e)
        return [v[c] for c in CAMPOS]

    def abrir_ficha(self, nome):
        import gradio as gr
        if nome in (None, "", NENHUMA):
            return "", "", "", "", ""
        try:
            f = fichas.ler_ficha(fichas.resolver(nome, self.cfg.pasta_fichas))
        except contrato.ErroPedido as e:
            raise gr.Error(str(e))
        return (f["nome"], f["tags"], f["negativo"], "\n".join("%s:%g" % (l["nome"], l["peso"]) for l in f["loras"]),
                f["notas"])

    def salvar_ficha(self, nome, tags, negativo, texto_loras, notas, sobrescrever):
        import gradio as gr
        try:
            ficha = {"nome": nome or "", "tags": tags or "", "negativo": negativo or "", "notas": notas or "",
                     "loras": loras.ler_lista(texto_loras)}
            caminho = os.path.join(self.cfg.pasta_fichas, fichas.nome_de_arquivo(nome or "") + ".toml")
            fichas.gravar_ficha(ficha, caminho, sobrescrever=bool(sobrescrever))
        except contrato.ErroPedido as e:
            raise gr.Error(str(e))
        escolhas = self.fichas()
        return ("Ficha gravada: `%s`" % os.path.basename(caminho), gr.update(choices=escolhas),
                gr.update(choices=escolhas))


def _aba_gerar(gr, app, c):
    with gr.Row():
        with gr.Column(scale=3):
            c["ficha"] = gr.Dropdown(app.fichas(), value=NENHUMA, label="Ficha de personagem", allow_custom_value=True)
            c["prompt"] = gr.Textbox(label="Prompt (tags da cena)", lines=4)
            c["negativo"] = gr.Textbox(label="Negativo", lines=2)
            with gr.Row():
                c["qualidade"] = gr.Checkbox(True, label="Tags de qualidade do Pony (score_9, score_8_up, ...)")
                c["bloquear_explicito"] = gr.Checkbox(True, label="Desativar classificações explícitas (rating_safe)")
                c["estilo"] = gr.Dropdown(list(contrato.ESTILOS) + [SEM_ESTILO], value="anime", label="Estilo")
            with gr.Row():
                c["largura"] = gr.Slider(contrato.LADO_MIN, contrato.LADO_MAX, 1024, step=8, label="Largura")
                c["altura"] = gr.Slider(contrato.LADO_MIN, contrato.LADO_MAX, 1024, step=8, label="Altura")
            with gr.Row():
                c["passos"] = gr.Slider(1, 150, 25, step=1, label="Passos")
                c["cfg"] = gr.Slider(1, 30, 7, step=0.5, label="CFG")
            with gr.Row():
                c["amostrador"] = gr.Dropdown(list(contrato.AMOSTRADORES), value="euler_a", label="Amostrador")
                c["seed"] = gr.Number(-1, precision=0, label="Seed (-1 sorteia)")
                c["quantidade"] = gr.Slider(1, 16, 1, step=1, label="Quantidade")
            c["loras"] = gr.Textbox(label="LoRAs (um por linha, nome:peso)", lines=2,
                                    info="Na pasta: " + (", ".join(loras.listar(app.cfg.pasta_loras)) or "nenhum"))
            _extras(gr, c)
            botao = gr.Button("Gerar", variant="primary")
        with gr.Column(scale=2):
            resultado = gr.Gallery(label="Resultado", columns=2, height="auto")
            aviso = gr.Markdown()
    return botao, resultado, aviso


def _extras(gr, c):
    with gr.Accordion("Hires fix (desligado por padrão)", open=False):
        c["hires"] = gr.Checkbox(False, label="Ligar")
        with gr.Row():
            c["hires_escala"] = gr.Slider(1.05, 4, 1.5, step=0.05, label="Escala")
            c["hires_forca"] = gr.Slider(0.05, 1, 0.4, step=0.05, label="Força")
            c["hires_passos"] = gr.Slider(1, 150, 15, step=1, label="Passos")
        c["hires_upscaler"] = gr.Radio(list(contrato.UPSCALERS), value="modelo", label="Upscaler")
    with gr.Accordion("Correção de rosto (desligada por padrão)", open=False):
        c["rosto"] = gr.Checkbox(False, label="Ligar")
        with gr.Row():
            c["rosto_forca"] = gr.Slider(0.05, 1, 0.4, step=0.05, label="Força")
            c["rosto_passos"] = gr.Slider(1, 150, 20, step=1, label="Passos")
            c["rosto_margem"] = gr.Slider(0, 2, 0.3, step=0.05, label="Margem")
            c["rosto_max"] = gr.Slider(1, 16, 4, step=1, label="Máximo de rostos")
        c["rosto_prompt"] = gr.Textbox(label="Tags a mais para o rosto")


def _aba_fichas(gr, app):
    escolha = gr.Dropdown(app.fichas(), value=NENHUMA, label="Abrir uma ficha")
    nome = gr.Textbox(label="Nome do personagem")
    tags = gr.Textbox(label="Tags (o que o descreve: cabelo, olhos, roupa)", lines=3)
    negativo = gr.Textbox(label="Negativo", lines=2)
    texto_loras = gr.Textbox(label="LoRAs (um por linha, nome:peso)", lines=2)
    notas = gr.Textbox(label="Notas", lines=2)
    sobrescrever = gr.Checkbox(False, label="Sobrescrever se já existir")
    salvar = gr.Button("Salvar ficha")
    aviso = gr.Markdown()
    escolha.change(app.abrir_ficha, escolha, [nome, tags, negativo, texto_loras, notas])
    return escolha, salvar, [nome, tags, negativo, texto_loras, notas, sobrescrever], aviso


def criar(app):
    """Monta a interface (gr.Blocks) da App."""
    import gradio as gr
    c = {}
    with gr.Blocks(title="AIGenerator") as tela:
        gr.Markdown("# AIGenerator\nPony Diffusion XL · versão %s" % VERSAO)
        with gr.Tab("Gerar"):
            botao, resultado, aviso = _aba_gerar(gr, app, c)
        with gr.Tab("Fichas"):
            escolha, salvar, entradas_ficha, aviso_ficha = _aba_fichas(gr, app)
        with gr.Tab("Galeria"):
            atualizar = gr.Button("Atualizar")
            galeria = gr.Gallery(label="Pasta de saída", columns=4, height="auto")
        with gr.Tab("Ler PNG"):
            arquivo = gr.File(label="Um PNG do AIGenerator", file_types=[".png"], type="filepath")
            gr.Markdown("O pedido guardado no PNG vai para a aba Gerar.")
        entradas = [c[k] for k in CAMPOS]
        botao.click(app.gerar, entradas, [resultado, aviso], concurrency_limit=1)
        salvar.click(app.salvar_ficha, entradas_ficha, [aviso_ficha, c["ficha"], escolha])
        atualizar.click(lambda: recentes(app.cfg.pasta_saida), None, galeria)
        arquivo.upload(app.ler_png, arquivo, entradas)
    return tela


def principal(argv=None):
    p = gerar._Opcoes(prog=contrato.comando("aigen_web"), description="A interface web do AIGenerator.")
    p.add_argument("--porta", type=int, help="a porta (padrão: a do config, 7860)")
    p.add_argument("--abrir", action="store_true", help="abre a interface no navegador quando ela estiver pronta")
    a = p.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        cfg = config.ler()
        modelo.conferir_bibliotecas(modelo.BIBLIOTECAS + ("gradio",))
    except contrato.ErroPedido as e:
        print("ERRO: %s" % e, file=sys.stderr)
        return contrato.ERRO_PEDIDO
    porta = a.porta or cfg.porta
    print("AIGenerator %s em http://127.0.0.1:%d" % (VERSAO, porta))
    criar(App(cfg)).queue().launch(server_name="127.0.0.1", server_port=porta, inbrowser=a.abrir)
    return contrato.OK


if __name__ == "__main__":
    sys.exit(principal())
