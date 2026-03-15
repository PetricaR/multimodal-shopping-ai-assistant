"""
BigQuery client for fetching and preprocessing Bringo product data
Following Google best practices for data preparation
"""
from google.cloud import bigquery
from google.auth import default
from typing import List, Dict, Optional
import pandas as pd
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

# BigQuery + Drive scopes for accessing Drive-linked external tables
SCOPES = [
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/drive.readonly",
]

class BigQueryClient:
    """
    Fetch and preprocess product data from BigQuery
    """
    
    def __init__(self):
        # Get credentials with Drive scope for external table access
        credentials, project = default(scopes=SCOPES)
        self.client = bigquery.Client(credentials=credentials, project=settings.PROJECT_ID)
        # Use unique view if available to prevent duplicates, otherwise native
        self.dataset = f"{settings.PROJECT_ID}.{settings.BQ_DATASET}"
        self.table = f"{self.dataset}.{settings.BQ_TABLE}"
        self.view_unique = f"{self.dataset}.bringo_products_unique_ids_view"
        
        # In-memory cache for product metadata
        self._cache = {}
        
        logger.info(f"✓ Initialized BigQuery client for {self.table}")

    def _get_from_cache(self, product_id: str) -> Optional[Dict]:
        return self._cache.get(str(product_id))

    def _add_to_cache(self, product: Dict):
        if product and 'product_id' in product:
            self._cache[str(product['product_id'])] = product

    def get_existing_product_ids(self) -> set:
        """Fetch all existing product IDs from BigQuery for deduplication"""
        query = f"SELECT product_id FROM `{self.table}`"
        logger.info(f"Fetching existing product IDs from {self.table}...")
        df = self.client.query(query).to_dataframe()
        if not df.empty:
            return set(df['product_id'].astype(str).tolist())
        return set()

    def insert_products_df(self, df: pd.DataFrame) -> int:
        """
        Insert new products DataFrame directly into BigQuery (Append)
        """
        if df.empty:
            return 0
            
        logger.info(f"Inserting {len(df)} rows into {self.table}...")
        
        # Configure load job for appending
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
            autodetect=True 
        )
        
        job = self.client.load_table_from_dataframe(df, self.table, job_config=job_config)
        job.result()  # Wait for completion
        
        logger.info(f"✓ Successfully inserted {len(df)} rows.")
        return len(df)

    def _combine_text_fields(self, row: pd.Series) -> str:
        """Combine product text fields into rich description"""
        parts = []
        if pd.notna(row.get('product_name')): parts.append(str(row['product_name']))
        if pd.notna(row.get('category')): parts.append(f"Categorie: {row['category']}")
        if pd.notna(row.get('producer')): parts.append(f"Producător: {row['producer']}")
        
        if pd.notna(row.get('description')):
            desc = str(row['description']).strip()
            if desc and desc != 'nan': parts.append(desc)
            
        if pd.notna(row.get('ingredients')):
            ingr = str(row['ingredients']).strip()
            if ingr and ingr != 'nan': parts.append(f"Ingrediente: {ingr}")
            
        if pd.notna(row.get('country_origin')):
            parts.append(f"Origine: {row['country_origin']}")
            
        combined = "\n".join(parts) if parts else ""
        if len(combined) > 1000:
            combined = combined[:997] + "..."
        return combined

    def _normalize_image_url(self, url: Optional[str]) -> Optional[str]:
        """Normalize image URL by ensuring it's absolute"""
        if not url or pd.isna(url):
            return None
        if url.startswith('/'):
            return f"https://www.bringo.ro{url}"
        return url

    def fetch_products(self, limit: Optional[int] = None, in_stock_only: bool = False) -> pd.DataFrame:
        """
        Fetch products from BigQuery using the deduplicated VIEW to ensure
        consistency with Feature Store (which requires unique Entity IDs).
        """
        table_to_query = self.view_unique or self.table
        logger.info(f"Using source table/view: {table_to_query}")
        
        query = f"SELECT * FROM `{table_to_query}` WHERE product_name IS NOT NULL"
        if in_stock_only: query += " AND in_stock = TRUE"
        if limit: query += f" LIMIT {limit}"
        
        logger.info(f"Fetching products from BigQuery...")
        df = self.client.query(query).to_dataframe()
        
        if 'image_url' in df.columns:
            df['image_url'] = df['image_url'].apply(self._normalize_image_url)
            
        return df

    def prepare_for_embedding(self, df: pd.DataFrame) -> List[Dict[str, any]]:
        products = []
        for _, row in df.iterrows():
            combined_text = self._combine_text_fields(row)
            if not combined_text: continue
            
            product = {
                'product_id': str(row['product_id']),
                'combined_text': combined_text,
                'image_url': self._normalize_image_url(row.get('image_url')),
                'metadata': {
                    'product_name': str(row.get('product_name', '')),
                    'category': str(row.get('category', '')),
                    'producer': str(row.get('producer', '')),
                    'in_stock': bool(row.get('in_stock', False)),
                    'price': float(row.get('price_ron', 0.0)) if pd.notna(row.get('price_ron')) else None,
                    'variant_id': str(row.get('variant_id')) if pd.notna(row.get('variant_id')) else None,
                }
            }
            products.append(product)
            self._add_to_cache(product)
        return products

    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        cached = self._get_from_cache(product_id)
        if cached: return cached
            
        query = f"SELECT * FROM `{self.table}` WHERE product_id = @product_id LIMIT 1"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("product_id", "INT64", int(product_id))]
        )
        df = self.client.query(query, job_config=job_config).to_dataframe()
        if df.empty: return None
        
        row = df.iloc[0]
        product = {
            'product_id': str(row['product_id']),
            'combined_text': self._combine_text_fields(row),
            'image_url': self._normalize_image_url(row.get('image_url')),
            'metadata': {
                'product_name': str(row.get('product_name', '')),
                'category': str(row.get('category', '')),
                'producer': str(row.get('producer', '')),
                'in_stock': bool(row.get('in_stock', False)),
                'price': float(row.get('price_ron', 0.0)) if pd.notna(row.get('price_ron')) else None,
                'variant_id': str(row.get('variant_id')) if pd.notna(row.get('variant_id')) else None,
            }
        }
        self._add_to_cache(product)
        return product

    def get_products_by_ids(self, product_ids: List[str]) -> Dict[str, Dict]:
        if not product_ids: return {}
        results = {}
        missing_ids = []
        for pid in product_ids:
            cached = self._get_from_cache(pid)
            if cached: results[str(pid)] = cached
            else: missing_ids.append(pid)

        if not missing_ids: return results

        query = f"SELECT * FROM `{self.table}` WHERE product_id IN UNNEST(@product_ids)"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("product_ids", "INT64", [int(pid) for pid in missing_ids])]
        )
        df = self.client.query(query, job_config=job_config).to_dataframe()

        for _, row in df.iterrows():
            product = {
                'product_id': str(row['product_id']),
                'combined_text': self._combine_text_fields(row),
                'image_url': self._normalize_image_url(row.get('image_url')),
                'metadata': {
                    'product_name': str(row.get('product_name', '')),
                    'category': str(row.get('category', '')),
                    'producer': str(row.get('producer', '')),
                    'in_stock': bool(row.get('in_stock', False)),
                    'price': float(row.get('price_ron', 0.0)) if pd.notna(row.get('price_ron')) else None,
                    'variant_id': str(row.get('variant_id')) if pd.notna(row.get('variant_id')) else None,
                }
            }
            results[product['product_id']] = product
            self._add_to_cache(product)
        return results

    def get_products_by_name(self, product_name: str, limit: int = 10, exact_match: bool = False) -> List[Dict]:
        """
        Search products by name

        Args:
            product_name: Product name to search for
            limit: Maximum number of results (default 10)
            exact_match: If True, search for exact match; if False, use LIKE search (default False)

        Returns:
            List of matching products
        """
        if exact_match:
            query = f"SELECT * FROM `{self.table}` WHERE LOWER(product_name) = LOWER(@product_name) LIMIT {limit}"
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("product_name", "STRING", product_name)]
            )
        else:
            # Use LIKE for partial matching
            query = f"SELECT * FROM `{self.table}` WHERE LOWER(product_name) LIKE LOWER(@product_name) LIMIT {limit}"
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("product_name", "STRING", f"%{product_name}%")]
            )

        logger.info(f"Searching products by name: {product_name} (exact_match={exact_match})")
        df = self.client.query(query, job_config=job_config).to_dataframe()

        if df.empty:
            logger.info(f"No products found matching: {product_name}")
            return []

        results = []
        for _, row in df.iterrows():
            product = {
                'product_id': str(row['product_id']),
                'combined_text': self._combine_text_fields(row),
                'image_url': self._normalize_image_url(row.get('image_url')),
                'metadata': {
                    'product_name': str(row.get('product_name', '')),
                    'category': str(row.get('category', '')),
                    'producer': str(row.get('producer', '')),
                    'in_stock': bool(row.get('in_stock', False)),
                    'price': float(row.get('price_ron', 0.0)) if pd.notna(row.get('price_ron')) else None,
                    'variant_id': str(row.get('variant_id')) if pd.notna(row.get('variant_id')) else None,
                }
            }
            results.append(product)
            self._add_to_cache(product)

        logger.info(f"Found {len(results)} products matching: {product_name}")
        return results

    def get_products_by_names(self, product_names: List[str]) -> Dict[str, Dict]:
        """
        Batch fetch products by their names.
        Used for enriching Vector Search results where datapoint_id = product_name.

        Args:
            product_names: List of product names to fetch

        Returns:
            Dict mapping product_name -> product data
        """
        if not product_names:
            return {}

        # Filter out empty/null names
        valid_names = [n for n in product_names if n and n.strip()]
        if not valid_names:
            return {}

        query = f"SELECT * FROM `{self.table}` WHERE product_name IN UNNEST(@product_names)"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("product_names", "STRING", valid_names)]
        )

        logger.info(f"Batch fetching {len(valid_names)} products by name...")
        df = self.client.query(query, job_config=job_config).to_dataframe()

        results = {}
        for _, row in df.iterrows():
            pname = str(row.get('product_name', ''))
            product = {
                'product_id': str(row['product_id']),
                'combined_text': self._combine_text_fields(row),
                'image_url': self._normalize_image_url(row.get('image_url')),
                'metadata': {
                    'product_name': pname,
                    'category': str(row.get('category', '')),
                    'producer': str(row.get('producer', '')),
                    'in_stock': bool(row.get('in_stock', False)),
                    'price': float(row.get('price_ron', 0.0)) if pd.notna(row.get('price_ron')) else None,
                    'variant_id': str(row.get('variant_id')) if pd.notna(row.get('variant_id')) else None,
                }
            }
            results[pname] = product
            self._add_to_cache(product)

        logger.info(f"✓ Batch fetched {len(results)} products by name")
        return results

    def save_embeddings_metadata(self, embeddings_data: List[Dict], output_table: str = None):
        if not output_table:
            output_table = f"{settings.PROJECT_ID}.{settings.BQ_OUTPUT_DATASET}.embeddings_metadata"
        df = pd.DataFrame(embeddings_data)
        job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
        job = self.client.load_table_from_dataframe(df, output_table, job_config=job_config)
        job.result()

    def load_csv_to_bq(self, csv_path: str, table_id: str = None) -> int:
        """
        Load CSV file into BigQuery table
        
        Args:
            csv_path: Path to CSV file
            table_id: Target table ID (default: settings.BQ_TABLE)
            
        Returns:
            Number of rows loaded
        """
        if not table_id:
            table_id = self.table
            
        logger.info(f"Loading CSV data from {csv_path} into {table_id}...")
        
        try:
            # Load CSV into pandas first to handle schema/cleaning if needed
            df = pd.read_csv(csv_path, sep=';')
            
            # Basic validation/cleaning
            if 'price_ron' not in df.columns and 'price_(ron)' in df.columns:
                df.rename(columns={'price_(ron)': 'price_ron'}, inplace=True)
                
            # Configure load job
            job_config = bigquery.LoadJobConfig(
                # For full pipeline sync, we likely want TRUNCATE to replace old data with fresh scrape
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                source_format=bigquery.SourceFormat.CSV,
                autodetect=True,
            )
            
            job = self.client.load_table_from_dataframe(df, table_id, job_config=job_config)
            job.result()  # Wait for job to complete
            
            table = self.client.get_table(table_id)
            logger.info(f"✓ Loaded {table.num_rows} rows into {table_id}")
            return table.num_rows
            
        except Exception as e:
            logger.error(f"Failed to load CSV to BigQuery: {e}")
            raise


