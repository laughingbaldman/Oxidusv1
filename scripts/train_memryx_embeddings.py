"""
Fine-tune an embedding model on local wiki knowledge and export to ONNX.
Unsupervised SimCSE-style contrastive learning (two dropout views).
"""

import argparse
import math
import random
from pathlib import Path
from typing import Iterable, List

import torch
from torch.utils.data import DataLoader
from transformers import AutoModel, AutoTokenizer

from src.utils.memryx_indexing import export_onnx


def iter_documents(root: Path) -> Iterable[str]:
    for path in root.rglob('*'):
        if path.is_dir():
            continue
        if 'retired' in path.parts or 'cache' in path.parts:
            continue
        if path.suffix.lower() == '.json':
            try:
                payload = path.read_text(encoding='utf-8')
            except Exception:
                continue
            try:
                import json
                data = json.loads(payload)
            except Exception:
                continue
            text = data.get('content') or data.get('text') or ''
            if text.strip():
                yield text
        elif path.suffix.lower() in {'.txt', '.md'}:
            try:
                text = path.read_text(encoding='utf-8')
            except Exception:
                continue
            if text.strip():
                yield text


def chunk_text(text: str, max_tokens: int, tokenizer) -> List[str]:
    tokens = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = tokens.get('offset_mapping', [])
    if not offsets:
        return [text]

    chunks = []
    start = 0
    while start < len(offsets):
        end = min(start + max_tokens, len(offsets))
        slice_offsets = offsets[start:end]
        start_char = slice_offsets[0][0]
        end_char = slice_offsets[-1][1]
        chunk = text[start_char:end_char]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end
    return chunks


def prepare_dataset(data_root: Path, tokenizer, max_tokens: int, limit: int) -> List[str]:
    samples = []
    for doc in iter_documents(data_root):
        chunks = chunk_text(doc, max_tokens=max_tokens, tokenizer=tokenizer)
        samples.extend(chunks)
        if limit and len(samples) >= limit:
            break
    return samples


def mean_pool(last_hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1)
    summed = (last_hidden * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1)
    return summed / counts


def simcse_loss(embeddings: torch.Tensor, temperature: float = 0.05) -> torch.Tensor:
    bsz = embeddings.size(0) // 2
    z1 = embeddings[:bsz]
    z2 = embeddings[bsz:]

    z1 = torch.nn.functional.normalize(z1, dim=1)
    z2 = torch.nn.functional.normalize(z2, dim=1)

    sim = torch.mm(z1, z2.t()) / temperature
    labels = torch.arange(bsz, device=embeddings.device)
    loss = torch.nn.functional.cross_entropy(sim, labels)
    return loss


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', default='data/knowledge_base')
    parser.add_argument('--model-id', default='BAAI/bge-small-en-v1.5')
    parser.add_argument('--output-dir', default='data/models/memryx/bge-small-en-v1.5-tuned')
    parser.add_argument('--max-tokens', type=int, default=256)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--epochs', type=int, default=1)
    parser.add_argument('--lr', type=float, default=2e-5)
    parser.add_argument('--sample-limit', type=int, default=2000)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--export-onnx', action='store_true')
    args = parser.parse_args()

    device = torch.device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModel.from_pretrained(args.model_id)
    model.to(device)
    model.train()

    data_root = Path(args.data_root)
    samples = prepare_dataset(data_root, tokenizer, args.max_tokens, args.sample_limit)
    if not samples:
        print('No samples found for training.')
        return 1

    random.shuffle(samples)

    def collate(batch):
        encoded = tokenizer(
            batch,
            padding='max_length',
            truncation=True,
            max_length=args.max_tokens,
            return_tensors='pt'
        )
        return encoded

    loader = DataLoader(samples, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    total_steps = args.epochs * math.ceil(len(samples) / args.batch_size)
    step = 0

    for epoch in range(args.epochs):
        for batch in loader:
            step += 1
            batch = {k: v.to(device) for k, v in batch.items()}
            # Two dropout views
            out1 = model(**batch).last_hidden_state
            out2 = model(**batch).last_hidden_state

            emb1 = mean_pool(out1, batch['attention_mask'])
            emb2 = mean_pool(out2, batch['attention_mask'])
            embeddings = torch.cat([emb1, emb2], dim=0)

            loss = simcse_loss(embeddings)
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()

            if step % 50 == 0:
                print(f'Epoch {epoch+1} | Step {step}/{total_steps} | Loss {loss.item():.4f}')

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    if args.export_onnx:
        onnx_path = output_dir / 'model.onnx'
        export_onnx(model_id=str(output_dir), onnx_path=onnx_path, max_tokens=args.max_tokens)
        print(f'Exported ONNX to {onnx_path}')

    print(f'Saved tuned model to {output_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
