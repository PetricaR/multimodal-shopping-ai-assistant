import React, { useState } from 'react';
import { Product } from '../types';

interface ProductCardProps {
  product: Product;
  isSubstitution?: boolean;
  onAddToCart?: (product: Product) => void;
  cartQuantity?: number;
  onIncrementQuantity?: (productId: string, productName: string) => void;
  onDecrementQuantity?: (productId: string, productName: string) => void;
  onRemoveFromCart?: (productId: string, productName: string) => void;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  isSubstitution = false,
  onAddToCart,
  cartQuantity = 0,
  onIncrementQuantity,
  onDecrementQuantity,
  onRemoveFromCart
}) => {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [imgError, setImgError] = useState(false);

  // Use the images array if available, otherwise fallback
  const images = product.images && product.images.length > 0 ? product.images : (product.image_url ? [product.image_url] : []);
  const hasMultipleImages = images.length > 1;

  const nextImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setImgError(false);
    setCurrentImageIndex((prev) => (prev + 1) % images.length);
  };

  const prevImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setImgError(false);
    setCurrentImageIndex((prev) => (prev - 1 + images.length) % images.length);
  };

  const placeholder = `https://placehold.co/400x400/1f2937/ffffff?text=${encodeURIComponent(product.product_name.substring(0, 10))}`;
  const activeImage = imgError || images.length === 0
    ? placeholder
    : (images[currentImageIndex] || placeholder);

  return (
    <div className="group relative bg-[#1F2937] rounded-2xl overflow-hidden shadow-lg hover:shadow-2xl hover:shadow-blue-900/20 transition-all duration-300 flex flex-col h-full border border-gray-700/50">

      {/* Image Gallery Area */}
      <div className="relative aspect-square bg-white p-6 flex items-center justify-center overflow-hidden group/carousel">
        <img
          src={activeImage}
          alt={product.product_name}
          onError={() => setImgError(true)}
          className="w-full h-full object-contain transition-transform duration-700 group-hover:scale-110"
        />

        {/* Navigation Arrows */}
        {hasMultipleImages && !imgError && (
          <>
            <button
              onClick={prevImage}
              className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/80 text-white rounded-full p-2 opacity-0 group-hover/carousel:opacity-100 transition-all duration-200 backdrop-blur-md z-20 border border-white/10"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              onClick={nextImage}
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/80 text-white rounded-full p-2 opacity-0 group-hover/carousel:opacity-100 transition-all duration-200 backdrop-blur-md z-20 border border-white/10"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </>
        )}

        {/* Status Overlay */}
        <div className="absolute top-3 left-3 flex flex-col gap-2 z-10">
          {product.in_stock === false && (
            <div className="bg-red-500/90 text-white px-2 py-0.5 rounded-md text-[9px] font-bold shadow-lg backdrop-blur-md">
              STOC EPUIZAT
            </div>
          )}
          {isSubstitution && product.gemini_confidence && (
            <div className="bg-emerald-500/90 text-white px-2 py-0.5 rounded-md text-[9px] font-bold shadow-lg backdrop-blur-md">
              {(product.gemini_confidence * 100).toFixed(0)}% MATCH
            </div>
          )}
        </div>
      </div>

      {/* Product Details */}
      <div className="p-4 flex flex-col flex-grow">
        <div className="flex-grow">
          {/* Brand/Producer */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[9px] font-mono tracking-widest text-blue-400/70 uppercase truncate max-w-[120px]">
              {product.producer || 'Standard Bringo'}
            </span>
            <div className="flex-grow border-t border-white/5"></div>
          </div>

          <h3 className="text-white font-medium text-sm leading-snug line-clamp-2 mb-3 h-[2.5em] group-hover:text-blue-400 transition-colors" title={product.product_name}>
            {product.product_name}
          </h3>

          {/* Optimization Insight */}
          {isSubstitution && product.substitution_reason && (
            <div className="mb-4 bg-blue-500/5 border border-blue-500/20 px-3 py-2 rounded-xl text-[11px] text-blue-200 leading-relaxed font-light italic">
              "{product.substitution_reason}"
            </div>
          )}
        </div>

        {/* Price & Action */}
        <div className="pt-4 mt-auto border-t border-white/5 flex items-center justify-between">
          <div className="flex flex-col">
            <div className="flex items-baseline gap-1">
              <span className="text-xl font-bold text-white tracking-tight">{(product.price ?? 0).toFixed(2)}</span>
              <span className="text-[10px] text-gray-400 font-bold uppercase">RON</span>
            </div>
            {isSubstitution && product.price_difference !== undefined && (
              <span className={`text-[9px] font-bold tracking-tight ${product.price_difference > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                {product.price_difference > 0 ? '↑' : '↓'} {Math.abs(product.price_difference).toFixed(2)} RON
              </span>
            )}
          </div>

          {/* Show quantity controls if item is in cart, otherwise show add button */}
          {cartQuantity > 0 ? (
            <div className="flex items-center gap-2">
              {/* Quantity Controls */}
              <div className="flex items-center gap-1 bg-blue-600/20 rounded-xl p-1 border border-blue-500/30">
                <button
                  onClick={() => onDecrementQuantity?.(product.product_id, product.product_name)}
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-blue-500/30 text-blue-300 transition-all active:scale-95"
                  title="Scade cantitatea"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M20 12H4" />
                  </svg>
                </button>
                <span className="text-sm font-bold text-white w-6 text-center">{cartQuantity}</span>
                <button
                  onClick={() => onIncrementQuantity?.(product.product_id, product.product_name)}
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-blue-500/30 text-blue-300 transition-all active:scale-95"
                  title="Crește cantitatea"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 4v16m8-8H4" />
                  </svg>
                </button>
              </div>
              {/* Remove Button */}
              <button
                onClick={() => onRemoveFromCart?.(product.product_id, product.product_name)}
                className="w-8 h-8 rounded-xl bg-red-500/20 hover:bg-red-500/40 flex items-center justify-center text-red-400 hover:text-red-300 transition-all active:scale-95 border border-red-500/30"
                title="Șterge din coș"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ) : (
            <button
              disabled={product.in_stock === false}
              onClick={() => onAddToCart?.(product)}
              className={`w-10 h-10 rounded-xl flex items-center justify-center shadow-lg transition-all active:scale-95 ${product.in_stock === false
                ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-900/40'
                }`}
              title="Adaugă în coș"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};