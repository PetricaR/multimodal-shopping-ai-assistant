import React, { useState } from 'react';
import { Product } from '../types';

interface CompactProductCardProps {
  product: Product;
  isSubstitution?: boolean;
  onAddToCart?: (product: Product) => void;
  onProductClick?: (product: Product) => void;
  cartQuantity?: number;
  onIncrementQuantity?: (productId: string, productName: string) => void;
  onDecrementQuantity?: (productId: string, productName: string) => void;
  animationIndex?: number;
}

export const CompactProductCard: React.FC<CompactProductCardProps> = ({
  product,
  isSubstitution = false,
  onAddToCart,
  onProductClick,
  cartQuantity = 0,
  onIncrementQuantity,
  onDecrementQuantity,
  animationIndex = 0,
}) => {
  const [imgError, setImgError] = useState(false);

  const imageUrl = product.images?.[0] || product.image_url;

  // Hide this card entirely if the image is missing or fails to load
  if (!imageUrl || imgError) return null;

  return (
    <div
      className="w-[180px] flex-shrink-0 bg-[#1F2937] rounded-xl overflow-hidden border border-gray-700/50 hover:border-blue-500/40 transition-all cursor-pointer card-reveal"
      style={{ animationDelay: `${animationIndex * 55}ms` }}
      onClick={() => onProductClick?.(product)}
    >
      <div className="relative h-24 bg-white flex items-center justify-center p-2">
        <img
          src={imageUrl}
          alt={product.product_name}
          onError={() => setImgError(true)}
          className="h-full w-full object-contain"
          loading="lazy"
        />
        {product.in_stock === false && (
          <div className="absolute top-1 left-1 bg-red-500/90 text-white px-1.5 py-0.5 rounded text-[8px] font-bold">OUT OF STOCK</div>
        )}
        {isSubstitution && product.gemini_confidence && (
          <div className="absolute top-1 right-1 bg-emerald-500/90 text-white px-1.5 py-0.5 rounded text-[8px] font-bold">
            {(product.gemini_confidence * 100).toFixed(0)}%
          </div>
        )}
      </div>
      <div className="p-2.5">
        {product.producer && (
          <p className="text-[8px] font-mono tracking-wider text-blue-400/60 uppercase truncate mb-0.5">{product.producer}</p>
        )}
        <h4 className="text-white text-xs font-medium leading-tight line-clamp-2 h-[2.2em] mb-2" title={product.product_name}>
          {product.product_name}
        </h4>
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-bold text-white">{(product.price ?? 0).toFixed(2)}</span>
            <span className="text-[8px] text-gray-400 ml-0.5">RON</span>
          </div>
          {cartQuantity > 0 ? (
            <div className="flex items-center gap-0.5 bg-blue-600/20 rounded-lg p-0.5 border border-blue-500/30">
              <button
                onClick={(e) => { e.stopPropagation(); onDecrementQuantity?.(product.product_id, product.product_name); }}
                className="w-5 h-5 flex items-center justify-center rounded text-blue-300 hover:bg-blue-500/30 transition-all"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M20 12H4" /></svg>
              </button>
              <span className="text-[10px] font-bold text-white w-4 text-center">{cartQuantity}</span>
              <button
                onClick={(e) => { e.stopPropagation(); onIncrementQuantity?.(product.product_id, product.product_name); }}
                className="w-5 h-5 flex items-center justify-center rounded text-blue-300 hover:bg-blue-500/30 transition-all"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 4v16m8-8H4" /></svg>
              </button>
            </div>
          ) : (
            <button
              disabled={product.in_stock === false}
              onClick={(e) => { e.stopPropagation(); onAddToCart?.(product); }}
              className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all active:scale-95 ${product.in_stock === false ? 'bg-gray-800 text-gray-500 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
              title="Add to cart"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
