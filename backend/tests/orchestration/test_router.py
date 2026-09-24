import pytest
from app.orchestration.router import QueryRouter, QueryType, RoutingResult

@pytest.fixture(scope="module")
def router():
    # We use a lightweight model for fast tests, but default is all-MiniLM-L6-v2
    # In tests, this will download the model once and cache it.
    return QueryRouter("all-MiniLM-L6-v2")

def test_router_exact_match(router):
    result = router.route("calculate water or vegetation index")
    assert result.is_supported is True
    assert result.query_type == QueryType.SPECTRAL_WATER_VEGETATION
    assert result.score > 0.99
    assert result.dag == ["preview", "spectral_index", "geochat_vqa", "geodesy"]

def test_router_paraphrase(router):
    # This isn't exactly in the templates, but should route correctly
    result = router.route("can you compute the ndvi for this area")
    assert result.is_supported is True
    assert result.query_type == QueryType.SPECTRAL_WATER_VEGETATION
    assert result.score > 0.60

def test_router_below_threshold(router):
    result = router.route("how many cars are parked outside my house")
    assert result.is_supported is False
    assert result.query_type is None
    assert result.score < 0.60

from unittest.mock import patch

def test_router_ambiguous_tie(router):
    import numpy as np
    from unittest.mock import patch
    
    # We want to force a tie. The easiest way is to mock self.template_embeddings
    # and the query_emb so they match perfectly on two different templates.
    # The actual templates have 14 items. We'll make the first two items identical.
    
    fake_embeddings = np.random.rand(14, 384)
    # Force a tie between the first template and the LAST template
    # Since they belong to different QueryTypes, it will trigger the tie rejection
    fake_embeddings[0] = fake_embeddings[-1]
    
    def mock_encode(texts, **kwargs):
        # Return the exact embedding that matches the first two templates
        return np.array([fake_embeddings[0]])
        
    with patch.object(router, 'template_embeddings', fake_embeddings):
        with patch.object(router.model, 'encode', side_effect=mock_encode):
            result = router.route("some ambiguous query")
            # Because the query matches both template 0 and template 1 perfectly (score 1.0),
            # the tie margin is 0.0, which is < TIE_MARGIN. It must reject it!
            assert result.is_supported is False


def test_two_images_route_by_scene_set_rule_with_real_score(router):
    result = router.route("describe this satellite image", image_ids=["a", "b"])
    assert result.query_type == QueryType.CHANGE_DETECTION
    assert result.mode == "scene_set_rule"
    assert result.score < 0.99  # the question is a caption request; the score says so
    assert result.runner_up is not None


def test_optical_sar_scene_set_routes_to_cross_modal(router):
    result = router.route("what changed here", image_ids=["a", "b"], scene_set_kind="optical_sar")
    assert result.query_type == QueryType.CROSS_MODAL
    assert result.mode == "scene_set_rule"


def test_change_question_on_one_image_needs_a_pair(router):
    result = router.route("what has changed between these two images", image_ids=["a"])
    assert result.is_supported is False
    assert result.rejection == "needs_pair"
    assert result.query_type == QueryType.CHANGE_DETECTION


def test_low_score_rejection_offers_candidates(router):
    result = router.route("how many cars are parked outside my house")
    assert result.rejection == "low_score"
    assert len(result.candidates) == 3
    assert result.candidates[0].score >= result.candidates[1].score


def test_user_choice_overrides_similarity(router):
    result = router.route("how many cars are parked outside my house", forced_type=QueryType.OBJECT_GROUNDING)
    assert result.is_supported is True
    assert result.mode == "user_choice"
    assert result.dag == ["preview", "geochat_grounding", "geodesy"]
