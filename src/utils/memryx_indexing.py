"""
MemryX indexing pipeline for Oxidus.
Builds embeddings with MX3 and stores FAISS index + metadata.
"""

import os
import json
import time
import threading
from collections import deque
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


class MemryxIndexingError(RuntimeError):
    pass


def _memryx_module():
    memryx_root = Path(os.environ.get('MEMRYX_HOME', r'C:/Program Files/MemryX'))
    python_dir = memryx_root / 'python'
    if python_dir.exists():
        import sys
        sys.path.insert(0, str(python_dir))
    try:
        import memryx  # type: ignore
        return memryx
    except Exception:
        try:
            import mxa  # type: ignore
            return mxa
        except Exception:
            return None


def _tokenizer(model_id: str):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(model_id)


def export_onnx(model_id: str, onnx_path: Path, max_tokens: int = 256) -> None:
    """Export a transformer model to ONNX for MemryX compilation."""
    from transformers import AutoModel
    from transformers.onnx import export, FeaturesManager
    import torch

    tokenizer = _tokenizer(model_id)
    model = AutoModel.from_pretrained(model_id)
    model.eval()
    model.to('cpu')

    try:
        _, onnx_config_cls = FeaturesManager.check_supported_model_or_raise(model, feature='default')
    except Exception:
        _, onnx_config_cls = FeaturesManager.check_supported_model_or_raise(model, feature='feature-extraction')

    onnx_config = onnx_config_cls(model.config)

    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    export(
        preprocessor=tokenizer,
        model=model,
        config=onnx_config,
        opset=17,
        output=onnx_path
    )


def _find_mx_nc() -> str:
    tool = shutil.which('mx_nc') or shutil.which('mx_nc.exe')
    if tool:
        return tool

    bin_env = os.environ.get('MEMRYX_BIN', '').strip()
    if bin_env:
        for name in ("mx_nc", "mx_nc.exe"):
            candidate = Path(bin_env) / name
            if candidate.exists():
                return str(candidate)

    memryx_root = Path(os.environ.get('MEMRYX_HOME', r'C:/Program Files/MemryX'))
    if memryx_root.exists():
        for pattern in ("mx_nc.exe", "mx_nc"):
            try:
                for path in memryx_root.rglob(pattern):
                    try:
                        result = subprocess.run([str(path), "-h"], capture_output=True, text=True)
                        if result.returncode == 0:
                            return str(path)
                    except Exception:
                        continue
            except Exception:
                continue

    raise MemryxIndexingError(
        "mx_nc not found. Activate the MemryX venv or set MEMRYX_BIN/MEMRYX_HOME and PATH."
    )


def _wsl_path(path: Path) -> Optional[str]:
    raw = str(path)
    normalized = raw.replace('\\', '/')
    try:
        result = subprocess.run(
            ["wsl", "wslpath", "-a", normalized],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()

        # Fallback conversion for drive-letter paths when wslpath fails.
        if len(normalized) > 2 and normalized[1:3] == ':/':
            drive = normalized[0].lower()
            rest = normalized[3:]
            return f'/mnt/{drive}/{rest}'
        return None
    except Exception:
        if len(normalized) > 2 and normalized[1:3] == ':/':
            drive = normalized[0].lower()
            rest = normalized[3:]
            return f'/mnt/{drive}/{rest}'
        return None


def _try_wsl_compile(onnx_path: Path, dfp_path: Path, num_chips: int) -> None:
    if os.environ.get('OXIDUS_WSL_MX', '1').lower() in {'0', 'false', 'off', 'no'}:
        raise MemryxIndexingError(
            "mx_nc not found. Add MemryX tools to PATH or set MEMRYX_HOME."
        )

    onnx_wsl = _wsl_path(onnx_path)
    dfp_wsl = _wsl_path(dfp_path)
    if not onnx_wsl or not dfp_wsl:
        raise MemryxIndexingError(
            "mx_nc not found and WSL is unavailable. Install WSL + MemryX tools."
        )

    venv = os.environ.get('OXIDUS_WSL_MX_VENV', '').strip() or '$HOME/mx'
    use_autocrop = os.environ.get('OXIDUS_MEMRYX_AUTOCROP', '1').lower() not in {'0', 'false', 'off', 'no'}
    autocrop_arg = ' --autocrop' if use_autocrop else ''
    activate = f"source {venv}/bin/activate >/dev/null 2>&1 || true"
    cmd = (
        f"{activate} && "
        f"MXNC=\"$(command -v mx_nc)\"; "
        f"if [ -z \"$MXNC\" ] && [ -x {venv}/bin/mx_nc ]; then MXNC={venv}/bin/mx_nc; fi; "
        f"if [ -z \"$MXNC\" ]; then echo 'mx_nc not found in WSL'; exit 127; fi; "
        f"$MXNC -m '{onnx_wsl}' --dfp_fname '{dfp_wsl}' -c {num_chips}{autocrop_arg}"
    )
    args = ["wsl", "-e", "bash", "-lc", cmd]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise MemryxIndexingError(
            result.stderr
            or result.stdout
            or 'mx_nc failed in WSL (venv not active?)'
        )


def _load_json(path: Path) -> Optional[Dict]:
    try:
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _iter_documents(root: Path) -> Iterable[Dict[str, str]]:
    for path in root.rglob('*'):
        if path.is_dir():
            continue
        if 'retired' in path.parts or 'cache' in path.parts:
            continue
        if path.suffix.lower() == '.json':
            payload = _load_json(path)
            if not payload:
                continue
            content = payload.get('content') or payload.get('text')
            if not content:
                continue
            yield {
                'source_path': str(path),
                'title': payload.get('title') or path.stem,
                'url': payload.get('url', ''),
                'content': content
            }
        elif path.suffix.lower() in {'.txt', '.md'}:
            try:
                text = path.read_text(encoding='utf-8')
            except Exception:
                continue
            if not text.strip():
                continue
            yield {
                'source_path': str(path),
                'title': path.stem,
                'url': '',
                'content': text
            }


def _chunk_text(text: str, max_tokens: int, tokenizer) -> List[str]:
    """Chunk text into smaller pieces based on token count."""
    if not text or not text.strip():
        return []
    
    try:
        tokens = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    except Exception:
        # If tokenization fails, return the whole text as one chunk
        return [text]
    
    # Handle cases where tokens might not be a dict or might be None
    if not tokens or not hasattr(tokens, 'get'):
        return [text]
        
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


def _prepare_inputs(texts: List[str], tokenizer, max_length: int) -> Tuple[np.ndarray, ...]:
    """Prepare tokenized inputs for the model."""
    if not texts:
        raise ValueError("No texts provided for tokenization")
    
    try:
        encoded = tokenizer(
            texts,
            padding='max_length',
            truncation=True,
            max_length=max_length,
            return_tensors='np'
        )
    except Exception as e:
        raise MemryxIndexingError(f"Tokenization failed: {type(e).__name__}")
    
    # Validate encoded output
    if not encoded or not hasattr(encoded, 'get') and not hasattr(encoded, '__getitem__'):
        raise MemryxIndexingError("Tokenizer returned invalid output")
    
    inputs = []
    for key in ['input_ids', 'attention_mask', 'token_type_ids']:
        if key in encoded:
            inputs.append(encoded[key].astype(np.int32))
    
    if not inputs:
        raise MemryxIndexingError("No valid inputs generated from tokenizer")
    
    return tuple(inputs)


def _mean_pool(last_hidden: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask = np.expand_dims(attention_mask, axis=-1)
    masked = last_hidden * mask
    summed = masked.sum(axis=1)
    counts = mask.sum(axis=1)
    counts[counts == 0] = 1
    return summed / counts


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return vectors / norms


def _cpu_embed_batch(batch_texts: List[str], model, tokenizer, max_tokens: int) -> np.ndarray:
    import torch

    encoded = tokenizer(
        batch_texts,
        padding='max_length',
        truncation=True,
        max_length=max_tokens,
        return_tensors='pt'
    )
    encoded = {k: v.to('cpu') for k, v in encoded.items()}

    with torch.no_grad():
        outputs = model(**encoded)
        last_hidden = outputs.last_hidden_state.cpu().numpy()

    attention_mask = encoded['attention_mask'].cpu().numpy().astype(np.int32)
    return _mean_pool(last_hidden, attention_mask)


def _materialize_static_onnx(onnx_path: Path, max_tokens: int) -> Path:
    """Create a static-shape ONNX copy for compilers that reject symbolic dims."""
    try:
        import onnx
    except Exception as exc:
        raise MemryxIndexingError(f'onnx package is required to staticize model shapes: {exc}')

    try:
        model = onnx.load(str(onnx_path))
    except Exception as exc:
        raise MemryxIndexingError(f'Failed to load ONNX for staticization: {onnx_path} ({exc})')

    changed = False
    for value_info in model.graph.input:
        tensor_type = value_info.type.tensor_type
        if not tensor_type.HasField('shape'):
            continue
        dims = tensor_type.shape.dim
        if len(dims) >= 1 and (dims[0].dim_param or dims[0].dim_value == 0):
            dims[0].dim_param = ''
            dims[0].dim_value = 1
            changed = True
        if len(dims) >= 2 and (dims[1].dim_param or dims[1].dim_value == 0):
            dims[1].dim_param = ''
            dims[1].dim_value = int(max_tokens)
            changed = True

    if not changed:
        return onnx_path

    static_dir = Path(tempfile.gettempdir()) / 'oxidus_memryx'
    static_dir.mkdir(parents=True, exist_ok=True)
    static_path = static_dir / f'{onnx_path.stem}.static_{int(max_tokens)}{onnx_path.suffix}'
    try:
        onnx.save(model, str(static_path))
    except Exception as exc:
        raise MemryxIndexingError(f'Failed to write static ONNX: {static_path} ({exc})')
    return static_path


def compile_to_dfp(onnx_path: Path, dfp_path: Path, num_chips: int = 0, max_tokens: int = 192) -> None:
    dfp_path.parent.mkdir(parents=True, exist_ok=True)
    compile_onnx_path = _materialize_static_onnx(onnx_path, max_tokens=max_tokens)
    use_autocrop = os.environ.get('OXIDUS_MEMRYX_AUTOCROP', '1').lower() not in {'0', 'false', 'off', 'no'}
    autocrop_args = ['--autocrop'] if use_autocrop else []
    prefer_wsl = (
        os.name == 'nt'
        and os.environ.get('OXIDUS_WSL_MX', '1').lower() not in {'0', 'false', 'off', 'no'}
    )
    if prefer_wsl:
        try:
            _try_wsl_compile(compile_onnx_path, dfp_path, num_chips)
            return
        except MemryxIndexingError:
            pass

    try:
        mx_nc = _find_mx_nc()
    except MemryxIndexingError:
        _try_wsl_compile(compile_onnx_path, dfp_path, num_chips)
        return

    args = [mx_nc, '-m', str(compile_onnx_path), '--dfp_fname', str(dfp_path), '-c', str(num_chips), *autocrop_args]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise MemryxIndexingError(result.stderr or result.stdout or 'mx_nc failed')


def build_index(
    model_id: str,
    onnx_path: Path,
    dfp_path: Path,
    data_root: Path,
    output_dir: Path,
    max_tokens: int = 256,
    batch_size: int = 16,
    device_ids: Optional[List[int]] = None,
    use_memryx: bool = True,
    prefer_async: bool = True,
    progress_cb: Optional[callable] = None,
    priority_paths: Optional[List[str]] = None,
    batch_delay_s: float = 0.0
) -> Dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    if use_memryx:
        memryx = _memryx_module()
        if not memryx:
            raise MemryxIndexingError('MemryX Python bindings not importable')
        if not dfp_path.exists():
            raise MemryxIndexingError('DFP not found. Compile first.')
    else:
        memryx = None

    tokenizer = _tokenizer(model_id)
    
    # Validate tokenizer is functional
    if not tokenizer or not hasattr(tokenizer, '__call__'):
        raise MemryxIndexingError('Failed to initialize tokenizer')

    texts = []
    metadata = []
    documents = list(_iter_documents(data_root))
    
    # Early validation - check for empty knowledge base
    if not documents:
        raise MemryxIndexingError('No documents found in knowledge base')
    
    if priority_paths:
        normalized = [str(Path(path).resolve()) for path in priority_paths if path]
        ranked = []
        for idx, doc in enumerate(documents):
            source_path = doc.get('source_path') or ''
            rank = len(normalized)
            for pos, prefix in enumerate(normalized):
                if source_path.startswith(prefix):
                    rank = pos
                    break
            ranked.append((rank, idx, doc))
        ranked.sort(key=lambda item: (item[0], item[1]))
        documents = [item[2] for item in ranked]

    for doc in documents:
        chunks = _chunk_text(doc['content'], max_tokens=max_tokens, tokenizer=tokenizer)
        for idx, chunk in enumerate(chunks):
            texts.append(chunk)
            metadata.append({
                'title': doc['title'],
                'url': doc['url'],
                'source_path': doc['source_path'],
                'chunk_index': idx,
                'text': chunk
            })

    if not texts:
        raise MemryxIndexingError('No documents found to index')

    embeddings: List[np.ndarray] = []
    total_batches = max(1, (len(texts) + batch_size - 1) // batch_size)
    processed_batches = 0
    start_time = time.time()

    if use_memryx:
        AsyncAccl = getattr(memryx, 'AsyncAccl', None)
        SyncAccl = getattr(memryx, 'SyncAccl', None)
        if not AsyncAccl and not SyncAccl:
            raise MemryxIndexingError('MemryX Accelerator API not available')

        device_ids = device_ids or [0, 1]
        if prefer_async and AsyncAccl:
            accl = AsyncAccl(str(dfp_path), device_ids=device_ids)
            iterator = iter(range(0, len(texts), batch_size))
            output_lock = threading.Lock()
            mask_queue = deque()

            def data_source():
                try:
                    start = next(iterator)
                except StopIteration:
                    return None
                batch = texts[start:start + batch_size]
                inputs = _prepare_inputs(batch, tokenizer, max_length=max_tokens)
                if len(inputs) > 1:
                    mask_queue.append(inputs[1])
                else:
                    mask_queue.append(None)
                return inputs

            def output_processor(*outputs):
                data = outputs[0]
                attn = mask_queue.popleft() if mask_queue else None
                if data.ndim == 3 and attn is not None:
                    pooled = _mean_pool(data, attn)
                else:
                    pooled = data
                with output_lock:
                    embeddings.append(pooled)
                nonlocal processed_batches
                processed_batches += 1
                if progress_cb:
                    progress_cb(processed_batches, total_batches, time.time() - start_time)
                if batch_delay_s > 0:
                    time.sleep(batch_delay_s)

            accl.connect_input(data_source)
            accl.connect_output(output_processor)
            accl.wait()
        elif SyncAccl:
            accl = SyncAccl(str(dfp_path), device_ids=device_ids)
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                inputs = _prepare_inputs(batch, tokenizer, max_length=max_tokens)
                outputs = accl.run(*inputs)
                if isinstance(outputs, (list, tuple)):
                    outputs = outputs[0]
                if outputs.ndim == 3:
                    pooled = _mean_pool(outputs, inputs[1])
                else:
                    pooled = outputs
                embeddings.append(pooled)
                processed_batches += 1
                if progress_cb:
                    progress_cb(processed_batches, total_batches, time.time() - start_time)
                if batch_delay_s > 0:
                    time.sleep(batch_delay_s)
        elif AsyncAccl:
            accl = AsyncAccl(str(dfp_path), device_ids=device_ids)
            iterator = iter(range(0, len(texts), batch_size))
            output_lock = threading.Lock()
            mask_queue = deque()

            def data_source():
                try:
                    start = next(iterator)
                except StopIteration:
                    return None
                batch = texts[start:start + batch_size]
                inputs = _prepare_inputs(batch, tokenizer, max_length=max_tokens)
                if len(inputs) > 1:
                    mask_queue.append(inputs[1])
                else:
                    mask_queue.append(None)
                return inputs

            def output_processor(*outputs):
                data = outputs[0]
                attn = mask_queue.popleft() if mask_queue else None
                if data.ndim == 3 and attn is not None:
                    pooled = _mean_pool(data, attn)
                else:
                    pooled = data
                with output_lock:
                    embeddings.append(pooled)
                nonlocal processed_batches
                processed_batches += 1
                if progress_cb:
                    progress_cb(processed_batches, total_batches, time.time() - start_time)
                if batch_delay_s > 0:
                    time.sleep(batch_delay_s)

            accl.connect_input(data_source)
            accl.connect_output(output_processor)
            accl.wait()
    else:
        from transformers import AutoModel

        model = AutoModel.from_pretrained(model_id)
        model.eval()
        model.to('cpu')

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            pooled = _cpu_embed_batch(batch, model, tokenizer, max_tokens=max_tokens)
            embeddings.append(pooled)
            processed_batches += 1
            if progress_cb:
                progress_cb(processed_batches, total_batches, time.time() - start_time)
            if batch_delay_s > 0:
                time.sleep(batch_delay_s)

    vectors = np.vstack(embeddings)
    vectors = _normalize(vectors.astype(np.float32))

    try:
        import faiss  # type: ignore
    except Exception as exc:
        raise MemryxIndexingError('faiss is required but not installed') from exc

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, str(output_dir / 'faiss.index'))
    with (output_dir / 'metadata.json').open('w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    meta = {
        'model_id': model_id,
        'indexed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'documents': len(metadata),
        'vectors': int(vectors.shape[0]),
        'dimensions': int(vectors.shape[1])
    }
    with (output_dir / 'index_meta.json').open('w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return meta
