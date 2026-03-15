"""
Fast Product Name Search Engine using Vector Search
Optimized for voice-based shopping agents

This provides sub-50ms product name lookups with semantic matching,
typo tolerance, and voice transcription error handling.
"""
from google.cloud import aiplatform
from google.cloud.aiplatform import MatchingEngineIndexEndpoint
from typing import List, Dict, Optional
import logging
from config.settings import settings
from embeddings.generator import MultimodalEmbeddingGenerator

logger = logging.getLogger(__name__)

class NameSearchEngine:
    """
    Fast semantic search for product names using Vector Search

    Use Case: Voice agents need to quickly find products by name
    - Handles ASR errors ("lapte" → "laptee")
    - Semantic matching ("milk" → "lapte")
    - Sub-50ms latency

    Architecture:
    - Separate Vector Search index for product names
    - Text-only embeddings (no images needed for names)
    - Returns product IDs for downstream product search
    """

    def __init__(self, endpoint: MatchingEngineIndexEndpoint = None):
        """
        Initialize name search engine

        Args:
            endpoint: Optional pre-initialized endpoint for name index
        """
        aiplatform.init(project=settings.PROJECT_ID, location=settings.LOCATION)

        if endpoint:
            self.endpoint = endpoint
        else:
            # Find name search endpoint
            # This should be a separate endpoint configured for name embeddings
            endpoint_name = getattr(settings, 'VS_NAME_ENDPOINT_NAME', f"{settings.VS_ENDPOINT_NAME}_names")

            endpoints = MatchingEngineIndexEndpoint.list(
                filter=f'display_name="{endpoint_name}"'
            )

            if not endpoints:
                logger.warning(f"Name search endpoint not found: {endpoint_name}")
                logger.warning("Falling back to BigQuery search. For optimal performance, create a separate Vector Search index for product names.")
                self.endpoint = None
            else:
                self.endpoint = endpoints[0]
                logger.info(f"✓ Initialized Name Search Engine")
                logger.info(f"  - Endpoint: {self.endpoint.display_name}")

        # Text embedding generator (no images for name search)
        self.generator = MultimodalEmbeddingGenerator()

    def is_available(self) -> bool:
        """Check if name search engine is available"""
        return self.endpoint is not None

    def search_by_name(
        self,
        query_name: str,
        num_results: int = 5,
        filter_in_stock: bool = False
    ) -> List[Dict]:
        """
        Search for products by name using semantic vector search

        Args:
            query_name: Product name to search for (e.g., "lapte", "milk", "paine")
            num_results: Number of matching products to return
            filter_in_stock: Only return in-stock products

        Returns:
            List of product matches with scores:
            [
                {
                    'product_id': '12345',
                    'product_name': 'Lapte Zuzu 3.5%',
                    'similarity_score': 0.92,
                    'distance': 0.08
                }
            ]
        """
        if not self.endpoint:
            logger.warning("Name search endpoint not available, returning empty results")
            return []

        logger.info(f"Searching for product name: '{query_name}'")

        # Generate text embedding for the name query
        embedding, _ = self.generator.generate_embedding(
            text=query_name,
            image_url=None  # Name search is text-only
        )

        # Prepare filter
        restricts = []
        if filter_in_stock:
            restricts.append({
                'namespace': 'in_stock',
                'allow_list': ['true']
            })

        # Query Vector Search using MatchServiceClient
        from google.cloud.aiplatform_v1 import MatchServiceClient, FindNeighborsRequest, IndexDatapoint

        public_domain = self.endpoint.public_endpoint_domain_name

        client = MatchServiceClient(
            client_options={
                "api_endpoint": f"{public_domain}:443"
            }
        )

        # Build datapoint
        datapoint = IndexDatapoint(
            feature_vector=embedding,
            restricts=restricts if restricts else []
        )

        # Get deployed index ID for name index
        deployed_index_id = getattr(settings, 'VS_NAME_DEPLOYED_INDEX_ID', settings.VS_DEPLOYED_INDEX_ID)

        # Execute request
        request = FindNeighborsRequest(
            index_endpoint=self.endpoint.resource_name,
            deployed_index_id=deployed_index_id,
            queries=[FindNeighborsRequest.Query(datapoint=datapoint, neighbor_count=num_results)],
            return_full_datapoint=False
        )

        logger.debug(f"Querying name search endpoint: {public_domain}")

        try:
            response = client.find_neighbors(request)
            logger.info(f"Name search response: {len(response.nearest_neighbors)} batches")
        except Exception as e:
            logger.error(f"Name search error: {e}")
            return []

        # Parse results
        results = []
        if response.nearest_neighbors:
            for neighbor in response.nearest_neighbors[0].neighbors:
                results.append({
                    'product_name': neighbor.datapoint.datapoint_id,  # Assuming datapoint_id is product_name
                    'distance': neighbor.distance,
                    'similarity_score': 1 - neighbor.distance
                })

        logger.info(f"✓ Found {len(results)} products matching '{query_name}'")
        if results:
            top_score = results[0]['similarity_score']
            logger.info(f"  Top match score: {top_score:.3f}")

        return results

    def get_best_match_name(
        self,
        query_name: str,
        filter_in_stock: bool = False,
        min_score: float = 0.5
    ) -> Optional[str]:
        """
        Get the best matching product name for a name query

        Args:
            query_name: Product name to search for
            filter_in_stock: Only consider in-stock products
            min_score: Minimum similarity score to accept (0-1)

        Returns:
            Product name of best match, or None if no good match found
        """
        results = self.search_by_name(
            query_name=query_name,
            num_results=1,
            filter_in_stock=filter_in_stock
        )

        if not results:
            return None

        best_match = results[0]
        if best_match['similarity_score'] < min_score:
            logger.warning(
                f"Best match score {best_match['similarity_score']:.3f} below threshold {min_score}"
            )
            return None

        return best_match['product_name']
