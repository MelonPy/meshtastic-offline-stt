# Mesh messages (your own recordings)

Short dictated messages typical of mesh use: position reports, arrivals, needs,
times, numbers and place names. FLEURS is read news-style text; this set checks
the engines on the kind of message the device will actually send.

**Privacy:** everything in this folder except this README and the two prompt files
is gitignored. Your recordings never go into git.

## Record

```bash
.venv/bin/python -m bench.datasets.record --lang fr          # all prompts
.venv/bin/python -m bench.datasets.record --lang en --only en05 en25
```

Each prompt is shown, you press Enter, speak, and press Enter again. The WAV is
saved as `data/mesh_messages/<lang>/<id>.wav` (16 kHz, mono, 16-bit). Needs a
microphone and PortAudio (`sudo apt install libportaudio2`). Use `--device` to
pick an input (`--list-devices` lists them).

## Build the manifest

```bash
.venv/bin/python -m bench.datasets.mesh_messages --lang fr en
```

This writes `data/mesh_messages/<lang>/manifest.csv` from the recordings that
exist, using the prompt text as the reference. Then add it to a config, e.g.
`configs/mesh.yaml`.

## Prompt format

`prompts_<lang>.txt`: one `id<TAB>text` per line, `#` starts a comment. Numbers
are written as words so the reference matches what is said; WER normalisation
does not convert digits.
