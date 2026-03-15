"""
Vector Search index manager
Following Google best practices (validated January 2026)
"""
from google.cloud import aiplatform
from google.cloud.aiplatform import MatchingEngineIndex, MatchingEngineIndexEndpoint
import logging
import time
from config.settings import settings

logger = logging.getLogger(__name__)

class IndexManager:
    """
    Manage Vector Search index creation and deployment
    
    Google Best Practices Implemented (Validated Jan 2026):
    - TreeAH algorithm (production-proven)
    - COSINE_DISTANCE (model trained with it)
    - approximateNeighborsCount=150 (standard)
    - 512 dimensions (optimal for production)
    - SHARD_SIZE_SMALL (<10M vectors)
    """
    
    def __init__(self):
        aiplatform.init(project=settings.PROJECT_ID, location=settings.LOCATION)
        self.index = None
        self.endpoint = None
        logger.info(f"✓ Initialized Index Manager")
        logger.info(f"  - Project: {settings.PROJECT_ID}")
        logger.info(f"  - Location: {settings.LOCATION}")
    
    def create_index(
        self,
        embeddings_gcs_uri: str,
        index_name: str = None
    ) -> MatchingEngineIndex:
        """
        Create Vector Search index with TreeAH algorithm
        
        Google Best Practice Configuration:
        - Algorithm: TreeAH (production standard)
        - Distance: COSINE_DISTANCE (model trained with it)
        - Neighbors: 150 (Google standard)
        - Dimensions: 512 (optimal cost/performance)
        
        Args:
            embeddings_gcs_uri: GCS URI with embeddings JSONL
            index_name: Index display name
            
        Returns:
            Created MatchingEngineIndex
        """
        if not index_name:
            index_name = settings.VS_INDEX_NAME
        
        logger.info(f"Creating Vector Search index: {index_name}")
        logger.info(f"  - Embeddings: {embeddings_gcs_uri}")
        logger.info(f"  - Algorithm: TreeAH")
        logger.info(f"  - Distance: COSINE_DISTANCE")
        logger.info(f"  - Dimensions: {settings.EMBEDDING_DIMENSION}")
        logger.info(f"  - Neighbors: {settings.VS_APPROXIMATE_NEIGHBORS}")
        
        # TreeAH configuration (Google Best Practice)
        tree_ah_config = {
            "leafNodeEmbeddingCount": 500,  # Optimal for balance
            "leafNodesToSearchPercent": 7,   # ~150 neighbors for 2000 leaf nodes
        }
        
        # Index configuration
        index_config = {
            "dimensions": settings.EMBEDDING_DIMENSION,  # 512 (validated optimal)
            "approximateNeighborsCount": settings.VS_APPROXIMATE_NEIGHBORS,  # 150 (standard)
            "distanceMeasureType": settings.VS_DISTANCE_MEASURE,  # COSINE_DISTANCE
            "shardSize": settings.VS_SHARD_SIZE,  # SHARD_SIZE_SMALL
            "algorithmConfig": {
                "treeAhConfig": tree_ah_config
            }
        }
        
        logger.info("Index configuration:")
        logger.info(f"  {index_config}")
        
        # Create index
        self.index = MatchingEngineIndex.create_tree_ah_index(
            display_name=index_name,
            contents_delta_uri=embeddings_gcs_uri,
            dimensions=settings.EMBEDDING_DIMENSION,
            approximate_neighbors_count=settings.VS_APPROXIMATE_NEIGHBORS,
            distance_measure_type=settings.VS_DISTANCE_MEASURE,
            shard_size=settings.VS_SHARD_SIZE,
            leaf_node_embedding_count=tree_ah_config["leafNodeEmbeddingCount"],
            leaf_nodes_to_search_percent=tree_ah_config["leafNodesToSearchPercent"],
            description=f"Bringo multimodal product similarity (512D, TreeAH, COSINE)",
            labels={"env": "production", "model": "multimodal", "dim": "512"}
        )
        
        logger.info(f"✓ Index created: {self.index.resource_name}")
        logger.info(f"  Note: Index build takes 45-90 minutes")
        
        return self.index
    
    def get_or_create_endpoint(
        self,
        endpoint_name: str = None
    ) -> MatchingEngineIndexEndpoint:
        """
        Get existing or create new endpoint
        
        Args:
            endpoint_name: Endpoint display name
            
        Returns:
            MatchingEngineIndexEndpoint
        """
        if not endpoint_name:
            endpoint_name = settings.VS_ENDPOINT_NAME
        
        # Try to find existing endpoint
        logger.info(f"Searching for endpoint: {endpoint_name}")
        endpoints = MatchingEngineIndexEndpoint.list(
            filter=f'display_name="{endpoint_name}"'
        )
        
        if endpoints:
            self.endpoint = endpoints[0]
            logger.info(f"✓ Found existing endpoint: {self.endpoint.resource_name}")
            return self.endpoint
        
        # Create new endpoint
        logger.info(f"Creating new endpoint: {endpoint_name}")
        
        self.endpoint = MatchingEngineIndexEndpoint.create(
            display_name=endpoint_name,
            description="Bringo product similarity endpoint (multimodal 512D)",
            public_endpoint_enabled=True,  # Public for easy access
            labels={"env": "production", "use_case": "product_similarity"}
        )
        
        logger.info(f"✓ Endpoint created: {self.endpoint.resource_name}")
        
        return self.endpoint
    
    def deploy_index(
        self,
        index: MatchingEngineIndex = None,
        endpoint: MatchingEngineIndexEndpoint = None,
        deployed_index_id: str = None
    ):
        """
        Deploy index to endpoint with auto-scaling
        
        Args:
            index: Index to deploy (optional, uses self.index)
            endpoint: Target endpoint (optional, uses self.endpoint)
            deployed_index_id: Deployed index ID
        """
        if not index:
            index = self.index
        if not endpoint:
            endpoint = self.endpoint
        if not deployed_index_id:
            deployed_index_id = settings.VS_DEPLOYED_INDEX_ID
        
        logger.info(f"Deploying index to endpoint...")
        logger.info(f"  - Index: {index.display_name}")
        logger.info(f"  - Endpoint: {endpoint.display_name}")
        logger.info(f"  - Deployed ID: {deployed_index_id}")
        logger.info(f"  - Machine: {settings.VS_MACHINE_TYPE}")
        logger.info(f"  - Replicas: {settings.VS_MIN_REPLICAS}-{settings.VS_MAX_REPLICAS}")
        
        # Deploy with auto-scaling
        endpoint.deploy_index(
            index=index,
            deployed_index_id=deployed_index_id,
            display_name=f"{index.display_name}-deployed",
            machine_type=settings.VS_MACHINE_TYPE,  # e2-standard-2
            min_replica_count=settings.VS_MIN_REPLICAS,  # 1
            max_replica_count=settings.VS_MAX_REPLICAS,  # 2
            enable_access_logging=True,
        )
        
        logger.info(f"✓ Index deployed successfully")
        logger.info(f"  Note: Deployment takes 10-20 minutes")
    
    def wait_for_completion(self, operation, operation_name: str = "Operation"):
        """
        Wait for long-running operation to complete
        
        Args:
            operation: LRO to wait for (or result object if already done)
            operation_name: Name for logging
        """
        # Check if it's actually an LRO
        if not hasattr(operation, 'done'):
            logger.info(f"✓ {operation_name} completed synchronously (or returned result directly).")
            return operation

        logger.info(f"Waiting for {operation_name} to complete...")
        
        start_time = time.time()
        while not operation.done():
            elapsed = time.time() - start_time
            logger.info(f"  ... still running ({elapsed/60:.1f} minutes elapsed)")
            time.sleep(60)  # Check every minute
        
        elapsed = time.time() - start_time
        logger.info(f"✓ {operation_name} completed in {elapsed/60:.1f} minutes")
        
        return operation.result()
    
    def get_existing_index(self, index_name: str) -> MatchingEngineIndex:
        """Get existing index by name"""
        indexes = MatchingEngineIndex.list(
            filter=f'display_name="{index_name}"'
        )
        
        if not indexes:
            raise ValueError(f"Index not found: {index_name}")
        
        return indexes[0]
    
    def get_existing_endpoint(self, endpoint_name: str) -> MatchingEngineIndexEndpoint:
        """Get existing endpoint by name"""
        endpoints = MatchingEngineIndexEndpoint.list(
            filter=f'display_name="{endpoint_name}"'
        )
        
        if not endpoints:
            raise ValueError(f"Endpoint not found: {endpoint_name}")
        
        return endpoints[0]

    def update_index(
        self,
        index_name: str,
        embeddings_gcs_uri: str,
        display_name: str = None
    ):
        """
        Update existing index with new embeddings
        
        Args:
            index_name: Name of the index to update
            embeddings_gcs_uri: GCS URI with new embeddings
            display_name: Optional new display name
        """
        index = self.get_existing_index(index_name)
        
        logger.info(f"Updating index: {index.display_name}")
        logger.info(f"  - New Embeddings: {embeddings_gcs_uri}")
        
        # Update the index
        operation = index.update_embeddings(
            contents_delta_uri=embeddings_gcs_uri,
            is_complete_overwrite=True  # Full refresh
        )
        
        logger.info(f"✓ Index update started")
        return operation
