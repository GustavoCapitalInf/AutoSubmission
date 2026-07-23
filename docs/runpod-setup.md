# RunPod Setup — baidu/Unlimited-OCR

This is the exact, verified-working configuration for serving `baidu/Unlimited-OCR`
on RunPod, plus every pitfall we hit getting here. Read the troubleshooting section
before re-deriving anything from scratch — most failures below look like new bugs
but are one of these known issues.

## Known-good pod configuration

| Setting | Value |
|---|---|
| GPU | Any card with ≥8GB VRAM (BF16). RTX 3090 (24GB) confirmed working. |
| Container Image | `vllm/vllm-openai:unlimited-ocr` (**not** `:latest` — see below) |
| Container start command | `baidu/Unlimited-OCR --host 0.0.0.0 --port 8000 --trust-remote-code --logits_processors vllm.model_executor.models.unlimited_ocr:NGramPerReqLogitsProcessor --no-enable-prefix-caching --mm-processor-cache-gb 0` |
| Environment Variables | `HF_HUB_DISABLE_XET=1` |
| Container Disk | 60GB |
| Expose HTTP Ports | 8000 |

Template already provides `VLLM_API_KEY="sk-$RUNPOD_POD_ID"` and `HF_HOME=/workspace/.huggingface`
— leave those as-is.

**Endpoint URL pattern:** `https://<pod-id>-8000.proxy.runpod.net/v1`
**API key pattern:** `sk-<pod-id>`

### Verify it's up

```bash
curl -sS "https://<pod-id>-8000.proxy.runpod.net/v1/models" -H "Authorization: Bearer sk-<pod-id>"
```

Should return a JSON model list containing `baidu/Unlimited-OCR`. Then confirm real
inference works (not just that the server is listening) — see "Required request
format" below; an empty `""` response or garbage means the request shape is wrong,
not that the server is broken.

## The "Container Image" field only appears on Edit Pod

RunPod's initial deploy screen only lets you pick from template cards (e.g. "vLLM
Latest") — there's no free-text Docker image field there. To set a custom image
(like `vllm/vllm-openai:unlimited-ocr`), deploy any template first, then go to
**Edit Pod** — that screen has the Container Image field.

## Container start command is NOT shell-parsed

This is the single biggest time-sink we hit. The "Container start command" field
is just a flat list of arguments appended to a fixed `vllm serve` entrypoint —
**not** a shell. `sh -c "..."`, `&&`, quotes, `export`, `mkdir` — none of it works.
Every token is space-split literally and handed to vLLM's own argument parser.

Symptom if you try it anyway:
```
vllm serve: error: argument --compilation-config/-cc: 1 validation error for CompilationConfig
  Invalid JSON: expected value at line 1 column 1 [type=json_invalid, input_value='...']
```
This happens because `-c` (from `sh -c`) gets matched against vLLM's own `-cc`
(`--compilation-config`) short flag, which then tries to consume the rest of your
string as its value.

**Fix:** only ever put plain `vllm serve` arguments in this field. If you need
environment setup (like redirecting the HF cache), use the Environment Variables
UI section instead — never the start command.

## "Disk quota exceeded" during model download (despite `df -h` showing free space)

`OSError: [Errno 122] Disk quota exceeded` during `hf_hub_download` is a RunPod
container overlay quota, not the actual disk size — `df -h /` can report tons of
free space while this error still fires. Two ways to fix, don't need both:

- **Simplest:** bump **Container Disk** to something generous (60GB) and let the
  model download straight there. This is what we ended up using.
- **Alternative:** redirect `HF_HOME` to the network volume (`/workspace`, which
  has far more space), but only via the Environment Variables field — **never**
  inline in the start command (see above). We abandoned this approach because it
  added a moving part without being necessary once the disk was bigger.

## HuggingFace's "Xet" download backend crashes mid-download

```
RuntimeError: Task error: File reconstruction error: Internal Writer Error: Background writer channel closed
```
This is a known instability in `hf_xet`, unrelated to disk/network capacity.
**Fix:** set `HF_HUB_DISABLE_XET=1` as an Environment Variable (already in the
known-good config above) — forces the standard HTTP download path instead.

## Crash-loop with near-instant restarts (~every 1 second)

If the pod is crash-looping *fast* (not the multi-minute cycles you'd see from a
slow model load), suspect **leaked/orphaned GPU memory** from previous crashed
attempts — `nvidia-smi` will show several GB "used" with "No running processes
found". Editing the pod's config again only recreates the *container*, not the
GPU's memory state. **Fix:** a full **Stop then Start** of the pod (not just
Edit-and-save) to force a genuine GPU reset. If that doesn't help, delete and
recreate the pod entirely.

## CUDA graph compilation is slow (10-20+ minutes) and can itself crash

Without `--enforce-eager`, vLLM compiles CUDA graphs for ~50 batch sizes on first
boot — genuinely slow, and we saw it crash outright partway through on one run
(`RuntimeError: Engine core initialization failed. See root cause above.`, with
the actual root cause scrolled out of view in RunPod's log viewer). We did not
end up needing `--enforce-eager` for `baidu/Unlimited-OCR` (the documented config
above omits it and has been stable), but if you see this category of crash, add
`--enforce-eager` to the start command to skip compilation entirely and trade
some inference speed for reliable startup.

## Required request format for `baidu/Unlimited-OCR`

Getting a *live, non-crashing* server is necessary but not sufficient — the model
also demands an exact request shape or it silently returns `""` (finish_reason
`stop`, zero tokens generated, no error).

- **Content block order matters:** the text block (containing the literal
  `<image>` prefix) must come **before** the `image_url` block in the message
  content array. We initially had image-first and got empty output every time.
- **Prompt text:** must be exactly `<image>` immediately followed by the task,
  no space/newline in between — e.g. `<image>Free OCR.` (a newline after
  `<image>` also produced empty output).
- **Required `extra_body` fields** on every request:
  ```python
  extra_body={
      "skip_special_tokens": False,
      "vllm_xargs": {"ngram_size": 35, "window_size": 128},
  }
  ```
  Omitting `skip_special_tokens: False` or the `vllm_xargs` block also produces
  empty output. Use `window_size=1024` instead of `128` if you switch to sending
  multiple page images in one request (whole-document mode).
- All of the above is already implemented in `ocr/ocr_client.py::ocr_page` —
  this section exists so nobody "fixes" it back to the more obvious-looking
  image-first ordering.

## Model output quirks (already handled in code, documented for context)

- **`<|det|>label [x0,y0,x1,y1]<|/det|>`** region-annotation tags prefix almost
  every transcribed line/table. Stripped by `ocr_client.strip_det_tags`.
- **Inline refusal commentary** — on pages with graphics the model can't parse
  (we saw this on a QR code), it sometimes emits a sentence like *"The image
  provided is a QR code. It does not contain any text... no textual content can
  be extracted from this image."* **inline** with otherwise-correct surrounding
  text, rather than just skipping the graphic. Prompt-engineering around this
  (adding "ignore decorative graphics" instructions) made it *worse* — it
  introduced new hallucinated commentary without removing the original.
  Stripped via `ocr_client.strip_refusal_commentary` (post-processing, not
  prompting) instead. If you see a *new* variant of this kind of sentence,
  extend that regex rather than the prompt.

## Why not Nanonets-OCR2 (1.5B-exp or 3B)?

Both produced pure repeating-token garbage (`!!!!!!...`) on every input — plain
text prompts and images alike, across two different model sizes and two
different vLLM crash-loop-free serving sessions. Root cause was never fully
pinned down (suspected chat-template mismatch for this niche model family in
vLLM), but given `baidu/Unlimited-OCR` worked correctly on the first properly-
formatted request, it wasn't worth further investigation. Don't re-attempt
Nanonets without a real reason to.

## Cost management

The pod bills by GPU-hour while running, regardless of whether you're actively
sending requests. **Stop the pod (not Delete) between work sessions** — Stop
preserves the container disk and config so restarting is instant with no
re-setup; Delete would require redoing everything in this document.
