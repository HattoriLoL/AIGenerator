"""A sessão: o que fica carregado na placa entre um pedido e outro (o pipeline do SDXL, o compel, o upscaler, o
detector de rosto e os LoRAs ligados), e a etapa que entrega o pipeline com o amostrador do pedido.

O torch e o diffusers só são importados dentro das funções (o módulo importa sem eles).
"""
import importlib.util

from aigen import contrato, etapas

# amostrador do pedido: (classe do diffusers, opções a mais). Os nomes são os de contrato.AMOSTRADORES.
AGENDADORES = {
    "euler_a": ("EulerAncestralDiscreteScheduler", {}),
    "euler": ("EulerDiscreteScheduler", {}),
    "dpmpp_2m": ("DPMSolverMultistepScheduler", {}),
    "dpmpp_2m_karras": ("DPMSolverMultistepScheduler", {"use_karras_sigmas": True}),
    "dpmpp_2m_sde_karras": ("DPMSolverMultistepScheduler", {"algorithm_type": "sde-dpmsolver++",
                                                             "use_karras_sigmas": True}),
    "ddim": ("DDIMScheduler", {}),
}
# as bibliotecas que a geração precisa (o nome do módulo); a falta de uma é um erro do pedido, antes de carregar nada
BIBLIOTECAS = ("torch", "diffusers", "transformers", "compel", "PIL", "numpy")
BIBLIOTECAS_HIRES = ("spandrel",)
BIBLIOTECAS_ROSTO = ("cv2",)


def conferir_bibliotecas(nomes):
    faltam = [n for n in nomes if importlib.util.find_spec(n) is None]
    if faltam:
        raise contrato.ErroPedido("faltam bibliotecas (%s): instale o ambiente com %s"
                                  % (", ".join(faltam), contrato.comando("instalar")))


def dispositivo():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


# Acima disso (em pixels), o VAE decodifica em blocos: inteira e em fp32 (o que o diffusers faz com o VAE do SDXL),
# uma imagem grande não cabe na placa. Os tamanhos de ~1 megapixel do Pony (1024×1024, 832×1216) ficam abaixo.
PIXELS_SEM_BLOCOS = int(1.25 * 1024 * 1024)


def usa_blocos(largura, altura):
    return largura * altura > PIXELS_SEM_BLOCOS


def preparar_vae(pipe, largura, altura):
    """Liga a decodificação em blocos do VAE para imagens grandes e desliga para as outras."""
    if usa_blocos(largura, altura):
        pipe.vae.enable_tiling()
    else:
        pipe.vae.disable_tiling()


def esvaziar_cache():
    """Devolve à placa a memória que o torch guardou e não usa mais (depois de uma falha, por exemplo)."""
    if importlib.util.find_spec("torch") is not None:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def gerador(seed):
    """Um torch.Generator na placa (ou na CPU, sem placa) com a seed dada."""
    import torch
    return torch.Generator(dispositivo()).manual_seed(int(seed))


def agendador(nome, configuracao):
    import diffusers
    classe, extra = AGENDADORES[nome]
    return getattr(diffusers, classe).from_config(configuracao, **extra)


class Sessao:
    """O que se carrega uma vez e serve a vários pedidos (a linha de comando faz uma; o lote e a tela, uma só)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.loras_carregadas = ()
        self._pipe = self._caminho = self._config_agendador = self._tipo = None
        self._compel = self._upscaler = self._detector = None

    def pipeline(self, amostrador):
        """O pipeline de texto para imagem do checkpoint configurado, com o amostrador pedido e o VAE no tipo certo."""
        if self._pipe is None or self._caminho != self.cfg.checkpoint:
            self.liberar()
            self._carregar()
        self._pipe.scheduler = agendador(amostrador, self._config_agendador)
        self.restaurar_vae()
        return self._pipe

    def restaurar_vae(self):
        """Devolve o VAE ao tipo do pipeline. O diffusers passa o VAE do SDXL para fp32 só para decodificar e o volta
        depois; se a decodificação falha no meio (faltou memória), ele fica em fp32 e toda geração seguinte falha com
        "Input type (c10::Half) and bias type (float) should be the same"."""
        if self._pipe.vae.dtype != self._tipo:
            self._pipe.vae.to(dtype=self._tipo)

    def _carregar(self):
        import torch
        from diffusers import StableDiffusionXLPipeline
        tipo = torch.float16 if dispositivo() == "cuda" else torch.float32
        extra = {}
        if self.cfg.vae:
            from diffusers import AutoencoderKL
            extra["vae"] = AutoencoderKL.from_single_file(self.cfg.vae, torch_dtype=tipo)
        pipe = StableDiffusionXLPipeline.from_single_file(self.cfg.checkpoint, torch_dtype=tipo, **extra)
        pipe.to(dispositivo())
        pipe.set_progress_bar_config(disable=True)
        self._pipe, self._caminho, self._tipo = pipe, self.cfg.checkpoint, tipo
        self._config_agendador = pipe.scheduler.config

    def derivado(self, classe):
        """Um pipeline do diffusers (img2img, inpaint) que usa os mesmos pesos já carregados, com o amostrador atual."""
        import diffusers
        pipe = getattr(diffusers, classe).from_pipe(self._pipe)
        pipe.set_progress_bar_config(disable=True)
        return pipe

    def compel(self):
        """O compel do pipeline carregado: os dois codificadores de texto do SDXL (a penúltima camada, que o SDXL usa),
        com pesos e prompts longos. O CompelForSDXL codifica o positivo e o negativo juntos e iguala os comprimentos;
        o Compel com as duas listas de codificadores falha ao igualar ('EmbeddingsProviderMulti' has no 'empty_z')
        quando um prompt passa de 77 tokens e o outro não."""
        if self._compel is None:
            from compel import CompelForSDXL
            self._compel = CompelForSDXL(self._pipe)
        return self._compel

    def upscaler(self):
        """O modelo de upscale (o arquivo do config, carregado pelo spandrel), na placa."""
        if self._upscaler is None:
            from spandrel import ModelLoader
            self._upscaler = ModelLoader().load_from_file(self.cfg.upscaler).to(dispositivo()).eval()
        return self._upscaler

    def detector(self):
        """O detector de rosto (uma cascata do OpenCV, o arquivo do config)."""
        if self._detector is None:
            import cv2
            detector = cv2.CascadeClassifier(self.cfg.detector_rosto)
            if detector.empty():
                raise RuntimeError("o detector de rosto não carregou: " + self.cfg.detector_rosto)
            self._detector = detector
        return self._detector

    def liberar(self):
        """Solta o que está na placa (ao trocar de checkpoint)."""
        self._pipe = self._caminho = self._config_agendador = self._tipo = None
        self._compel = self._upscaler = None
        self.loras_carregadas = ()
        esvaziar_cache()


@etapas.declarar(le=("pedido", "sessao"), grava=("pipe",))
def etapa(t):
    """Carrega o checkpoint (uma vez por sessão) e põe nele o amostrador do pedido."""
    t.pipe = t.sessao.pipeline(t.pedido["amostrador"])
