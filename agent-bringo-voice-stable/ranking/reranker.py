"""
Vertex AI Ranking API integration
Following Google best practices (validated January 2026)

CRITICAL: Ranking API provides +15-25% improvement in precision
"""
from google.cloud import discoveryengine_v1 as discoveryengine
from typing import List, Dict
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class Reranker:
    """
    Rerank search results using Vertex AI Ranking API
    
    Google Best Practice (Validated Jan 2026):
    - Use semantic-ranker-default@latest (auto-updates to 004)
    - Rerank top 20 from 150 candidates
    - Provides 0-1 relevance scores (not just similarity)
    - +15-25% improvement in nDCG@5
    - Only +50-100ms latency
    """
    
    def __init__(self):
        self.client = discoveryengine.RankServiceClient()
        
        # Ranking model configuration
        self.ranking_config = f"projects/{settings.PROJECT_ID}/locations/global/rankingConfigs/default_ranking_config"
        self.model = settings.RANKING_MODEL  # semantic-ranker-default@latest
        
        logger.info(f"✓ Initialized Ranking API")
        logger.info(f"  - Model: {self.model}")
        logger.info(f"  - Project: {settings.PROJECT_ID}")
    
    def rerank(
        self,
        query: str,
        candidates: List[Dict],
        top_n: int = None
    ) -> List[Dict]:
        """
        Rerank candidates using Ranking API
        
        Google Best Practice:
        - Input: 150 candidates from Vector Search
        - Output: Top 20 ranked by relevance
        - Provides precise 0-1 relevance scores
        
        Args:
            query: Search query or product description
            candidates: List of candidate products from Vector Search
            top_n: Number of top results to return (default from settings)
            
        Returns:
            Reranked candidates with ranking_score added
        """
        if not top_n:
            top_n = settings.RANKING_TOP_N
        
        logger.info(f"Reranking {len(candidates)} candidates...")
        logger.debug(f"Query: {query}")
        
        # Prepare records for Ranking API
        records = []
        for candidate in candidates:
            # Ranking API expects title and content
            record = discoveryengine.RankingRecord(
                id=candidate['id'],
                title=candidate.get('product_name') or candidate['id'],
                content=candidate.get('combined_text') or candidate.get('product_name') or candidate['id']
            )
            records.append(record)
        
        # Create ranking request
        request = discoveryengine.RankRequest(
            ranking_config=self.ranking_config,
            model=self.model,  # semantic-ranker-default@latest
            top_n=top_n,
            query=query,
            records=records
        )
        
        try:
            # Call Ranking API
            response = self.client.rank(request=request)
            
            # Map ranked results back to candidates
            ranked_results = []
            for record in response.records:
                # Find original candidate
                candidate = next((c for c in candidates if c['id'] == record.id), None)
                if candidate:
                    # Add ranking score (0-1, higher = more relevant)
                    candidate['ranking_score'] = record.score
                    ranked_results.append(candidate)
            
            logger.info(f"✓ Reranked to top {len(ranked_results)} results")
            
            # Sort by ranking score (highest first)
            ranked_results.sort(key=lambda x: x.get('ranking_score', 0), reverse=True)
            
            return ranked_results
        
        except Exception as e:
            logger.error(f"Ranking API error: {e}")
            logger.warning("Falling back to Vector Search order")
            
            # Fallback: return original order (by distance)
            return candidates[:top_n]
    
    def rerank_product_similarity(
        self,
        product_text: str,
        candidates: List[Dict],
        top_n: int = None
    ) -> List[Dict]:
        """
        Rerank for product similarity search
        
        Args:
            product_text: Query product description
            candidates: Similar product candidates
            top_n: Number to return
            
        Returns:
            Reranked products
        """
        return self.rerank(
            query=product_text,
            candidates=candidates,
            top_n=top_n
        )
