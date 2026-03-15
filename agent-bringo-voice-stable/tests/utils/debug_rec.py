from data.bigquery_client import BigQueryClient
from vector_search.search_engine import SearchEngine
import pandas as pd

def debug_recommendations():
    bq = BigQueryClient()
    se = SearchEngine()
    
    # 1. Search in BigQuery
    print("\n🔎 Searching BigQuery for 'gelatina'...")
    query = f"SELECT product_id, product_name, category FROM `{bq.table}` WHERE LOWER(product_name) LIKE '%gelatina%'"
    df = bq.client.query(query).to_dataframe()
    print(f"Found {len(df)} products in BigQuery.")
    if not df.empty:
        print(df.head(10))
    
    # 2. Vector Search check
    print("\n🔍 Vector Search for 'gelatina'...")
    results = se.search_by_text('gelatina', num_neighbors=10)
    
    ids = [r['id'] for r in results]
    metadata = bq.get_products_by_ids(ids)
    
    print("Top Vector Search results:")
    for i, r in enumerate(results, 1):
        p = metadata.get(r['id'], {})
        name = p.get('metadata', {}).get('product_name', 'UNKNOWN')
        cat = p.get('metadata', {}).get('category', 'UNKNOWN')
        print(f"{i}. [{r['id']}] {name} (Score: {r['similarity_score']:.4f}) - Cat: {cat}")

if __name__ == "__main__":
    debug_recommendations()
