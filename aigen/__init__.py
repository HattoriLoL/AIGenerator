"""AIGenerator: anime character image generation with Pony Diffusion XL (SDXL), from the command line or a local web
interface. The program is generate.py; the input and output contract is contract.py.

No module here imports torch, diffusers, gradio or another heavy library at the top of the file: they are imported
inside the functions that use them, so that everything imports (and the tests run) without them.
"""
VERSION = "0.1.0"
