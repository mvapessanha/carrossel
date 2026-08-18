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
- **Gemini** (recomendado, melhor qualidade, mas é pago) — testado com chave
  real em ago/2026: **geração de imagem do Gemini exige billing (Blaze)
  ativado no projeto Google**, mesmo a doc sugerindo tier grátis — o tier
  grátis devolve `limit: 0`. Duas variantes configuradas em
  `config/providers.yaml`, cada uma com teto de gasto próprio
  (`budget_usd`, nunca reseta sozinho): Nano Banana Pro (`gemini-3-pro-image`,
  ~US$0.134/imagem, melhor pra texto longo/preciso) e Nano Banana 2 Flash
  (`gemini-3.1-flash-image`, ~US$0.067/imagem, mais barato). Sem
  `GEMINI_API_KEY`, o sistema cai pros provedores grátis abaixo.
- **Supabase** (obrigatório pra hospedar de verdade) — ver seção "Deploy"
  abaixo. Sem isso, roda só local com SQLite/disco.
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

## Deploy (Render + Supabase)

Uso hoje: poucas pessoas de confiança testando no mesmo link. Orçamento do
Gemini e a fila de geração (só um job por vez) são **compartilhados por todo
mundo que acessar** -- ok pra esse cenário, mas não pra um link público aberto
sem controle nenhum (isso exigiria login por pessoa e orçamento separado,
ainda não construído).

Render free tier tem **disco efêmero** (apaga tudo a cada ~15min de
inatividade) -- por isso o banco de dados vive no Postgres do Supabase e as
imagens no Storage do Supabase, não em disco local. Sem isso, cada sono do
servidor grátis apagaria a biblioteca inteira.

### 1. Criar o projeto no Supabase (grátis, sem cartão)

1. Crie uma conta em https://supabase.com e um novo projeto.
2. Pegue as 3 credenciais e cole no `.env` local primeiro pra testar
   (ver `.env.example` pra onde achar cada uma):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `DATABASE_URL` (use a variante **Transaction pooler**, porta 6543 --
     a conexão direta padrão é só IPv6 e o Render não alcança)
3. Rode local (`uvicorn api.main:app --reload`) uma vez -- isso cria as
   tabelas e o bucket de imagens automaticamente no Supabase.

### 2. Subir o código pro GitHub

```bash
git add -A
git commit -m "sua mensagem"
git push
```

### 3. Criar o Web Service no Render (grátis, sem cartão)

1. Crie uma conta em https://render.com (login com GitHub é o mais rápido).
2. **New → Blueprint**, conecte o repositório do GitHub -- o Render detecta
   o `render.yaml` deste projeto automaticamente e já propõe o serviço
   configurado (build/start command certos).
3. Na tela de variáveis de ambiente, cole os valores reais (os mesmos do seu
   `.env` local): `GEMINI_API_KEY`, `GROQ_API_KEY`, `HF_TOKEN`,
   `POLLINATIONS_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
   `DATABASE_URL`. Nunca comite o `.env` de verdade, só cole aqui no painel.
4. Deploy. Depois de pronto, o Render dá a URL pública (`*.onrender.com`) --
   esse já é o link final pra mandar pra quem for testar.
5. Qualquer `git push` depois disso re-implanta automaticamente.

**Nota sobre o free tier do Render**: o servidor "dorme" depois de ~15min sem
acesso e demora uns 30-50s pra acordar na próxima visita (plano grátis não
tem como evitar isso) -- mas como os dados agora vivem no Supabase, nada se
perde durante esse sono, só demora a primeira resposta depois de um tempo
parado.

## Ajustando a cadeia de IAs

Editar `config/providers.yaml` — dá pra reordenar, ligar/desligar um provedor
ou mudar os limites de cota sem tocar em código. Os limites diários lá são
estimativas conservadoras; ajuste conforme o que você observar de uso real
(o Gemini, por exemplo, pode ser conferido em https://aistudio.google.com/rate-limit).

## Estrutura

```
config/providers.yaml   -> ordem da cadeia de fallback + limites de cota
src/db.py               -> Postgres (Supabase) -- jobs, slides, cota, gasto por provedor
src/planner/            -> divide o conteúdo entre os slides (Groq)
src/providers/          -> um adapter por IA de imagem + o registry (fallback)
src/quota/              -> contador de uso por provedor
src/storage/            -> imagens no Supabase Storage (bucket público) + zip do carrossel
src/prompt_builder.py   -> monta o prompt único mandado pro gerador de imagem
src/edit.py             -> editar um slide já gerado
api/main.py             -> API FastAPI (todos os endpoints)
web/                    -> formulário de criação + biblioteca
render.yaml             -> blueprint de deploy do Render
data/                   -> só cache/scratch local (não é mais a fonte real dos dados), gitignored
```
