import numpy as np
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

class QueryType(str, Enum):
    SPECTRAL_WATER_VEGETATION = "SPECTRAL_WATER_VEGETATION"
    CAPTION_SCENE = "CAPTION_SCENE"
    OBJECT_GROUNDING = "OBJECT_GROUNDING"
    CHANGE_DETECTION = "CHANGE_DETECTION"
    SAR_WATER = "SAR_WATER"

# Fixed version for reproducibility
ROUTER_VERSION = "v1.0.0"
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
}

# Fixed DAG maps for each query type
QUERY_DAGS = {
    QueryType.SPECTRAL_WATER_VEGETATION: ["preview", "spectral_index", "geochat_vqa", "geodesy"],
    QueryType.CAPTION_SCENE: ["preview", "geochat_caption"],
    QueryType.OBJECT_GROUNDING: ["preview", "geochat_grounding", "geodesy"],
    QueryType.CHANGE_DETECTION: ["compatibility", "preview", "changeformer", "change_area"],
    QueryType.SAR_WATER: ["sar_calibrate", "sar_despeckle", "mndwi", "geochat_summary"],
}

class RoutingResult(BaseModel):
    query_type: Optional[QueryType]
    dag: List[str]
    score: float
    is_supported: bool

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
        
    def route(self, query: str) -> RoutingResult:
        query_emb = self.model.encode([query], convert_to_numpy=True)[0]
        
        # Cosine similarity
        norm_q = np.linalg.norm(query_emb)
        norm_t = np.linalg.norm(self.template_embeddings, axis=1)
        
        # Prevent division by zero
        if norm_q == 0 or np.any(norm_t == 0):
            return RoutingResult(query_type=None, dag=[], score=0.0, is_supported=False)
            
        similarities = np.dot(self.template_embeddings, query_emb) / (norm_t * norm_q)
        
        sorted_indices = np.argsort(similarities)[::-1]
        best_idx = sorted_indices[0]
        best_score = float(similarities[best_idx])
        best_type = self.template_types[best_idx]
        
        # Check threshold
        if best_score < SIMILARITY_THRESHOLD:
            return RoutingResult(query_type=None, dag=[], score=best_score, is_supported=False)
            
        # Check tie margin (ambiguity)
        if len(sorted_indices) > 1:
            second_best_idx = sorted_indices[1]
            if self.template_types[second_best_idx] != best_type:
                second_best_score = float(similarities[second_best_idx])
                if (best_score - second_best_score) < TIE_MARGIN:
                    return RoutingResult(query_type=None, dag=[], score=best_score, is_supported=False)
                    
        return RoutingResult(
            query_type=best_type,
            dag=QUERY_DAGS[best_type],
            score=best_score,
            is_supported=True
        )
