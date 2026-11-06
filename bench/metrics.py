"""Accuracy, speed and resource metrics.

Text normalisation (applied identically to reference and hypothesis for the
"normalised" WER/CER; the "raw" scores only strip and collapse whitespace):

  1. Unicode NFKC, then lowercase (casefold).
  2. Apostrophes ' ’ ʼ ‘ ` ´ become a space: French elisions are split
     ("l'eau" -> "l eau", "aujourd'hui" -> "aujourd hui"), English contractions
     likewise ("don't" -> "don t"). Same rule on both sides, so it is neutral.
  3. Hyphens and dashes (- ‐ ‑ ‒ – — −) become a space
     ("Saint-Gervais" -> "saint gervais", "vingt-et-un" -> "vingt et un").
  4. All other punctuation and symbols (Unicode categories P*, S*) are removed,
     except that a decimal separator between two digits is kept ("2.5", "2,5").
  5. Whitespace is collapsed.
Accents are kept (they distinguish French words). Numbers are NOT converted:
"100" vs "cent" counts as an error. This penalises engines that write digits
(whisper, moonshine) when the reference spells numbers out, or vice versa.

WER and CER are corpus-level: total edit operations / total reference words
(or characters), computed by jiwer over all utterances of a run.
"""
import re
import statistics
import unicodedata

import jiwer

APOSTROPHES = "'’ʼ‘`´"
DASHES = "-‐‑‒–—−"
_apos = re.compile(f"[{re.escape(APOSTROPHES)}]")
_dash = re.compile(f"[{re.escape(DASHES)}]")
_decimal = re.compile(r"(?<=\d)[.,](?=\d)")
_ws = re.compile(r"\s+")


def normalise(text):
    t = unicodedata.normalize("NFKC", text).casefold()
    t = _apos.sub(" ", t)
    t = _dash.sub(" ", t)
    t = _decimal.sub("\u0000", t)  # protect decimal separators
    t = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in t)
    t = t.replace("\u0000", ".")
    return _ws.sub(" ", t).strip()


def raw(text):
    return _ws.sub(" ", unicodedata.normalize("NFC", text)).strip()


def _rates(refs, hyps):
    pairs = [(r, h) for r, h in zip(refs, hyps) if r]
    if not pairs:
        return None, None
    r, h = zip(*pairs)
    # jiwer rejects empty hypotheses inside a list in some versions; use a placeholder
    # that is never a real word so it scores as deletions + one substitution at most.
    h = [x if x else "∅" for x in h]
    return jiwer.wer(list(r), list(h)), jiwer.cer(list(r), list(h))


def accuracy(refs, hyps):
    wer_raw, cer_raw = _rates([raw(x) for x in refs], [raw(x) for x in hyps])
    wer_n, cer_n = _rates([normalise(x) for x in refs], [normalise(x) for x in hyps])
    return dict(wer_raw=wer_raw, cer_raw=cer_raw, wer=wer_n, cer=cer_n)


def utt_wer(ref, hyp):
    r, h = normalise(ref), normalise(hyp)
    if not r:
        return None
    return jiwer.wer(r, h if h else "∅")


def p90(values):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    if len(v) == 1:
        return v[0]
    return statistics.quantiles(v, n=10, method="inclusive")[8]


def mean(values):
    v = [x for x in values if x is not None]
    return statistics.fmean(v) if v else None


def summarise_utterances(utts):
    """Aggregate per-utterance records produced by bench.worker."""
    ok = [u for u in utts if u.get("error") is None]
    acc = accuracy([u["reference"] for u in ok], [u["hypothesis"] for u in ok])
    rtf = [u["proc_s"] / u["duration"] for u in ok if u["duration"] > 0]
    audio = sum(u["duration"] for u in ok)
    proc = sum(u["proc_s"] for u in ok)
    lat = [u.get("stream_latency_s") for u in ok]
    cpu = [u.get("cpu_util") for u in ok]
    return dict(
        n_utterances=len(ok), n_errors=len(utts) - len(ok), audio_s=audio,
        **acc,
        rtf_mean=mean(rtf), rtf_p90=p90(rtf), rtf_total=(proc / audio if audio else None),
        latency_mean_s=mean([u["proc_s"] for u in ok]), latency_p90_s=p90([u["proc_s"] for u in ok]),
        stream_latency_mean_s=mean(lat), stream_latency_p90_s=p90(lat),
        cpu_util_mean=mean(cpu),
    )
