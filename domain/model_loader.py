"""Descarga y resuelve la ruta del modelo YOLO de residuos."""

import logging
import shutil
from pathlib import Path

from domain.waste_classes import (
    _DEFAULT_MODEL_PATH,
    _HF_MODEL_FILENAME,
    _HF_MODEL_REPO,
)

_log = logging.getLogger("ras.model")


def resolve_yolo_model_path(model_path: str | Path | None = None) -> Path:
    if model_path is not None:
        path = Path(model_path)
        if path.is_file():
            return path
        if _is_hf_repo_id(str(model_path)):
            return _download_hf_model(str(model_path))
        raise FileNotFoundError(f"No se encontró el modelo YOLO: {path}")

    default_path = Path(_DEFAULT_MODEL_PATH)
    if default_path.is_file():
        return default_path

    _log.info("Modelo local no encontrado — descargando desde Hugging Face...")
    return _download_hf_model(_HF_MODEL_REPO)


def _is_hf_repo_id(value: str) -> bool:
    return "/" in value and not Path(value).exists()


def _download_hf_model(repo_id: str) -> Path:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "Falta huggingface_hub. Instala con: pip install huggingface_hub"
        ) from exc

    cached_file = hf_hub_download(repo_id=repo_id, filename=_HF_MODEL_FILENAME)
    destination = Path(_DEFAULT_MODEL_PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached_file, destination)
    _log.info("Modelo guardado en %s", destination.resolve())
    return destination
