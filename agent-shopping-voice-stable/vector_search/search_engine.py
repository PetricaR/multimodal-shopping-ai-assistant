"""
Vector Search query engine
Retrieves similar products using approximate nearest neighbor search
"""
from google.cloud import aiplatform
from google.cloud.aiplatform import MatchingEngineIndexEndpoint
from google.cloud.aiplatform_v1 import MatchServiceClient, FindNeighborsRequest, IndexDatapoint
from typing import List, Dict, Optional
import logging
from config.settings import settings
from embeddings.generator import MultimodalEmbeddingGenerator

logger = logging.getLogger(__name__)

class SearchEngine:
    """
    Query Vector Search index for similar products

    Google Best Practice:
    - Retrieve 150 candidates (fast, approximate)
    - Use Ranking API for precision (see ranking/reranker.py)
    """

    def __init__(self, endpoint: MatchingEngineIndexEndpoint = None):
        aiplatform.init(project=settings.PROJECT_ID, location=settings.LOCATION)

        if endpoint:
            self.endpoint = endpoint
        else:
            # Find endpoint by name AND verify deployed index
            endpoints = MatchingEngineIndexEndpoint.list(
                filter=f'display_name="{settings.VS_ENDPOINT_NAME}"'
            )

            if not endpoints:
                raise ValueError(f"Endpoint not found: {settings.VS_ENDPOINT_NAME}")

            # If multiple endpoints exist, find the one with our deployed index
            matching_endpoint = None
            for ep in endpoints:
                try:
                    deployed_indexes = ep.deployed_indexes
                    for deployed in deployed_indexes:
                        if deployed.id == settings.VS_DEPLOYED_INDEX_ID:
                            matching_endpoint = ep
                            logger.info(f"Found endpoint with deployed index: {settings.VS_DEPLOYED_INDEX_ID}")
                            break
                    if matching_endpoint:
                        break
                except Exception as e:
                    logger.warning(f"Could not check deployed indexes for endpoint {ep.display_name}: {e}")
                    continue

            if not matching_endpoint:
                # Fallback to first endpoint (backward compatibility)
                logger.warning(f"Could not find endpoint with deployed index {settings.VS_DEPLOYED_INDEX_ID}, using first match")
                matching_endpoint = endpoints[0]

            self.endpoint = matching_endpoint

            # Log endpoint details for debugging
            logger.info(f"Selected endpoint: {self.endpoint.resource_name}")
            logger.info(f"  Public domain: {self.endpoint.public_endpoint_domain_name}")

        self.generator = MultimodalEmbeddingGenerator()

        # Cache a single MatchServiceClient to reuse the gRPC channel across all calls.
        # Creating a new client per search_by_embedding invocation would open a new TLS
        # connection every time — especially costly when many parallel threads search
        # simultaneously (each thread would incur a ~100-200ms handshake).
        public_domain = self.endpoint.public_endpoint_domain_name
        self._match_client = MatchServiceClient(
            client_options={"api_endpoint": f"{public_domain}:443"}
        )

        logger.info(f"Initialized Search Engine")
        logger.info(f"  - Endpoint: {self.endpoint.display_name}")

    def _enrich_with_metadata(self, results: List[Dict]) -> List[Dict]:
        """
        Enrich vector search results with complete metadata from Feature Store.

        Flow:
        1. Vector Search returns product IDs (numeric)
        2. Feature Store enriches with: product_id, variant_id, price, etc.
        3. Agent receives complete product data for cart operations

        Note: Requires Feature Store to be synced with product data
        """
        if not results:
            return results

        try:
            # Import Feature Store client
            from features.realtime_server import get_feature_server
            feature_server = get_feature_server()

            # Get product IDs from results
            product_ids = [r['id'] for r in results]
            logger.info(f"Enriching {len(product_ids)} products from Feature Store...")

            # Fetch metadata from Feature Store
            metadata_dict = feature_server.get_product_metadata(product_ids)

            # Enrich results
            enriched_count = 0
            for result in results:
                pid = result['id']
                result['product_id'] = pid

                if pid in metadata_dict:
                    metadata = metadata_dict[pid]

                    # Map Feature Store fields to result
                    result['product_name'] = metadata.get('product_name', '')
                    result['variant_id'] = metadata.get('variant_id')
                    result['category'] = metadata.get('category')
                    result['price'] = metadata.get('price_ron') or metadata.get('price')
                    result['in_stock'] = metadata.get('in_stock', True)
                    result['store'] = metadata.get('store')
                    result['product_url'] = metadata.get('product_url')

                    enriched_count += 1
                    logger.debug(f"Enriched {pid}: {result.get('product_name')} (variant: {result.get('variant_id')})")
                else:
                    # No metadata found - keep basic info
                    result['product_name'] = f"Product {pid}"
                    logger.warning(f"No Feature Store metadata for product_id: {pid}")

            logger.info(f"Enriched {enriched_count}/{len(results)} products from Feature Store")
            return results

        except Exception as e:
            logger.error(f"Feature Store enrichment failed: {e}", exc_info=True)
            raise  # Don't fallback - we want to know if Feature Store fails

    def search_by_embedding(
        self,
        embedding: List[float],
        num_neighbors: int = 150,
        filter_in_stock: bool = False,
        enrich: bool = True,
    ) -> List[Dict]:
        """
        Search by embedding vector

        Args:
            embedding: Query embedding vector
            num_neighbors: Number of neighbors to retrieve (default 150)
            filter_in_stock: Only return in-stock products
            enrich: Enrich results with Feature Store metadata. Set to False when
                    the caller will do a bulk enrichment pass after deduplication.

        Returns:
            List of {id, distance} dicts
        """
        # Prepare filter
        restricts = []
        if filter_in_stock:
            restricts.append({
                'namespace': 'in_stock',
                'allow_list': ['true']
            })

        # Build datapoint
        datapoint = IndexDatapoint(
            feature_vector=embedding,
            restricts=restricts if restricts else []
        )

        # Execute request — reuse the cached gRPC client (no TLS handshake per call)
        request = FindNeighborsRequest(
            index_endpoint=self.endpoint.resource_name,
            deployed_index_id=settings.VS_DEPLOYED_INDEX_ID,
            queries=[FindNeighborsRequest.Query(datapoint=datapoint, neighbor_count=num_neighbors)],
            return_full_datapoint=False
        )

        public_domain = self.endpoint.public_endpoint_domain_name
        logger.info(f"Querying public endpoint: {public_domain}")
        logger.debug(f"Request: {request}")

        try:
            response = self._match_client.find_neighbors(request)
            logger.info(f"Raw response neighbors count: {len(response.nearest_neighbors)}")
            if response.nearest_neighbors:
                logger.info(f"First batch neighbors: {len(response.nearest_neighbors[0].neighbors)}")
        except Exception as e:
            logger.error(f"MatchServiceClient error: {e}")
            raise e

        # Parse results (response structure is slightly different for GRPC client)
        results = []
        if response.nearest_neighbors:
            for neighbor in response.nearest_neighbors[0].neighbors:
                results.append({
                    'id': neighbor.datapoint.datapoint_id,
                    'distance': neighbor.distance,
                    'similarity_score': 1 - neighbor.distance
                })

        logger.info(f"Found {len(results)} similar products")

        # Enrich with metadata only when requested (skipped in merchandiser path
        # where bulk enrichment happens after deduplication).
        if enrich:
            results = self._enrich_with_metadata(results)

        return results

    def search_by_product_name(
        self,
        product_name: str,
        product_text: str,
        product_image_url: Optional[str] = None,
        num_neighbors: int = 150,
        filter_in_stock: bool = False,
        enrich: bool = True,
    ) -> List[Dict]:
        """
        Search for products similar to given product

        Args:
            product_name: Query product name
            product_text: Product combined text
            product_image_url: Product image URL (optional)
            num_neighbors: Number of neighbors
            filter_in_stock: Only in-stock products
            enrich: Whether to enrich with Feature Store metadata

        Returns:
            List of similar products (excluding query product)
        """
        logger.info(f"Searching for products similar to: {product_name}")

        # Generate query embedding (RETRIEVAL_QUERY for search queries)
        embedding, _ = self.generator.generate_embedding(
            text=product_text,
            image_url=product_image_url,
            task_type="RETRIEVAL_QUERY"
        )

        # Search
        results = self.search_by_embedding(
            embedding=embedding,
            num_neighbors=num_neighbors + 1,  # +1 to exclude self
            filter_in_stock=filter_in_stock,
            enrich=enrich,
        )

        # Note: We cannot filter by product_name here since Vector Search uses product_id as datapoint_id
        # The exclusion will happen at the API layer if needed

        return results[:num_neighbors]

    def search_by_text(
        self,
        query_text: str,
        num_neighbors: int = 150,
        filter_in_stock: bool = False,
        enrich: bool = True,
    ) -> List[Dict]:
        """
        Search products by text query

        Args:
            query_text: Search query (Romanian)
            num_neighbors: Number of results
            filter_in_stock: Only in-stock products
            enrich: Whether to enrich with Feature Store metadata

        Returns:
            List of similar products
        """
        logger.info(f"Searching for: {query_text}")

        # Generate query embedding (RETRIEVAL_QUERY for search queries)
        embedding, _ = self.generator.generate_embedding(
            text=query_text,
            image_url=None,
            task_type="RETRIEVAL_QUERY"
        )

        # Search
        results = self.search_by_embedding(
            embedding=embedding,
            num_neighbors=num_neighbors,
            filter_in_stock=filter_in_stock,
            enrich=enrich,
        )

        return results
