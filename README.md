# LudusTier 🎮

**LudusTier** é um aplicativo moderno para Linux (desenvolvido em Python com **GTK 4** e **Libadwaita**) para criação e organização de tier lists de jogos.

---

## ✨ Principais Funcionalidades

- 🔍 **Busca e Capas Automáticas (SteamGridDB & Steam Store)**:
  - Pesquise jogos pelo nome e obtenha automaticamente a arte da capa em formato pôster vertical **600x900**.
  - Suporte a capas nos formatos **Banner / Header horizontal** e **Ícone quadrado**.
  - Cache local automático para carregamento instantâneo e offline.

- 🔍 **Controle de Zoom e Visualização (Semelhante ao Lutris)**:
  - 5 níveis de zoom ajustáveis para exibir cards compactos ou pôsteres detalhados.
  - Alternância entre estilos de capa:
    - 🎴 **Pôster Vertical (600x900)** (proporção 2:3)
    - 🖼️ **Banner / Header Horizontal** (proporção ~2.14:1)
    - 🔲 **Ícone Quadrado Compacto** (proporção 1:1)

- 🏷️ **Extração Automática de Metadados (Franquia, Empresa e Gêneros)**:
  - Ao adicionar um título (ex: *Resident Evil 4*), o aplicativo identifica automaticamente:
    - **Franquia**: *Resident Evil*
    - **Empresa / Desenvolvedora**: *Capcom*
    - **Gêneros**: *Action, Adventure, Survival Horror*
  - Suporte a edição manual dos metadados de qualquer jogo via menu de contexto.

- 🎯 **Filtragem Dinâmica Avançada**:
  - Filtre sua tier list inteira instantaneamente por:
    - **Franquia** (ex: ver apenas jogos do *Resident Evil*, *Dark Souls*, *Final Fantasy*, etc.)
    - **Empresa / Desenvolvedora** (ex: ver apenas jogos da *Capcom*, *FromSoftware*, *CD Projekt Red*, etc.)
    - **Gênero** (ex: ver apenas *RPG*, *Survival Horror*, *Hack and Slash*, etc.)
    - **Busca por texto** em tempo real pelo título do jogo.
  - Combinável (ex: jogos da *Capcom* da franquia *Resident Evil* do gênero *Ação*).

- ⚙️ **Tiers 100% Configuráveis**:
  - Adicione novos tiers personalizados (ex: *SS*, *Obra-Prima*, *Favoritos*).
  - Renomeie qualquer tier existente.
  - Altere as cores do tier com uma paleta de cores vibrantes.
  - Reordene os tiers subindo ou descendo na lista.
  - Exclua tiers com segurança: os jogos são preservados e movidos para o banco de jogos não rankeados.

- 📤 **Exportação e Compartilhamento**:
  - **Exportar como Imagem (PNG)**: gere uma imagem pronta em alta resolução da sua tier list para compartilhar no Discord, Twitter, Reddit, etc.
  - **Exportar / Importar JSON**: faça backup ou compartilhe suas listas de jogos com amigos.

---

## 🚀 Como Executar

### Pré-requisitos
- Python 3.10+
- GTK 4 e Libadwaita
- PyGObject (`python-gobject`)
- Pillow (`python-pillow`)

### Execução em Desenvolvimento
```bash
# Compilar os recursos (apenas na primeira vez ou após alterações no UI/CSS)
glib-compile-resources --target=src/ludustier.gresource --sourcedir=src src/ludustier.gresource.xml

# Executar a aplicação
python3 -m src.main
```

### Executar a Suíte de Testes
```bash
python3 -m unittest tests/test_ludustier.py
```

---

## 📄 Licença
Distribuído sob a licença GNU General Public License v3 (GPL-3.0-or-later).
