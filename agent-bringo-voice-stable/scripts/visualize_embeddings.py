#!/usr/bin/env python3
"""
Visualize Product Embeddings
Creates an interactive 3D scatter plot of the embedding space.

Usage:
    uv run --with scikit-learn --with plotly scripts/visualize_embeddings.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import storage
from config.settings import settings
import json
import logging
import pandas as pd
import numpy as np

# These will be imported dynamically or expected to be present
try:
    from sklearn.decomposition import PCA
    from sklearn.manifold import TSNE
    import plotly.express as px
except ImportError:
    print("❌ Missing dependencies! Run with:")
    print("   uv run --with scikit-learn --with plotly scripts/visualize_embeddings.py")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

def load_embeddings():
    """Download and load embeddings from GCS"""
    logger.info("⬇️  Downloading embeddings from GCS...")
    
    storage_client = storage.Client(project=settings.PROJECT_ID)
    bucket = storage_client.bucket(settings.STAGING_BUCKET)
    blob = bucket.blob("embeddings/bringo_products_embeddings.json")
    
    if not blob.exists():
        logger.error("❌ Embeddings file not found.")
        sys.exit(1)
        
    content = blob.download_as_text()
    lines = content.strip().split('\n')
    
    data = []
    vectors = []
    
    logger.info(f"   Parsing {len(lines)} records...")
    
    for line in lines:
        try:
            record = json.loads(line)
            # Embeddings format: {'id': '...', 'embedding': [...], 'metadata': {...}}
            # But generate_embeddings might output slightly different structure?
            # Let's check based on batch_processor.py structure
            # Structure is: {"id": "...", "embedding": [...], "restricts": [...] (maybe)}
            
            # The generate_embeddings.py output likely contains metadata if configured?
            # Actually, typically vector search format is simple.
            # But let's hope we have metadata for coloring.
            # If not, we might need to fetch it or rely on ID if it's "Name".
            
            vec = record.get('embedding')
            pid = record.get('id')
            
            if vec and pid:
                vectors.append(vec)
                
                # Check for metadata
                # Usually we don't put rich metadata in the vector file for index creation...
                # ...Wait, verify_embeddings.py was checking headers.
                # If no metadata in file, we can't color by category easily.
                # But 'id' is the Product Name.
                
                label = str(pid)
                category = "Unknown"
                
                # Try simple heuristic for category if missing
                # e.g., "Lapte Zuzu" -> "Lapte" (just first word as naive category if nothing else)
                if len(label.split()) > 0:
                    heuristic_cat = label.split()[0]
                else:
                    heuristic_cat = "Unknown"
                    
                data.append({
                    "Product Name": label,
                    "Category Hint": heuristic_cat
                })
                
        except Exception:
            continue
            
    return np.array(vectors), pd.DataFrame(data)

def reduce_dimensions(vectors):
    """Reduce dimensions for visualization"""
    n_samples = vectors.shape[0]
    
    logger.info(f"🔄 Reducing dimensions for {n_samples} vectors...")
    
    # 1. PCA to 50 dimensions (fast initialization for t-SNE)
    logger.info("   Running PCA (512 -> 50)...")
    pca = PCA(n_components=min(50, n_samples))
    pca_result = pca.fit_transform(vectors)
    logger.info(f"   PCA Explained Variance: {sum(pca.explained_variance_ratio_):.2f}")
    
    # 2. t-SNE to 3 dimensions (visualization)
    logger.info("   Running t-SNE (50 -> 3)...")
    tsne = TSNE(
        n_components=3, 
        verbose=1, 
        perplexity=min(30, n_samples - 1), 
        n_iter=1000, 
        random_state=42
    )
    tsne_results = tsne.fit_transform(pca_result)
    
    return tsne_results

def create_visualization(vectors_3d, metadata_df):
    """Create interactive Plotly chart"""
    logger.info("🎨 Creating interactive 3D chart...")
    
    metadata_df['x'] = vectors_3d[:, 0]
    metadata_df['y'] = vectors_3d[:, 1]
    metadata_df['z'] = vectors_3d[:, 2]
    
    fig = px.scatter_3d(
        metadata_df, 
        x='x', y='y', z='z',
        color='Category Hint', # Naive clustering color
        hover_name='Product Name',
        title='Bringo Product Embeddings (3D t-SNE)',
        opacity=0.7,
        size_max=5
    )
    
    fig.update_traces(marker=dict(size=3))
    fig.update_layout(margin=dict(l=0, r=0, b=0, t=30))
    
    output_file = "embeddings_visualization.html"
    fig.write_html(output_file)
    logger.info(f"✅ Saved visualization to: {output_file}")
    
def main():
    logger.info("=== Embedding Visualization Generator ===")
    
    vectors, df = load_embeddings()
    if len(vectors) == 0:
        logger.error("No vectors found.")
        return
        
    vectors_3d = reduce_dimensions(vectors)
    create_visualization(vectors_3d, df)

if __name__ == "__main__":
    main()
