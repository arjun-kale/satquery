import numpy as np
from enum import Enum
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

class QueryType(str, Enum):
    SPECTRAL_WATER_VEGETATION = "SPECTRAL_WATER_VEGETATION"
    CAPTION_SCENE = "CAPTION_SCENE"
    OBJECT_GROUNDING = "OBJECT_GROUNDING"
    CHANGE_DETECTION = "CHANGE_DETECTION"
    SAR_WATER = "SAR_WATER"
    CROSS_MODAL = "CROSS_MODAL"

# Fixed version for reproducibility
ROUTER_VERSION = "v1.1.0"  # 1.1: real SAR steps and index-change in the DAGs
SIMILARITY_THRESHOLD = 0.60
TIE_MARGIN = 0.10

CANONICAL_TEMPLATES = {
    QueryType.SPECTRAL_WATER_VEGETATION: [
        "calculate water or vegetation index",
        "show me the ndvi or mndwi for this region",
        "analyze the vegetation health or water bodies",
    ],
    QueryType.CAPTION_SCENE: [
        "describe this satellite image",
        "what is in this scene",
        "generate a caption for this picture",
    ],
    QueryType.OBJECT_GROUNDING: [
        "find the location of ships",
        "where are the airplanes",
        "detect objects and give their bounding boxes",
    ],
    QueryType.CHANGE_DETECTION: [
        "what has changed between these two images",
        "find the difference between before and after",
        "detect building changes",
    ],
    QueryType.SAR_WATER: [
        "find water in this SAR image",
        "calibrate and despeckle this radar image to find water",
    ],
    QueryType.CROSS_MODAL: [
        "use optical and SAR together",
        "identify built-up regions from radar and optical",
        "combine optical and synthetic aperture radar",
    ],
}

# Fixed DAG maps for each query type
QUERY_DAGS = {
    QueryType.SPECTRAL_WATER_VEGETATION: ["preview", "spectral_index", "geochat_vqa", "geodesy"],
    QueryType.CAPTION_SCENE: ["preview", "geochat_caption"],
    QueryType.OBJECT_GROUNDING: ["preview", "geochat_grounding", "geodesy"],
    QueryType.CHANGE_DETECTION: ["compatibility", "preview", "index_change", "changeformer", "change_area", "change_vqa"],
    QueryType.SAR_WATER: ["sar_calibrate", "sar_despeckle", "sar_water"],
    QueryType.CROSS_MODAL: ["compatibility", "preview", "sar_calibrate", "sar_despeckle", "sar_water", "cross_modal_fusion", "geochat_vqa"],
}

class Candidate(BaseModel):
    task: QueryType
    score: float


class RoutingResult(BaseModel):
    query_type: Optional[QueryType]
    dag: List[str]
    score: float
    is_supported: bool
    # How the task was chosen: embedding similarity, a scene-set rule (e.g. two dates → change),
    # or the user picking an intent after the router was unsure.
    mode: Literal["similarity", "scene_set_rule", "user_choice"] = "similarity"
    runner_up: Optional[Candidate] = None
    # Best similarity per task type, highest first — what the UI offers when the router is unsure.
    candidates: List[Candidate] = Field(default_factory=list)
    rejection: Optional[Literal["low_score", "ambiguous", "needs_pair"]] = None


PAIR_TASKS = {QueryType.CHANGE_DETECTION, QueryType.CROSS_MODAL}


class QueryRouter:
    """
    Deterministic query classifier and router.
    Embeds the incoming query with a local sentence-transformers model,
    compares it to versioned canonical templates using a fixed similarity threshold,
    then selects a fixed DAG.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

        self.template_types = []

        for q_type, templates in CANONICAL_TEMPLATES.items():
            for t in templates:
                self.template_types.append(q_type)

        # Flatten templates to encode
        flat_templates = [t for templates in CANONICAL_TEMPLATES.values() for t in templates]
        self.template_embeddings = self.model.encode(flat_templates, convert_to_numpy=True)

    def _similarities(self, query: str) -> Optional[np.ndarray]:
        query_emb = self.model.encode([query], convert_to_numpy=True)[0]
        norm_q = np.linalg.norm(query_emb)
        norm_t = np.linalg.norm(self.template_embeddings, axis=1)
        if norm_q == 0 or np.any(norm_t == 0):
            return None
        return np.dot(self.template_embeddings, query_emb) / (norm_t * norm_q)

    def _per_type(self, similarities: np.ndarray) -> List[Candidate]:
        best: Dict[QueryType, float] = {}
        for q_type, sim in zip(self.template_types, similarities):
            best[q_type] = max(best.get(q_type, -1.0), float(sim))
        return sorted((Candidate(task=t, score=s) for t, s in best.items()), key=lambda c: -c.score)

    def route(
        self,
        query: str,
        image_ids: List[str] = None,
        scene_set_kind: Optional[str] = None,
        forced_type: Optional[QueryType] = None,
    ) -> RoutingResult:
        n_images = len(image_ids) if image_ids else 0
        similarities = self._similarities(query)

        if similarities is None:
            best_type = QueryType.CHANGE_DETECTION if n_images == 2 else None
            return RoutingResult(query_type=best_type, dag=QUERY_DAGS[best_type] if best_type else [], score=0.0, is_supported=bool(best_type))

        candidates = self._per_type(similarities)
        score_of = {c.task: c.score for c in candidates}

        def result(task: QueryType, mode: str) -> RoutingResult:
            others = [c for c in candidates if c.task != task]
            return RoutingResult(
                query_type=task, dag=QUERY_DAGS[task], score=score_of[task], is_supported=True,
                mode=mode, runner_up=others[0] if others else None, candidates=candidates[:3],
            )

        if forced_type is not None:
            return result(forced_type, "user_choice")

        # The scene set decides pair tasks: the question can't turn two dates into a SAR pair.
        if scene_set_kind == "optical_sar":
            return result(QueryType.CROSS_MODAL, "scene_set_rule")
        if n_images == 2 and (scene_set_kind == "bitemporal" or candidates[0].task != QueryType.CROSS_MODAL):
            return result(QueryType.CHANGE_DETECTION, "scene_set_rule")

        sorted_indices = np.argsort(similarities)[::-1]
        best_idx = sorted_indices[0]
        best_score = float(similarities[best_idx])
        best_type = self.template_types[best_idx]

        def reject(kind: str) -> RoutingResult:
            return RoutingResult(
                query_type=None, dag=[], score=best_score, is_supported=False,
                runner_up=candidates[1] if len(candidates) > 1 else None,
                candidates=candidates[:3], rejection=kind,
            )

        # Check threshold
        if best_score < SIMILARITY_THRESHOLD:
            return reject("low_score")

        # Check tie margin (ambiguity)
        if len(sorted_indices) > 1:
            second_best_idx = sorted_indices[1]
            if self.template_types[second_best_idx] != best_type:
                second_best_score = float(similarities[second_best_idx])
                if (best_score - second_best_score) < TIE_MARGIN:
                    return reject("ambiguous")

        # A pair task asked about one image can't run; say so instead of failing mid-run.
        if n_images == 1 and best_type in PAIR_TASKS:
            rejected = reject("needs_pair")
            rejected.query_type = best_type
            return rejected

        return result(best_type, "similarity")
