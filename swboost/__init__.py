"""SW Boost - camada de melhorias para o servidor do Social Wars.

O pacote nao altera nenhum arquivo do projeto original: ele importa o
`server.py` do jogo, pega o objeto Flask ja montado e troca/acrescenta
funcionalidades em cima dele. Isso significa que basta apagar estes arquivos
para voltar exatamente ao comportamento de fabrica.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
