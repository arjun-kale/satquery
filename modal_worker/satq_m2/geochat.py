"""GeoChat prompt conventions and token/label construction.

Everything here mirrors the upstream GeoChat code (github.com/mbzuai-oryx/GeoChat):
- conversation template ``llava_v1`` (geochat/conversation.py), used by all GeoChat eval scripts
- ``tokenizer_image_token`` (geochat/mm_utils.py): prompt chunks around ``<image>`` are tokenized
  separately and each chunk's BOS is dropped
- task tags and box syntax from GeoChat_Instruct: ``[refer] ... <p>phrase</p>`` and
  ``{<x1><y1><x2><y2>|<theta>}`` with coordinates in 0-100 and theta=90 for axis-aligned boxes

BigEarthNet.txt annotations are mapped onto these conventions so the pre-adaptation baseline
is measured with prompts GeoChat actually understands, and training builds on its grounding
ability instead of teaching a new output syntax.
"""

from __future__ import annotations

import re

SYSTEM_PROMPT = (
    "A chat between a curious human and an artificial intelligence assistant. "
    "The assistant gives helpful, detailed, and polite answers to the human's questions."
)
IMAGE_PLACEHOLDER = "<image>"

# GeoChat: CLIP ViT-L/14-336 with position embeddings interpolated to 504px -> 36x36 patches
IMAGE_SIZE = 504
PATCH_SIZE = 14
IMAGE_SEQ_LEN = (IMAGE_SIZE // PATCH_SIZE) ** 2  # 1296, CLS token dropped ("patch" features)

# Token ids added during conversion to the llava-hf layout (same ids as llava-hf/llava-1.5-7b-hf)
IMAGE_TOKEN = "<image>"
PAD_TOKEN = "<pad>"
IMAGE_TOKEN_ID = 32000
PAD_TOKEN_ID = 32001

AXIS_ALIGNED_THETA = 90

VQA_SHORT_SUFFIX = "Answer the question using a single word or phrase."
MCQ_SUFFIX = "Answer with the option's letter from the given choices directly."

_POINT_RE = re.compile(r"<point>\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)\s*</point>")
_BEN_BOX_RE = re.compile(r"\[\s*([\d.]+)\s+([\d.]+)\s*,\s*([\d.]+)\s+([\d.]+)\s*\]")


def _pct(v: float) -> int:
    return max(0, min(100, int(round(float(v) * 100))))


def ben_box_to_geochat(ben_box: str) -> str:
    """'[x1 y1, x2 y2]' (0-1, x first) -> '{<x1><y1><x2><y2>|<90>}' (0-100).

    Axis order was checked empirically: on 1,610 BigEarthNet.txt relative-position questions the
    dominant displacement agreed with first=x in 1,603 cases.
    """
    m = _BEN_BOX_RE.fullmatch(ben_box.strip())
    if not m:
        raise ValueError(f"Unrecognised BigEarthNet.txt box: {ben_box!r}")
    x1, y1, x2, y2 = (_pct(v) for v in m.groups())
    return f"{{<{x1}><{y1}><{x2}><{y2}>|<{AXIS_ALIGNED_THETA}>}}"


def build_question(text_input: str, qtype: str) -> str:
    """Rewrite a BigEarthNet.txt input into GeoChat's task conventions."""
    if qtype == "binary":
        return f"{text_input}\n{VQA_SHORT_SUFFIX}"
    if qtype == "mcq":
        return f"{text_input}\n{MCQ_SUFFIX}"
    if qtype == "captioning":
        return text_input
    if qtype == "bounding box":
        q = text_input.replace("<ref>", "<p>").replace("</ref>", "</p>")
        q = _POINT_RE.sub(lambda m: f"{{<{_pct(m.group(1))}><{_pct(m.group(2))}>}}", q)
        return f"[refer] {q}"
    raise ValueError(f"Unsupported BigEarthNet.txt type: {qtype!r}")


def build_target(reference_output: str, qtype: str) -> str:
    if qtype == "bounding box":
        return ben_box_to_geochat(reference_output)
    return reference_output.strip()


def build_prompt(question: str) -> str:
    """conv_templates['llava_v1'] with one user turn and an open assistant turn."""
    return f"{SYSTEM_PROMPT} USER: {IMAGE_PLACEHOLDER}\n{question} ASSISTANT:"


def tokenizer_image_token(prompt: str, tokenizer) -> list[int]:
    """Port of geochat.mm_utils.tokenizer_image_token, with the image placeholder expanded to
    IMAGE_SEQ_LEN copies of IMAGE_TOKEN_ID (llava-hf inserts image features at those positions)."""
    chunks = [tokenizer(c).input_ids for c in prompt.split(IMAGE_PLACEHOLDER)]
    ids: list[int] = []
    offset = 0
    if chunks and chunks[0] and chunks[0][0] == tokenizer.bos_token_id:
        offset = 1
        ids.append(chunks[0][0])
    for i, chunk in enumerate(chunks):
        if i > 0:
            ids.extend([IMAGE_TOKEN_ID] * IMAGE_SEQ_LEN)
        ids.extend(chunk[offset:])
    return ids


def build_inference_ids(question: str, tokenizer) -> list[int]:
    return tokenizer_image_token(build_prompt(question), tokenizer)


def build_training_ids(question: str, target: str, tokenizer) -> tuple[list[int], list[int]]:
    """Returns (input_ids, labels) with labels = -100 everywhere except the answer and </s>."""
    prompt = build_prompt(question)
    prompt_ids = tokenizer_image_token(prompt, tokenizer)
    full_ids = tokenizer_image_token(f"{prompt} {target}{tokenizer.eos_token}", tokenizer)
    if full_ids[: len(prompt_ids)] != prompt_ids:
        # Tokenization of the answer merged with the prompt's last token; masking by length would
        # then be wrong, so refuse rather than silently train on the wrong tokens.
        raise ValueError(f"Prompt is not a token prefix of prompt+answer for target {target!r}")
    if full_ids[-1] != tokenizer.eos_token_id:
        raise ValueError("Target does not end with EOS; the model would never learn to stop")
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
    return full_ids, labels
