"""Hugging Face Inference Providers — FLUX.1 Kontext [dev]. Gratis (conta sem
cartao, cota mensal de creditos), segue imagem de referencia (so 1 por
chamada, diferente do Gemini/Pollinations Kontext que aceitam varias).

Testado e confirmado funcionando em ago/2026 (edicao de ambiente seguindo
instrucao, manteve a composicao original). Descoberta importante: esse modelo
so faz image-to-image (edicao a partir de uma imagem) -- NAO gera do zero so
com texto. Por isso, sem nenhuma imagem de referencia disponivel (nem do
usuario, nem do primeiro slide do carrossel), esse provedor e' pulado.

Nota de licenca: o modelo em si (pesos) e' licenciado como nao-comercial pra
quem hospeda ele proprio; o texto da licenca permite usar as IMAGENS GERADAS
pra qualquer finalidade, incluindo comercial, mas ha ambiguidade/discussao
sobre isso entre desenvolvedores. Considerar isso se for publicar conteudo
comercial de verdade.
"""
import io
import os

from src.providers.base import GeneratedImage, ImageProvider, ProviderError

MODEL = "black-forest-labs/FLUX.1-Kontext-dev"


class HFFluxKontextProvider(ImageProvider):
    id = "hf_flux_kontext"
    label = "Hugging Face (FLUX Kontext)"
    supports_reference = True
    max_reference_images = 1

    def generate(self, prompt: str, reference_images: list[bytes], aspect_ratio: str) -> GeneratedImage:
        if not reference_images:
            raise ProviderError("precisa de pelo menos 1 imagem de referencia (esse modelo so edita, nao gera do zero)")

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise ProviderError("HF_TOKEN nao configurada")

        try:
            from huggingface_hub import InferenceClient
        except ImportError as e:
            raise ProviderError(f"huggingface_hub nao instalado: {e}") from e

        client = InferenceClient(api_key=token)

        try:
            image = client.image_to_image(reference_images[0], prompt=prompt, model=MODEL)
        except Exception as e:  # a lib nao expoe uma excecao base unica documentada
            raise ProviderError(f"Hugging Face falhou: {e}") from e

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return GeneratedImage(image_bytes=buffer.getvalue(), mime_type="image/png")
