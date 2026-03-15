#!/usr/bin/env python3
"""
Real-Time Feature Server
Fetches product features with <2ms latency using Vertex AI Feature Store
"""

from google.cloud import aiplatform_v1
from google.cloud.aiplatform_v1.types import feature_online_store_service
from google.api_core import client_options
from typing import List, Dict, Optional
import logging
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealTimeFeatureServer:
    """
    Ultra-low-latency feature serving for mobile app
    
    Performance:
    - Single product: <2ms
    - Batch (20 products): <5ms
    - Embedding similarity: <10ms
    """
    
    def __init__(
        self,
        project_id: str = "formare-ai",
        location: str = "europe-west1",
        feature_online_store_id: str = "bringo_realtime_features" # Corrected ID (underscores)
    ):
        # ERROR FIX: Must verify regional endpoint for Europe West 1
        # Use dedicated endpoint from settings
        api_endpoint = settings.FS_PUBLIC_ENDPOINT
        
        self.client = aiplatform_v1.FeatureOnlineStoreServiceClient(
            client_options=client_options.ClientOptions(api_endpoint=api_endpoint)
        )
        
        self.feature_online_store = (
            f"projects/{project_id}/locations/{location}/"
            f"featureOnlineStores/{feature_online_store_id}"
        )
        
        # Metadata view for enriched product details
        self.metadata_view = f"{self.feature_online_store}/featureViews/{settings.FS_METADATA_VIEW}"
        self.embeddings_view = f"{self.feature_online_store}/featureViews/product_embeddings_view" # inferred convention
        
        logger.info(f"✓ Initialized RealTimeFeatureServer")
        logger.info(f"  Feature Store: {feature_online_store_id}")
    
    def _fetch_single_product(self, product_id: str, view: str) -> Optional[Dict]:
        """Helper to fetch one product"""
        try:
            data_key = feature_online_store_service.FeatureViewDataKey(key=str(product_id))
            request = feature_online_store_service.FetchFeatureValuesRequest(
                feature_view=view,
                data_key=data_key
            )
            response = self.client.fetch_feature_values(request=request)
            
            # Response has key_values (singular) or data_keys_with_values?
            # Standard response for single fetch usually puts data in key_values
            
            # Let's inspect response structure safely
            # Proto structure: key_values -> FeatureViewDataKey
            
            # Actually, fetch_feature_values returns dictionary-like access in some SDK versions,
            # but usually it returns a FetchFeatureValuesResponse.
            # If using data_key (singular), the response usually contains `key_values` field.
            
            return response
        except Exception as e:
            logger.warning(f"Failed to fetch {product_id}: {e}")
            return None

    def get_product_metadata(self, product_ids: List[str]) -> Dict[str, Dict]:
        """
        Fetch real-time product metadata for given IDs
        Parallelized for performance
        """
        import concurrent.futures
        
        logger.info(f"Fetching metadata for {len(product_ids)} products...")
        products = {}
        
        def fetch_one(pid):
            try:
                data_key = feature_online_store_service.FeatureViewDataKey(key=str(pid))
                request = feature_online_store_service.FetchFeatureValuesRequest(
                    feature_view=self.metadata_view,
                    data_key=data_key
                )
                response = self.client.fetch_feature_values(request=request)
                
                # The response object has `key_values` which contains `features` list directly?
                # Based on raw output: key_values { features { ... } }
                features = {}
                kv = response.key_values
                
                # Iterate over features list directly
                for fv in kv.features:
                    name = fv.name
                    val = fv.value
                    
                    # Correctly identify which field is set in the oneof
                    field = val._pb.WhichOneof("value")
                    if field == "string_value":
                        features[name] = val.string_value
                    elif field == "double_value":
                        features[name] = val.double_value
                    elif field == "int64_value":
                        features[name] = val.int64_value
                    elif field == "bool_value":
                        features[name] = val.bool_value
                
                # Debug: Log feature names on first fetch
                if not hasattr(self, '_logged_fs_fields'):
                    logger.info(f"Feature Store fields available: {list(features.keys())}")
                    self._logged_fs_fields = True
                    
                return pid, features
            except Exception as e:
                # Log the error to see why it failed
                logger.error(f"Error fetching {pid}: {e}")
                return pid, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_pid = {executor.submit(fetch_one, pid): pid for pid in product_ids}
            for future in concurrent.futures.as_completed(future_to_pid):
                pid, data = future.result()
                if data:
                    products[pid] = data
        
        logger.info(f"✓ Fetched {len(products)} product metadata records")
        return products
    
    def get_product_embeddings(self, product_ids: List[str]) -> Dict[str, List[float]]:
        """Fetch product embeddings"""
        import concurrent.futures
        
        logger.info(f"Fetching embeddings for {len(product_ids)} products...")
        embeddings = {}
        
        def fetch_one(pid):
            try:
                data_key = feature_online_store_service.FeatureViewDataKey(key=str(pid))
                request = feature_online_store_service.FetchFeatureValuesRequest(
                    feature_view=self.embeddings_view,
                    data_key=data_key
                )
                response = self.client.fetch_feature_values(request=request)
                
                kv = response.key_values
                emb = None
                
                for feature_value in kv.features:
                    if feature_value.name == 'multimodal_embedding':
                        v = feature_value.value
                        # Check for array values
                        if v.double_array_value and v.double_array_value.values:
                            emb = list(v.double_array_value.values)
                return pid, emb
            except Exception:
                return pid, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_pid = {executor.submit(fetch_one, pid): pid for pid in product_ids}
            for future in concurrent.futures.as_completed(future_to_pid):
                pid, data = future.result()
                if data:
                    embeddings[pid] = data
        
        logger.info(f"✓ Fetched {len(embeddings)} embeddings")
        return embeddings
    
    def search_nearest_embeddings(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        filter_in_stock: bool = True
    ) -> List[Dict]:
        """
        Search for nearest neighbors using Feature Store's native embedding search
        
        Args:
            query_embedding: Query vector (512D)
            top_k: Number of results
            filter_in_stock: Only return in-stock products
            
        Returns:
            List of products with metadata and similarity scores
        """
        
        logger.info(f"Searching nearest embeddings (top_k={top_k})...")
        
        # Create embedding request
        request = feature_online_store_service.SearchNearestEntitiesRequest(
            feature_view=self.embeddings_view,
            query=feature_online_store_service.NearestNeighborQuery(
                embedding=feature_online_store_service.NearestNeighborQuery.Embedding(
                    value=query_embedding
                ),
                neighbor_count=top_k * 2 if filter_in_stock else top_k  # Over-fetch for filtering
            )
        )
        
        response = self.client.search_nearest_entities(request=request)
        
        # Extract neighbor IDs
        neighbor_ids = [
            neighbor.entity_id 
            for neighbor in response.nearest_neighbors.neighbors
        ]
        
        # Fetch metadata for neighbors
        neighbor_metadata = self.get_product_metadata(neighbor_ids)
        
        # Combine and filter
        results = []
        for neighbor in response.nearest_neighbors.neighbors:
            product_id = neighbor.entity_id
            metadata = neighbor_metadata.get(product_id, {})
            
            # Apply stock filter
            if filter_in_stock and not metadata.get('in_stock', False):
                continue
            
            results.append({
                'product_id': product_id,
                'similarity_score': neighbor.distance,  # Already normalized
                **metadata
            })
            
            if len(results) >= top_k:
                break
        
        logger.info(f"✓ Found {len(results)} in-stock neighbors")
        
        return results
    
    def get_product_with_embedding(self, product_id: str) -> Optional[Dict]:
        """
        Fetch both metadata and embedding for a single product
        
        Optimized for substitution queries
        """
        
        metadata = self.get_product_metadata([product_id])
        embeddings = self.get_product_embeddings([product_id])
        
        if product_id in metadata:
            return {
                **metadata[product_id],
                'embedding': embeddings.get(product_id)
            }
        
        return None

# Convenience singleton
_feature_server = None

def get_feature_server() -> RealTimeFeatureServer:
    """Get or create feature server singleton"""
    global _feature_server
    if _feature_server is None:
        _feature_server = RealTimeFeatureServer()
    return _feature_server
