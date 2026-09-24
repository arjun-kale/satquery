| Benchmark (held-out BigEarthNet.txt test split) | Base model (GeoChat-7B) | Post-adaptation (GeoChat-7B + M2 LoRA) | Δ | Trivial baseline¹ | n |
|---|---|---|---|---|---|
| VQA — binary (accuracy) | 0.500 | 0.300 | -0.200 | 0.600 | 10 ⚠ small n |
| VQA — multiple choice (accuracy) | 0.300 | 0.200 | -0.100 | 0.400 | 10 ⚠ small n |
| VQA — multiple choice, image-dependent categories only (accuracy) | 0.500 | 0.333 | -0.167 | 0.667 | 6 ⚠ small n |
| Grounding — point-prompted (Acc@0.5 IoU) | 0.000 | 0.000 | +0.000 | 0.400 | 5 ⚠ small n |
| Grounding — referring expression (Acc@0.5 IoU) | 0.000 | 0.000 | +0.000 | 0.200 | 5 ⚠ small n |
| Grounding — mean IoU, all | 0.001 | 0.017 | +0.016 | 0.322 | 10 ⚠ small n |
| Captioning — ROUGE-L F1 | 0.154 | 0.153 | -0.001 | — | 10 ⚠ small n |
| Captioning — BLEU-4 | 0.000 | 0.000 | +0.000 | — | 10 ⚠ small n |
| Captioning — LULC-class F1 | 0.000 | 0.000 | +0.000 | — | 10 ⚠ small n |

¹ Image-blind strategy on the same references: most common answer (VQA), whole-image box (grounding).
