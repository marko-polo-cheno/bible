import torch

import argparse
import json
import logging
import sys
from pathlib import Path

from .index import build_index
from .retrieve import retrieve

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = [
    REPO_ROOT / "backend" / "testimonies_en.jsonl",
    REPO_ROOT / "backend" / "testimonies_zh.jsonl",
]


def _cmd_index(args: argparse.Namespace) -> None:
    paths = [Path(p) for p in args.corpus]
    gpu_ids = [int(x) for x in args.gpus.split(",")] if args.gpus else [0, 1]
    try:
        build_index(
            paths,
            index_dir=Path(args.index_dir) if args.index_dir else None,
            batch_size=args.batch_size,
            gpu_ids=gpu_ids,
            fresh=args.fresh,
            max_docs=args.max_docs,
            max_chunks=args.max_chunks,
        )
    except Exception as e:
        logger.error("%s", e)
        sys.exit(1)


def _cmd_retrieve(args: argparse.Namespace) -> None:
    categories = args.category.split(",") if args.category else None
    try:
        result = retrieve(
            args.query,
            top_k=args.top_k,
            lang_id=args.lang_id,
            category_prefixes=categories,
            index_dir=Path(args.index_dir) if args.index_dir else None,
            gpu_id=args.gpu,
        )
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error("%s", e)
        sys.exit(1)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="BGE-M3 testimony retrieval index")
    sub = parser.add_subparsers(dest="command", required=True)

    idx = sub.add_parser("index", help="Build FAISS index from JSONL corpora")
    idx.add_argument(
        "--corpus",
        nargs="+",
        default=[str(p) for p in DEFAULT_CORPUS],
        help="Paths to testimonies JSONL files",
    )
    idx.add_argument("--index-dir", default=None, help="Output index directory")
    idx.add_argument("--batch-size", type=int, default=32)
    idx.add_argument("--gpus", default="0,1", help="Comma-separated GPU ids for parallel embed")
    idx.add_argument(
        "--fresh",
        action="store_true",
        help="Discard partial embeddings and restart embedding from scratch",
    )
    idx.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Load only the first N testimony documents total (for test runs)",
    )
    idx.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Embed only the first N chunks after chunking (for test runs)",
    )
    idx.set_defaults(func=_cmd_index)

    ret = sub.add_parser("retrieve", help="Semantic search over indexed corpus")
    ret.add_argument("query", type=str)
    ret.add_argument("--top-k", type=int, default=10)
    ret.add_argument("--lang-id", type=int, default=None)
    ret.add_argument("--category", default=None, help="Comma-separated category prefix filters")
    ret.add_argument("--index-dir", default=None)
    ret.add_argument("--gpu", type=int, default=0)
    ret.set_defaults(func=_cmd_retrieve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
