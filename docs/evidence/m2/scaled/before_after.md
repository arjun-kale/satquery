| Benchmark (held-out BigEarthNet.txt test split) | Base model (GeoChat-7B) | Post-adaptation (GeoChat-7B + M2 LoRA) | Δ | Trivial baseline¹ | n |
|---|---|---|---|---|---|
| VQA — binary (accuracy) | 0.550 | 0.730 | +0.180 | 0.520 | 100 |
| VQA — multiple choice (accuracy) | 0.270 | 0.770 | +0.500 | 0.310 | 100 |
| VQA — multiple choice, image-dependent categories only (accuracy) | 0.322 | 0.610 | +0.288 | 0.271 | 59 ⚠ small n |
| Grounding — point-prompted (Acc@0.5 IoU) | 0.000 | 0.843 | +0.843 | 0.118 | 51 ⚠ small n |
| Grounding — referring expression (Acc@0.5 IoU) | 0.020 | 0.265 | +0.245 | 0.265 | 49 ⚠ small n |
| Grounding — mean IoU, all | 0.067 | 0.501 | +0.434 | 0.271 | 100 |
| Captioning — ROUGE-L F1 | 0.138 | 0.491 | +0.353 | — | 100 |
| Captioning — BLEU-4 | 0.007 | 0.290 | +0.283 | — | 100 |
| Captioning — LULC-class F1 | 0.000 | 0.494 | +0.494 | — | 100 |

¹ Image-blind strategy on the same references: most common answer (VQA), whole-image box (grounding).
