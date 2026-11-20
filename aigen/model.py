"""The session: what stays loaded on the GPU from one request to the next (the SDXL pipeline, compel, the upscaler,
the face detector and the active LoRAs), and the stage that delivers the pipeline with the request's sampler.

torch and diffusers are only imported inside the functions (the module imports without them).
"""
import importlib.util

from aigen import contract, memory, stages

# the request's sampler: (diffusers class, extra options). The names are those of contract.SAMPLERS.
SCHEDULERS = {
    "euler_a": ("EulerAncestralDiscreteScheduler", {}),
    "euler": ("EulerDiscreteScheduler", {}),
    "dpmpp_2m": ("DPMSolverMultistepScheduler", {}),
    "dpmpp_2m_karras": ("DPMSolverMultistepScheduler", {"use_karras_sigmas": True}),
    "dpmpp_2m_sde_karras": ("DPMSolverMultistepScheduler", {"algorithm_type": "sde-dpmsolver++",
                                                             "use_karras_sigmas": True}),
    "ddim": ("DDIMScheduler", {}),
}
# the libraries the generation needs (the module name); a missing one is a request error, before anything is loaded
LIBRARIES = ("torch", "diffusers", "transformers", "compel", "PIL", "numpy")
HIRES_LIBRARIES = ("spandrel",)
FACE_LIBRARIES = ("cv2",)


def check_libraries(names):
    missing = [n for n in names if importlib.util.find_spec(n) is None]
    if missing:
        raise contract.RequestError("missing libraries (%s): install the environment with %s"
                                    % (", ".join(missing), contract.command("setup")))


def device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


# Above this (in pixels), the VAE decodes in tiles: whole and in fp32 (what diffusers does with the SDXL VAE), a large
# image does not fit on the GPU. Pony's ~1 megapixel sizes (1024×1024, 832×1216) stay below.
PIXELS_WITHOUT_TILING = int(1.25 * 1024 * 1024)


def uses_tiling(width, height):
    return width * height > PIXELS_WITHOUT_TILING


def prepare_vae(pipe, width, height):
    """Turns on the tiled VAE decoding for large images and turns it off for the others."""
    if uses_tiling(width, height):
        pipe.vae.enable_tiling()
    else:
        pipe.vae.disable_tiling()


def empty_cache():
    """Gives back to the GPU the memory torch kept and no longer uses (after a failure, for example)."""
    memory.free()


def generator(seed):
    """A torch.Generator on the GPU (or on the CPU, without a GPU) with the given seed."""
    import torch
    return torch.Generator(device()).manual_seed(int(seed))


def scheduler(name, configuration):
    import diffusers
    cls, extra = SCHEDULERS[name]
    return getattr(diffusers, cls).from_config(configuration, **extra)


class Session:
    """What is loaded once and serves several requests (the command line makes one; batch mode and the web interface,
    a single one)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.loaded_loras = ()
        self._pipe = self._path = self._scheduler_config = self._dtype = None
        self._compel = self._upscaler = self._detector = None

    @property
    def loaded(self):
        """Whether the checkpoint is loaded."""
        return self._pipe is not None

    def pipeline(self, sampler):
        """The text-to-image pipeline of the configured checkpoint, with the requested sampler and the VAE in the right
        type."""
        if self._pipe is None or self._path != self.cfg.checkpoint:
            self.release()
            self._load()
        self._pipe.scheduler = scheduler(sampler, self._scheduler_config)
        self.restore_vae()
        return self._pipe

    def restore_vae(self):
        """Puts the VAE back in the pipeline's type. diffusers moves the SDXL VAE to fp32 only to decode and moves it
        back afterwards; if the decode fails half-way (out of memory), it stays in fp32 and every following generation
        fails with "Input type (c10::Half) and bias type (float) should be the same"."""
        if self._pipe.vae.dtype != self._dtype:
            self._pipe.vae.to(dtype=self._dtype)

    def _load(self):
        import torch
        from diffusers import StableDiffusionXLPipeline
        dtype = torch.float16 if device() == "cuda" else torch.float32
        extra = {}
        if self.cfg.vae:
            from diffusers import AutoencoderKL
            extra["vae"] = AutoencoderKL.from_single_file(self.cfg.vae, torch_dtype=dtype)
        pipe = StableDiffusionXLPipeline.from_single_file(self.cfg.checkpoint, torch_dtype=dtype, **extra)
        pipe.to(device())
        pipe.set_progress_bar_config(disable=True)
        self._pipe, self._path, self._dtype = pipe, self.cfg.checkpoint, dtype
        self._scheduler_config = pipe.scheduler.config
        memory.trim()  # the checkpoint went through RAM on its way to the GPU

    def derived(self, cls):
        """A diffusers pipeline (img2img, inpaint) that uses the same weights already loaded, with the current
        sampler."""
        import diffusers
        pipe = getattr(diffusers, cls).from_pipe(self._pipe)
        pipe.set_progress_bar_config(disable=True)
        return pipe

    def compel(self):
        """The compel of the loaded pipeline: the two SDXL text encoders (the penultimate layer, which SDXL uses), with
        weights and long prompts. CompelForSDXL encodes the positive and the negative together and evens out their
        lengths; Compel with the two lists of encoders fails to even them out ('EmbeddingsProviderMulti' has no
        'empty_z') when one prompt goes past 77 tokens and the other does not."""
        if self._compel is None:
            from compel import CompelForSDXL
            self._compel = CompelForSDXL(self._pipe)
        return self._compel

    def upscaler(self):
        """The upscaler model (the file in the config, loaded by spandrel), on the GPU."""
        if self._upscaler is None:
            from spandrel import ModelLoader
            self._upscaler = ModelLoader().load_from_file(self.cfg.upscaler).to(device()).eval()
        return self._upscaler

    def detector(self):
        """The face detector (an OpenCV cascade, the file in the config)."""
        if self._detector is None:
            import cv2
            detector = cv2.CascadeClassifier(self.cfg.face_detector)
            if detector.empty():
                raise RuntimeError("the face detector did not load: " + self.cfg.face_detector)
            self._detector = detector
        return self._detector

    def release(self):
        """Lets go of the model, compel and the upscaler and gives their memory back, on the GPU and in RAM (when
        switching checkpoints, and when the web interface stays idle)."""
        self._pipe = self._path = self._scheduler_config = self._dtype = None
        self._compel = self._upscaler = None
        self.loaded_loras = ()
        memory.free()


@stages.declare(reads=("request", "session"), writes=("pipe",))
def stage(t):
    """Loads the checkpoint (once per session) and sets the request's sampler on it."""
    t.pipe = t.session.pipeline(t.request["sampler"])
