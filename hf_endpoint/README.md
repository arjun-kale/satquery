# SatQuery VLM endpoint bundle

`handler.py` + `requirements.txt` are uploaded with the model weights to the private Hugging Face
model repo `<user>/satquery-vlm` by `modal_worker/publish_hf.py`, and served by a Hugging Face
Inference Endpoint (custom task). See `docs/DEPLOY.md`.
