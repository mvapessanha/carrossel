# Carrossel IA

Gera imagem única ou carrossel para Instagram a partir de um texto de conteúdo
+ uma descrição de design (com imagens de referência opcionais), usando só IAs
gratuitas, em cadeia de fallback (melhor → pior).

Uso pessoal por enquanto, mas a arquitetura já é pensada pra virar produto
depois (ver `config/providers.yaml` e o plano em
`C:\Users\grsai\.claude\plans\peaceful-coalescing-sparrow.md`).

## Como funciona (resumo)

1. Você escreve o conteúdo (e pode anexar imagem/PDF/DOCX) e a descrição de
   design (com até algumas imagens de referência estética).
2. Uma IA de texto gratuita (**Groq**) divide o conteúdo entre as N imagens
   do carrossel, seguindo a lógica de post do Instagram (gancho → valor →
   CTA), ou aproveita a divisão que você já tiver escrito.
3. Para cada imagem, o sistema tenta gerar com a **melhor IA de imagem
   gratuita disponível** e cai pra próxima da lista se a cota acabar ou der
   erro (ordem definida em `config/providers.yaml`).
4. Você recebe as imagens prontas, pode baixar (uma a uma ou o carrossel
   inteiro em `.zip`), editar cada uma, e tudo fica salvo na **Biblioteca**
   pra consultar ou repetir depois.

## Setup

### 1. Instalar dependências

```bash
cd carrossel-ia
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Criar as contas/chaves

- **Groq** (obrigatório) — divide o texto entre os slides. Grátis, sem
  cartão. Crie em https://console.groq.com/keys
- **Gemini** (opcional, mas hoje não funciona sem billing) — testado com
  chave real em ago/2026: os 3 modelos de imagem disponíveis devolvem
  `limit: 0` no tier gratuito. Ou seja, **geração de imagem do Gemini via API
  exige billing (Blaze) ativado no projeto Google** — não é gratuito de fato
  pra essa finalidade, mesmo a doc sugerindo o contrário. Fica com cota 0 no
  `config/providers.yaml` (pulado automaticamente) até isso mudar.
- **Pollinations "Seed"** (recomendado, grátis) — cadastro em
  https://enter.pollinations.ai. Sem isso, o sistema usa só o tier anônimo:
  funciona, mas é mais lento (~1 chamada a cada 15s) e a qualidade das
  imagens é inconsistente (testado: às vezes segue bem o prompt, às vezes
  devolve algo sem relação nenhuma com o pedido — parece que anônimo cai num
  modelo substituto mais fraco). Com o token, cole em `POLLINATIONS_TOKEN` no
  `.env` — libera também o Kontext (2º da cadeia, segue referência estética).
- **Together AI** — NÃO recomendado: desde 2025 exige cartão com cobrança
  mínima de US$5 só pra criar conta. Deixe `TOGETHER_API_KEY` em branco.

Copie `.env.example` para `.env` e cole as chaves:

```bash
copy .env.example .env
```

### 3. Rodar

```bash
uvicorn api.main:app --reload
```

Abra http://127.0.0.1:8000 no navegador.

## Estado real testado (ago/2026)

Com só Groq configurado (sem Gemini, sem Together, sem token Pollinations),
o sistema **gera imagem de verdade, ponta a ponta**, pelo Pollinations Flux
anônimo (último da cadeia). Qualidade inconsistente entre slides do mesmo
carrossel (ver acima) — pra resultado confiável, vale a pena o cadastro
gratuito no Pollinations Seed.

## Limitação conhecida: Pollinations Kontext e referência de imagem

Mesmo com `POLLINATIONS_TOKEN` configurado, o Kontext só consegue usar
imagens de referência se elas estiverem numa **URL pública** — e rodando
localmente (`localhost`) isso não é possível, porque o servidor deles não
alcança sua máquina. Sem isso, esse provedor é pulado automaticamente quando
há referência de design.

Se quiser habilitar isso mesmo local, exponha o servidor com um túnel (ex:
`ngrok http 8000`) e configure no `.env`:

```
PUBLIC_BASE_URL=https://SEU-TUNEL.ngrok-free.app
```

Quando o sistema for hospedado de verdade (fase de produto), essa variável
vira o domínio real e o provedor passa a funcionar sem gambiarra.

## Deploy (Railway)

Uso hoje: poucas pessoas de confiança testando no mesmo link. Orçamento do
Gemini e a fila de geração (só um job por vez) são **compartilhados por todo
mundo que acessar** -- ok pra esse cenário, mas não pra um link público aberto
sem controle nenhum (isso exigiria login por pessoa e orçamento separado,
ainda não construído).

1. Crie uma conta grátis em https://railway.app (login com GitHub é o mais rápido).
2. Instale a CLI e faça login (abre o navegador pra autenticar):
   ```bash
   npm install -g @railway/cli
   railway login
   ```
3. Dentro da pasta `carrossel-ia`:
   ```bash
   railway init
   railway up
   ```
4. No painel do Railway (web), no seu projeto:
   - **Variables**: cole as mesmas chaves do seu `.env` (`GEMINI_API_KEY`,
     `GROQ_API_KEY`, `HF_TOKEN`, `POLLINATIONS_TOKEN` se tiver) — nunca comite
     o `.env` de verdade, só as variáveis no painel.
   - **Settings → Networking**: gere o domínio público (`*.up.railway.app`) e
     copie a URL.
   - Adicione essa URL como `PUBLIC_BASE_URL` nas variáveis também -- isso
     destrava o Pollinations Kontext (referência de imagem), que só funciona
     com URL pública de verdade.
   - **Volume**: crie um volume persistente montado em `/app/data` (Settings →
     Volumes) -- sem isso, o banco de dados e as imagens geradas somem a cada
     redeploy.
5. Depois de configurado, `railway up` de novo aplica qualquer mudança de código.

## Ajustando a cadeia de IAs

Editar `config/providers.yaml` — dá pra reordenar, ligar/desligar um provedor
ou mudar os limites de cota sem tocar em código. Os limites diários lá são
estimativas conservadoras; ajuste conforme o que você observar de uso real
(o Gemini, por exemplo, pode ser conferido em https://aistudio.google.com/rate-limit).

## Estrutura

```
config/providers.yaml   -> ordem da cadeia de fallback + limites de cota
src/planner/            -> divide o conteúdo entre os slides (Groq)
src/providers/          -> um adapter por IA de imagem + o registry (fallback)
src/quota/              -> contador de uso por provedor
src/storage/            -> imagens geradas em disco + zip do carrossel
src/edit.py             -> editar um slide já gerado
api/main.py             -> API FastAPI (todos os endpoints)
web/                    -> formulário de criação + biblioteca
data/                   -> gerado em runtime (banco SQLite + imagens), gitignored
```
