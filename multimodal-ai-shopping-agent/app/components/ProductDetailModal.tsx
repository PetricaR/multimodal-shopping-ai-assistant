import React, { useState, useEffect } from 'react';
import { Product } from '../types';

interface ProductDetailModalProps {
  product: Product;
  isSubstitution?: boolean;
  cartQuantity?: number;
  onClose: () => void;
  onAddToCart?: (product: Product) => void;
  onIncrementQuantity?: (productId: string, productName: string) => void;
  onDecrementQuantity?: (productId: string, productName: string) => void;
}

export const ProductDetailModal: React.FC<ProductDetailModalProps> = ({
  product,
  isSubstitution = false,
  cartQuantity = 0,
  onClose,
  onAddToCart,
  onIncrementQuantity,
  onDecrementQuantity,
}) => {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [imgError, setImgError] = useState(false);

  const images = product.images && product.images.length > 0
    ? product.images
    : product.image_url ? [product.image_url] : [];
  const hasMultipleImages = images.length > 1;

  const placeholder = `https://placehold.co/400x400/1f2937/ffffff?text=${encodeURIComponent(product.product_name.substring(0, 10))}`;
  const activeImage = imgError || images.length === 0
    ? placeholder
    : (images[currentImageIndex] || placeholder);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const nextImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setImgError(false);
    setCurrentImageIndex((prev) => (prev + 1) % images.length);
  };

  const prevImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setImgError(false);
    setCurrentImageIndex((prev) => (prev - 1 + images.length) % images.length);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in"
      onClick={onClose}
    >
      <div
        className="relative bg-[#1a1f2e] rounded-2xl overflow-hidden shadow-2xl border border-white/10 w-[340px] max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-20 w-8 h-8 rounded-full bg-black/50 hover:bg-black/80 flex items-center justify-center text-white/70 hover:text-white transition-colors backdrop-blur-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="relative bg-white p-6 flex items-center justify-center h-[240px]">
          <img
            src={activeImage}
            alt={product.product_name}
            onError={() => setImgError(true)}
            className="h-full w-full object-contain"
          />
          {hasMultipleImages && !imgError && (
            <>
              <button onClick={prevImage} className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/70 text-white rounded-full p-2 transition-colors backdrop-blur-sm">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
              </button>
              <button onClick={nextImage} className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/70 text-white rounded-full p-2 transition-colors backdrop-blur-sm">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
              </button>
            </>
          )}
          {hasMultipleImages && (
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
              {images.map((_, i) => (
                <div key={i} className={`w-1.5 h-1.5 rounded-full transition-colors ${i === currentImageIndex ? 'bg-blue-500' : 'bg-gray-400/50'}`} />
              ))}
            </div>
          )}
          <div className="absolute top-3 left-3 flex flex-col gap-1.5">
            {product.in_stock === false && (
              <div className="bg-red-500/90 text-white px-2.5 py-1 rounded-lg text-[10px] font-bold shadow-lg backdrop-blur-sm">OUT OF STOCK</div>
            )}
            {isSubstitution && product.gemini_confidence && (
              <div className="bg-emerald-500/90 text-white px-2.5 py-1 rounded-lg text-[10px] font-bold shadow-lg backdrop-blur-sm">
                {(product.gemini_confidence * 100).toFixed(0)}% MATCH
              </div>
            )}
          </div>
        </div>

        <div className="p-5 space-y-3">
          {product.producer && (
            <span className="text-[10px] font-mono tracking-widest text-blue-400/70 uppercase">{product.producer}</span>
          )}
          <h2 className="text-white font-semibold text-base leading-snug">{product.product_name}</h2>
          {product.category && (
            <span className="inline-block text-[10px] text-gray-400 bg-white/5 px-2 py-0.5 rounded-full">{product.category}</span>
          )}
          {isSubstitution && product.substitution_reason && (
            <div className="bg-blue-500/10 border border-blue-500/20 px-3 py-2 rounded-xl text-[11px] text-blue-200 leading-relaxed italic">
              "{product.substitution_reason}"
            </div>
          )}
          <div className="flex items-center justify-between pt-3 border-t border-white/10">
            <div>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-bold text-white tracking-tight">{product.price.toFixed(2)}</span>
                <span className="text-xs text-gray-400 font-semibold">RON</span>
              </div>
              {isSubstitution && product.price_difference !== undefined && (
                <span className={`text-[10px] font-bold ${product.price_difference > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                  {product.price_difference > 0 ? '↑' : '↓'} {Math.abs(product.price_difference).toFixed(2)} RON
                </span>
              )}
              {product.in_stock !== false && (
                <div className="flex items-center gap-1 mt-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span className="text-[10px] text-emerald-400/80">In stock</span>
                </div>
              )}
            </div>
            {cartQuantity > 0 ? (
              <div className="flex items-center gap-1 bg-blue-600/20 rounded-xl p-1 border border-blue-500/30">
                <button onClick={() => onDecrementQuantity?.(product.product_id, product.product_name)} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-blue-500/30 text-blue-300 transition-all active:scale-95">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M20 12H4" /></svg>
                </button>
                <span className="text-sm font-bold text-white w-6 text-center">{cartQuantity}</span>
                <button onClick={() => onIncrementQuantity?.(product.product_id, product.product_name)} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-blue-500/30 text-blue-300 transition-all active:scale-95">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 4v16m8-8H4" /></svg>
                </button>
              </div>
            ) : (
              <button
                disabled={product.in_stock === false}
                onClick={() => onAddToCart?.(product)}
                className={`px-5 py-2.5 rounded-xl font-semibold text-sm transition-all active:scale-95 ${product.in_stock === false ? 'bg-gray-800 text-gray-500 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/30'}`}
              >
                Add to cart
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
