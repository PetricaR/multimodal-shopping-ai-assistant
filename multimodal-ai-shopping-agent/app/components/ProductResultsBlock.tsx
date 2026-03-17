import React, { useRef, useState } from 'react';
import { BasketItem, Product } from '../types';
import { CompactProductCard } from './CompactProductCard';
import { ProductDetailModal } from './ProductDetailModal';

interface ProductQueryGroup {
  query: string;
  products: Product[];
}

interface ProductResultsBlockProps {
  queryGroups: ProductQueryGroup[];
  isSubstitution: boolean;
  cartItems: BasketItem[];
  onAddToCart: (product: Product) => void;
  onIncrementQuantity: (productId: string, productName: string) => void;
  onDecrementQuantity: (productId: string, productName: string) => void;
}

export const ProductResultsBlock: React.FC<ProductResultsBlockProps> = ({
  queryGroups,
  isSubstitution,
  cartItems,
  onAddToCart,
  onIncrementQuantity,
  onDecrementQuantity,
}) => {
  const scrollContainerRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  const scrollGallery = (index: number, direction: 'left' | 'right') => {
    const container = scrollContainerRefs.current[index];
    if (!container) return;
    container.scrollBy({ left: direction === 'right' ? 300 : -300, behavior: 'smooth' });
  };

  if (!queryGroups || queryGroups.length === 0) return null;

  let globalCardIndex = 0;

  return (
    <div className="max-w-[95%] rounded-2xl px-4 py-3 bg-white border border-gray-200 rounded-bl-md space-y-4">
      {queryGroups.map((group, idx) => (
        <div key={`${group.query}-${idx}`}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-semibold text-gray-700">
              {isSubstitution ? 'Substitutions for' : 'Results for'}
            </span>
            <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
              "{group.query}"
            </span>
            <span className="text-[10px] text-gray-400">
              {group.products.length} {group.products.length === 1 ? 'product' : 'products'}
            </span>
          </div>

          {group.products.length > 0 ? (
            <div className="relative group/gallery">
              <button
                onClick={() => scrollGallery(idx, 'left')}
                className="absolute left-0 top-1/2 -translate-y-1/2 z-10 bg-white/90 hover:bg-white border border-gray-300 rounded-full p-2 shadow-lg opacity-0 group-hover/gallery:opacity-100 transition-opacity duration-200"
              >
                <svg className="w-4 h-4 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>

              <div
                ref={(el) => { scrollContainerRefs.current[idx] = el; }}
                className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent"
              >
                {group.products
                  .filter(product => !!(product.images?.[0] || product.image_url))
                  .slice(0, 10)
                  .map((product) => {
                  const cartItem = cartItems.find(c => c.product_id === product.product_id);
                  const cardIndex = globalCardIndex++;
                  return (
                    <CompactProductCard
                      key={product.product_id}
                      product={product}
                      isSubstitution={isSubstitution}
                      onAddToCart={onAddToCart}
                      onProductClick={setSelectedProduct}
                      cartQuantity={cartItem?.quantity || 0}
                      onIncrementQuantity={onIncrementQuantity}
                      onDecrementQuantity={onDecrementQuantity}
                      animationIndex={cardIndex}
                    />
                  );
                })}
              </div>

              <button
                onClick={() => scrollGallery(idx, 'right')}
                className="absolute right-0 top-1/2 -translate-y-1/2 z-10 bg-white/90 hover:bg-white border border-gray-300 rounded-full p-2 shadow-lg opacity-0 group-hover/gallery:opacity-100 transition-opacity duration-200"
              >
                <svg className="w-4 h-4 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          ) : (
            <p className="text-xs text-gray-400 italic">No products found</p>
          )}
        </div>
      ))}

      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          isSubstitution={isSubstitution}
          cartQuantity={cartItems.find(c => c.product_id === selectedProduct.product_id)?.quantity || 0}
          onClose={() => setSelectedProduct(null)}
          onAddToCart={onAddToCart}
          onIncrementQuantity={onIncrementQuantity}
          onDecrementQuantity={onDecrementQuantity}
        />
      )}
    </div>
  );
};
