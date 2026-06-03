"""Thin wrapper around BGEM3FlagModel for normalized dense embeddings."""
from __future__ import annotations

import os
from typing import List, Optional

import numpy as np
from loguru import logger

from .config import EMBED_DIM, MODEL_NAME, ensure_hf_home


def _resolve_devices(explicit: Optional[List[str]]) -> Optional[List[str]]:
    """Pick CUDA devices. Honours RAG_DEVICES (e.g. 'cuda:0' or 'cuda:0,cuda:1') and CUDA_VISIBLE_DEVICES."""
    if explicit:
        return explicit
    env = os.environ.get("RAG_DEVICES")
    if env:
        return [d.strip() for d in env.split(",") if d.strip()]
    import torch
    if not torch.cuda.is_available():
        return None
    n = torch.cuda.device_count()
    return [f"cuda:{i}" for i in range(n)] if n > 0 else None


class Embedder:
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        use_fp16: Optional[bool] = None,
        batch_size: int = 64,
        devices: Optional[List[str]] = None,
    ):
        ensure_hf_home()
        import torch
        from FlagEmbedding import BGEM3FlagModel

        cuda = torch.cuda.is_available()
        resolved = _resolve_devices(devices)
        if use_fp16 is None:
            use_fp16 = cuda
        logger.info(f"Loading {model_name} (cuda={cuda}, fp16={use_fp16}, devices={resolved})")
        kwargs = {"use_fp16": use_fp16}
        if resolved:
            kwargs["devices"] = resolved
        self._model = BGEM3FlagModel(model_name, **kwargs)
        self.batch_size = batch_size
        self.devices = resolved
        self.device = (resolved[0] if resolved else "cpu")

    @property
    def tokenizer(self):
        return self._model.tokenizer

    def embed(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """Return float32 array of shape (N, EMBED_DIM), L2-normalized for cosine via IP."""
        if not texts:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)
        out = self._model.encode(
            texts,
            batch_size=batch_size or self.batch_size,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        vecs = np.asarray(out["dense_vecs"], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms
