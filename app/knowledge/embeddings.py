"""Configurable local embedding contract; E5 runs offline from verified artifacts."""

import hashlib
import json
from pathlib import Path
from typing import Protocol


class Embedder(Protocol):
    model_id: str

    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


class LocalE5:
    def __init__(self, directory):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        directory = Path(directory)
        manifest = json.loads((directory / "manifest.json").read_text())
        for record in manifest["files"]:
            path = (directory / record["file"]).resolve()
            if not path.is_relative_to(directory.resolve()):
                raise ValueError("Model artifact outside directory")
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError("Model artifact integrity mismatch")
        self.model_id = (
            manifest["model"]
            + "@"
            + manifest["revision"]
            + ":"
            + hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        )
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(
            str(directory / "model.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_padding()
        # No silent truncation of a section or of its attached warning.
        self.tokenizer.no_truncation()

    def encode(self, texts, *, query=False):
        import numpy as np

        results = []
        for offset in range(0, len(texts), 4):
            batch = self.tokenizer.encode_batch(
                [("query: " if query else "passage: ") + t for t in texts[offset : offset + 4]]
            )
            if any(len(e.ids) > 512 for e in batch):
                raise ValueError(
                    "Section exceeds embedding token limit; split with warnings intact"
                )
            ids = np.asarray([e.ids for e in batch], dtype=np.int64)
            mask = np.asarray([e.attention_mask for e in batch], dtype=np.int64)
            inputs = {
                "input_ids": ids,
                "attention_mask": mask,
                "token_type_ids": np.zeros_like(ids),
            }
            hidden = self.session.run(None, inputs)[0]
            pooled = (hidden * mask[..., None]).sum(axis=1) / mask.sum(axis=1)[:, None]
            pooled = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
            results.extend(pooled.tolist())
        return results
