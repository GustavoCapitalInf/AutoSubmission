#!/usr/bin/env bash
# Serve baidu/Unlimited-OCR on the local AMD GPU (RX 7800 XT / ROCm), exposing an
# OpenAI-compatible endpoint at http://localhost:8000/v1 that this repo's client
# (CLI + webapp) can use unchanged. See requirements-local.txt for setup.
#
# Usage:  ./serve_local.sh
# Then, in another shell, point the client at it:
#   export OCR_BASE_URL=http://localhost:8000/v1
#   export OCR_API_KEY=EMPTY
#   .venv/bin/python -m webapp.app          # or: .venv/bin/python parse.py <pdf>
set -euo pipefail
cd "$(dirname "$0")"

# gfx1101 (7800 XT) runs fine reusing the gfx1100 kernels bundled in the ROCm
# wheel; this override is the widely-used, safe default for RDNA3 desktop cards.
export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-11.0.0}"
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"

exec .venv/bin/python local_ocr_server.py
