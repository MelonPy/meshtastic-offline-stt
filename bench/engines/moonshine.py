"""Moonshine via onnxruntime, using the Hugging Face "onnx-community" ONNX exports.

Runs encoder_model.onnx once, then decoder_model_merged.onnx token by token with
a KV cache (greedy decoding). The same code serves moonshine-tiny / -base
(English) and the community French fine-tune, so the comparison is like for like
and no PyTorch is needed on the board.

Decoding: plain greedy, the same for every Moonshine model. With
`use_generation_config: true` the repetition_penalty / no_repeat_ngram_size of
the model's generation_config.json are applied as well (the French fine-tune
sets them; on 20 FLEURS-fr utterances they made WER slightly worse, 69.5% vs
66.9%). Beam search is not implemented (too slow for the target). The token
budget is ceil(duration * tokens_per_second), capped by max_length.
"""
import json
import math
from pathlib import Path

import numpy as np

from .base import Engine, read_wav_float


class Moonshine(Engine):
    name = "moonshine"

    def load(self, model_dir, lang, threads, tokens_per_second=6.5, use_generation_config=False,
             **_):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        d = Path(model_dir)
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        so.log_severity_level = 3
        prov = ["CPUExecutionProvider"]
        self.enc = ort.InferenceSession(str(d / "onnx" / "encoder_model.onnx"), so, providers=prov)
        self.dec = ort.InferenceSession(str(d / "onnx" / "decoder_model_merged.onnx"), so, providers=prov)
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        cfg = json.loads((d / "config.json").read_text())
        gen = json.loads((d / "generation_config.json").read_text())
        self.layers = cfg["decoder_num_hidden_layers"]
        self.kv_heads = cfg.get("decoder_num_key_value_heads", cfg["decoder_num_attention_heads"])
        self.head_dim = cfg["hidden_size"] // cfg["decoder_num_attention_heads"]
        self.start = cfg.get("decoder_start_token_id", 1)
        eos = gen.get("eos_token_id", cfg.get("eos_token_id", 2))
        self.eos = set(eos if isinstance(eos, list) else [eos])
        self.max_length = gen.get("max_length", 194)
        self.rep_penalty = gen.get("repetition_penalty", 1.0) if use_generation_config else 1.0
        self.no_repeat = gen.get("no_repeat_ngram_size", 0) if use_generation_config else 0
        self.tps = tokens_per_second
        self.settings = dict(decoding="greedy", tokens_per_second=tokens_per_second,
                             repetition_penalty=self.rep_penalty, no_repeat_ngram_size=self.no_repeat,
                             max_length=self.max_length, threads=threads)
        self.input_names = [i.name for i in self.dec.get_inputs()]

    def _apply_rules(self, logits, seq):
        if self.rep_penalty and self.rep_penalty != 1.0:
            for t in set(seq):
                logits[t] = logits[t] / self.rep_penalty if logits[t] > 0 else logits[t] * self.rep_penalty
        n = self.no_repeat
        if n and len(seq) >= n:
            prefix = tuple(seq[-(n - 1):]) if n > 1 else ()
            for i in range(len(seq) - n + 1):
                if tuple(seq[i:i + n - 1]) == prefix:
                    logits[seq[i + n - 1]] = -np.inf
        return logits

    def transcribe(self, wav_path):
        audio = read_wav_float(wav_path)[None, :]
        hidden = self.enc.run(None, {"input_values": audio})[0]
        budget = min(self.max_length, max(8, math.ceil(audio.shape[1] / 16000 * self.tps)))
        empty = np.zeros((1, self.kv_heads, 0, self.head_dim), dtype=np.float32)
        past = {}
        for i in range(self.layers):
            for part in ("decoder", "encoder"):
                for kv in ("key", "value"):
                    past[f"past_key_values.{i}.{part}.{kv}"] = empty
        seq = [self.start]
        out_tokens = []
        for step in range(budget):
            feed = {"input_ids": np.array([[seq[-1]]], dtype=np.int64),
                    "encoder_hidden_states": hidden, **past}
            if "use_cache_branch" in self.input_names:
                feed["use_cache_branch"] = np.array([step > 0])
            outs = self.dec.run(None, feed)
            logits = self._apply_rules(outs[0][0, -1].astype(np.float64), seq)
            nxt = int(np.argmax(logits))
            if nxt in self.eos:
                break
            seq.append(nxt)
            out_tokens.append(nxt)
            # outs[1:] = present.{i}.decoder.key/value, present.{i}.encoder.key/value
            names = [o.name for o in self.dec.get_outputs()]
            for name, val in zip(names[1:], outs[1:]):
                key = name.replace("present.", "past_key_values.")
                # The encoder cross-attention cache is only produced on the first step.
                if ".encoder." in key and step > 0:
                    continue
                past[key] = val
        return self.tok.decode(out_tokens, skip_special_tokens=True).strip()

    def info(self):
        import importlib.metadata as md
        return dict(engine="moonshine (onnxruntime)", onnxruntime=md.version("onnxruntime"),
                    tokenizers=md.version("tokenizers"), decoding=self.settings)
