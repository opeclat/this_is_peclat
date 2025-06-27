# Clipboard Copier GUI

Uma interface gráfica simples para copiar variáveis para a área de transferência de forma sequencial.

## Funcionalidades

- Interface gráfica minimalista com botão circular
- Copia variáveis sequencialmente com duplo clique
- Janela de preview transparente
- Suporte a imagens locais para os estados do botão
- Janela sempre no topo e arrastável
- Fecha automaticamente quando todas as variáveis foram copiadas

## Uso

### Sintaxe Básica
```bash
python clipboard_copier_gui.py --variables arquivo_vars.json
```

### Com Imagens Personalizadas
```bash
python clipboard_copier_gui.py --variables arquivo_vars.json --normal-image normal.png --finished-image finished.png
```

### Parâmetros

- `--variables` ou `-v`: Caminho para o arquivo JSON com as variáveis (obrigatório)
- `--normal-image` ou `-n`: Caminho para a imagem do estado normal (opcional)
- `--finished-image` ou `-f`: Caminho para a imagem do estado finalizado (opcional)

### Formatos de Imagem Suportados
- PNG
- JPG/JPEG
- GIF
- BMP
- TIFF
- E outros formatos suportados pelo PIL

## Arquivo de Variáveis

O arquivo JSON deve conter uma lista de strings:

```json
[
    "Primeira variável para copiar",
    "Segunda variável com mais texto",
    "https://exemplo.com",
    "Outra variável qualquer"
]
```

Ou em formato de dicionário:

```json
{
    "variables": [
        "Primeira variável para copiar",
        "Segunda variável com mais texto",
        "https://exemplo.com",
        "Outra variável qualquer"
    ]
}
```

## Como Usar

1. **Preparar as imagens**: Coloque suas imagens na pasta do projeto
2. **Executar o programa**: Use o comando com os caminhos das imagens
3. **Copiar variáveis**: Dê duplo clique no botão para copiar cada variável
4. **Finalizar**: Quando todas as variáveis forem copiadas, o botão mudará para a imagem de "finalizado"
5. **Fechar**: Clique uma vez no botão vermelho para fechar o programa

## Exemplos

### Exemplo 1: Sem imagens (usa cores padrão)
```bash
python clipboard_copier_gui.py --variables my_vars.json
```

### Exemplo 2: Com imagens personalizadas
```bash
python clipboard_copier_gui.py --variables my_vars.json --normal-image icons/normal.png --finished-image icons/finished.png
```

### Exemplo 3: Apenas imagem normal (finalizado usa cor vermelha)
```bash
python clipboard_copier_gui.py --variables my_vars.json --normal-image button.png
```

## Dependências

- `tkinter` (incluído no Python)
- `pyperclip` (para operações de área de transferência)
- `PIL` (Pillow) (para processamento de imagens)

## Instalação das Dependências

```bash
pip install pyperclip pillow
```

## Características Técnicas

- Janela sempre no topo
- Sem decorações de janela (bordas, barra de título)
- Botão circular com máscara
- Redimensionamento automático de imagens
- Suporte a transparência
- Arquivo PID para controle de processo