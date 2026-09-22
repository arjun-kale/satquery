# M1 EuroSAT Fine-Tuning Results

**Completed on:** 2026-09-22
**Hardware:** NVIDIA A10G (23.7 GB VRAM)
**Base Model:** `llava-hf/llava-1.5-7b-hf`
**Dataset:** `tanganke/eurosat` (Sentinel-2, 10 RS classes)
**Elapsed Time:** 9006.0 seconds (~2.5 hours)

## Metrics
- **Before Training:** 20.0% accuracy (20/100 correct)
- **After Training:** 97.0% accuracy (97/100 correct)
- **Improvement:** +77.0%

## Architecture Note
This run successfully fine-tuned the vision-language projection and LLM self-attention layers (QLoRA, `r=16`) on a curated remote sensing dataset. It bridges the gap between generic internet images and satellite imagery characteristics.

## Next Steps
The checkpoint is available at `/vol/checkpoints/m1_lora/final` on the Modal Volume `satquery-m1-vol` and is now actively served via the `satquery-m1-infer` app deployed in Phase 5A.