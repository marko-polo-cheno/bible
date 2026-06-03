import contextlib
import fcntl
import json
import logging
import multiprocessing as mp
import os
from pathlib import Path

import faiss
import numpy as np
from FlagEmbedding import BGEM3FlagModel
from pydantic import BaseModel
from tqdm import tqdm

from .chunk import chunk_corpus
from .config import EMBED_DIM, MODEL_NAME
from .corpus import load_corpus
from .models import ChunkRecord

logger = logging.getLogger(__name__)

DEFAULT_INDEX_DIR = Path(__file__).resolve().parents[1] / "index"
FAISS_FILE = "faiss.index"
METADATA_FILE = "metadata.jsonl"
EMBEDDINGS_PARTIAL = "embeddings.partial.f32"
CHECKPOINT_FILE = "embed_checkpoint.json"


class ShardProgress(BaseModel):
    gpu_id: int
    row_start: int
    row_end: int
    done: int = 0


class EmbedCheckpoint(BaseModel):
    total: int
    batch_size: int
    model_name: str
    dim: int
    shards: list[ShardProgress]


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return vectors / norms


@contextlib.contextmanager
def _quiet_flagembedding():
    prev = os.environ.get("TQDM_DISABLE")
    os.environ["TQDM_DISABLE"] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("TQDM_DISABLE", None)
        else:
            os.environ["TQDM_DISABLE"] = prev


def _encode_batch(model: BGEM3FlagModel, batch: list[str], batch_size: int) -> np.ndarray:
    with _quiet_flagembedding():
        out = model.encode(batch, batch_size=batch_size, max_length=512)
    dense = out["dense_vecs"]
    if isinstance(dense, list):
        dense = np.array(dense, dtype=np.float32)
    return np.asarray(dense, dtype=np.float32)


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        logger.error("Failed to write %s: %s", path, e)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def _load_checkpoint(path: Path) -> EmbedCheckpoint | None:
    if not path.exists():
        return None
    try:
        return EmbedCheckpoint.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception as e:
        logger.error("Invalid checkpoint %s: %s", path, e)
        return None


def _save_checkpoint(path: Path, checkpoint: EmbedCheckpoint) -> None:
    _atomic_write_json(path, checkpoint.model_dump())


def _commit_shard_done(checkpoint_path: Path, gpu_id: int, done: int) -> None:
    try:
        with open(checkpoint_path, "r+", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                raw = f.read()
                checkpoint = EmbedCheckpoint.model_validate(json.loads(raw))
                for shard in checkpoint.shards:
                    if shard.gpu_id == gpu_id:
                        shard.done = done
                        break
                else:
                    raise ValueError(f"gpu_id {gpu_id} not in checkpoint shards")
                payload = json.dumps(checkpoint.model_dump())
                f.seek(0)
                f.truncate()
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logger.error("Failed to update checkpoint %s: %s", checkpoint_path, e)
        raise


def _invalidate_partial(index_dir: Path) -> None:
    for name in (EMBEDDINGS_PARTIAL, CHECKPOINT_FILE):
        p = index_dir / name
        if p.exists():
            p.unlink()


def _open_embeddings_memmap(path: Path, n_rows: int, dim: int) -> np.memmap:
    if path.exists() and path.stat().st_size == n_rows * dim * 4:
        return np.memmap(path, dtype=np.float32, mode="r+", shape=(n_rows, dim))
    if path.exists():
        path.unlink()
    return np.memmap(path, dtype=np.float32, mode="w+", shape=(n_rows, dim))


def _init_checkpoint(
    index_dir: Path,
    total: int,
    batch_size: int,
    gpu_ids: list[int],
    use_cuda: bool,
    fresh: bool,
) -> tuple[EmbedCheckpoint, np.memmap]:
    checkpoint_path = index_dir / CHECKPOINT_FILE
    embeddings_path = index_dir / EMBEDDINGS_PARTIAL

    if fresh:
        _invalidate_partial(index_dir)

    if use_cuda and len(gpu_ids) > 1 and total >= batch_size:
        mid = total // 2
        shards = [
            ShardProgress(gpu_id=gpu_ids[0], row_start=0, row_end=mid),
            ShardProgress(gpu_id=gpu_ids[1], row_start=mid, row_end=total),
        ]
    else:
        gpu = gpu_ids[0]
        shards = [ShardProgress(gpu_id=gpu, row_start=0, row_end=total)]

    existing = None if fresh else _load_checkpoint(checkpoint_path)
    if existing is not None:
        if (
            existing.total != total
            or existing.batch_size != batch_size
            or existing.model_name != MODEL_NAME
            or existing.dim != EMBED_DIM
            or len(existing.shards) != len(shards)
        ):
            logger.warning("Checkpoint mismatch; restarting embedding from scratch")
            _invalidate_partial(index_dir)
        else:
            for expected, loaded in zip(shards, existing.shards):
                if (
                    expected.gpu_id != loaded.gpu_id
                    or expected.row_start != loaded.row_start
                    or expected.row_end != loaded.row_end
                ):
                    logger.warning("Shard layout changed; restarting embedding from scratch")
                    _invalidate_partial(index_dir)
                    break
            else:
                shards = existing.shards
                done = sum(s.done for s in shards)
                if done:
                    logger.info("Resuming embedding at %d / %d rows", done, total)
                checkpoint = existing
                mmap = _open_embeddings_memmap(embeddings_path, total, EMBED_DIM)
                return checkpoint, mmap

    checkpoint = EmbedCheckpoint(
        total=total,
        batch_size=batch_size,
        model_name=MODEL_NAME,
        dim=EMBED_DIM,
        shards=shards,
    )
    _save_checkpoint(checkpoint_path, checkpoint)
    mmap = _open_embeddings_memmap(embeddings_path, total, EMBED_DIM)
    return checkpoint, mmap


def _embed_shard(
    model: BGEM3FlagModel,
    texts: list[str],
    mmap: np.memmap,
    shard: ShardProgress,
    batch_size: int,
    checkpoint_path: Path,
    desc: str,
) -> None:
    local_done = shard.done
    total_batches = (len(texts) - local_done + batch_size - 1) // batch_size
    position = shard.gpu_id if desc.startswith("embed gpu") else 0
    with tqdm(total=total_batches, desc=desc, unit="batch", position=position) as bar:
        while local_done < len(texts):
            batch = texts[local_done : local_done + batch_size]
            vecs = _encode_batch(model, batch, batch_size)
            row = shard.row_start + local_done
            mmap[row : row + len(batch)] = vecs
            mmap.flush()
            local_done += len(batch)
            _commit_shard_done(checkpoint_path, shard.gpu_id, local_done)
            bar.update(1)


def _embed_worker(
    gpu_id: int,
    texts: list[str],
    row_start: int,
    row_end: int,
    done: int,
    batch_size: int,
    memmap_path: str,
    total_rows: int,
    dim: int,
    checkpoint_path: str,
    result_queue: mp.Queue,
) -> None:
    try:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        model = BGEM3FlagModel(MODEL_NAME, use_fp16=True)
        mmap = np.memmap(memmap_path, dtype=np.float32, mode="r+", shape=(total_rows, dim))
        shard = ShardProgress(gpu_id=gpu_id, row_start=row_start, row_end=row_end, done=done)
        _embed_shard(
            model,
            texts,
            mmap,
            shard,
            batch_size,
            Path(checkpoint_path),
            desc=f"embed gpu{gpu_id}",
        )
        result_queue.put((gpu_id, True))
    except Exception as e:
        logger.error("Embed worker on GPU %s failed: %s", gpu_id, e)
        result_queue.put((gpu_id, False))


def embed_texts_checkpointed(
    texts: list[str],
    index_dir: Path,
    batch_size: int = 32,
    gpu_ids: list[int] | None = None,
    fresh: bool = False,
) -> np.ndarray:
    if not texts:
        return np.zeros((0, EMBED_DIM), dtype=np.float32)

    import torch

    gpu_ids = gpu_ids or [0, 1]
    use_cuda = torch.cuda.is_available()
    if not use_cuda:
        logger.info("CUDA unavailable; embedding on CPU")
        gpu_ids = [0]

    n = len(texts)
    checkpoint_path = index_dir / CHECKPOINT_FILE
    checkpoint, mmap = _init_checkpoint(
        index_dir, n, batch_size, gpu_ids, use_cuda, fresh
    )

    incomplete = [s for s in checkpoint.shards if s.done < s.row_end - s.row_start]
    if not incomplete:
        logger.info("All %d embeddings already on disk", n)
        return np.asarray(mmap, dtype=np.float32)

    multi = use_cuda and len(gpu_ids) > 1 and n >= batch_size and len(checkpoint.shards) > 1

    if multi:
        ctx = mp.get_context("spawn")
        embeddings_path = str(index_dir / EMBEDDINGS_PARTIAL)
        result_queue: mp.Queue = ctx.Queue()
        processes = []
        for shard in incomplete:
            shard_texts = texts[shard.row_start : shard.row_end]
            p = ctx.Process(
                target=_embed_worker,
                args=(
                    shard.gpu_id,
                    shard_texts,
                    shard.row_start,
                    shard.row_end,
                    shard.done,
                    batch_size,
                    embeddings_path,
                    n,
                    EMBED_DIM,
                    str(checkpoint_path),
                    result_queue,
                ),
            )
            p.start()
            processes.append(p)

        for _ in processes:
            gpu_id, ok = result_queue.get()
            if not ok:
                raise RuntimeError(f"Embedding failed on GPU {gpu_id}")
        for p in processes:
            p.join()
        checkpoint = _load_checkpoint(checkpoint_path)
        if checkpoint is None:
            raise RuntimeError("Checkpoint missing after embed")
        for shard in checkpoint.shards:
            if shard.done < shard.row_end - shard.row_start:
                raise RuntimeError(f"Shard gpu{shard.gpu_id} incomplete after workers finished")
        return np.asarray(mmap, dtype=np.float32)

    shard = incomplete[0]
    device = f"cuda:{shard.gpu_id}" if use_cuda else "cpu"
    try:
        if use_cuda:
            os.environ["CUDA_VISIBLE_DEVICES"] = str(shard.gpu_id)
        model = BGEM3FlagModel(MODEL_NAME, use_fp16=use_cuda, device=device)
        shard_texts = texts[shard.row_start : shard.row_end]
        _embed_shard(
            model,
            shard_texts,
            mmap,
            shard,
            batch_size,
            checkpoint_path,
            desc="embed",
        )
        return np.asarray(mmap, dtype=np.float32)
    except Exception as e:
        logger.error("Embed failed: %s", e)
        raise


def save_metadata(chunks: list[ChunkRecord], path: Path) -> None:
    try:
        with path.open("w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(chunk.model_dump_json() + "\n")
    except Exception as e:
        logger.error("Failed to write metadata %s: %s", path, e)
        raise


def build_index(
    corpus_paths: list[Path],
    index_dir: Path | None = None,
    batch_size: int = 32,
    gpu_ids: list[int] | None = None,
    fresh: bool = False,
    max_docs: int | None = None,
    max_chunks: int | None = None,
) -> tuple[Path, Path]:
    index_dir = index_dir or DEFAULT_INDEX_DIR
    index_dir.mkdir(parents=True, exist_ok=True)

    docs = load_corpus(corpus_paths, max_docs=max_docs)
    if max_docs is not None:
        logger.info("Loaded %d documents (max_docs=%d)", len(docs), max_docs)
    chunks = chunk_corpus(docs)
    if not chunks:
        raise ValueError("No chunks produced from corpus")

    if max_chunks is not None:
        if max_chunks <= 0:
            raise ValueError("max_chunks must be positive")
        chunks = chunks[:max_chunks]
        logger.info("Limiting to first %d chunks (test run)", len(chunks))

    meta_path = index_dir / METADATA_FILE
    save_metadata(chunks, meta_path)

    texts = [c.text for c in chunks]
    vectors = embed_texts_checkpointed(
        texts,
        index_dir=index_dir,
        batch_size=batch_size,
        gpu_ids=gpu_ids,
        fresh=fresh,
    )
    vectors = _normalize(vectors.astype(np.float32))

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    faiss_path = index_dir / FAISS_FILE
    try:
        faiss.write_index(index, str(faiss_path))
    except Exception as e:
        logger.error("Failed to persist index: %s", e)
        raise

    _invalidate_partial(index_dir)
    logger.info("Indexed %d chunks (%d docs) -> %s", len(chunks), len(docs), index_dir)
    return faiss_path, meta_path


def load_index(index_dir: Path | None = None) -> tuple[faiss.Index, list[ChunkRecord]]:
    index_dir = index_dir or DEFAULT_INDEX_DIR
    faiss_path = index_dir / FAISS_FILE
    meta_path = index_dir / METADATA_FILE

    try:
        index = faiss.read_index(str(faiss_path))
        chunks: list[ChunkRecord] = []
        with meta_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    chunks.append(ChunkRecord.model_validate(json.loads(line)))
        return index, chunks
    except Exception as e:
        logger.error("Failed to load index from %s: %s", index_dir, e)
        raise
