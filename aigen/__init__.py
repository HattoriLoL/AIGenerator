"""AIGenerator: geração de imagens de personagens de anime com o Pony Diffusion XL (SDXL), pela linha de comando ou
por uma interface web local. O programa é o gerar.py; o contrato de entrada e saída, o contrato.py.

Nenhum módulo daqui importa o torch, o diffusers, o gradio ou outra biblioteca pesada no topo do arquivo: elas são
importadas dentro das funções que as usam, para que tudo importe (e os testes rodem) sem elas.
"""
VERSAO = "0.1.0"
