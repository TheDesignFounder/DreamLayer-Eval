import type { HistoryImage } from '@/types/api';
import { create } from 'zustand';
import { ImageResult } from '@/types/imageResult';

interface Txt2ImgGalleryState {
  images: ImageResult[];
  isLoading: boolean;
  currentImageIndex: number;
  addImages: (newImages: ImageResult[]) => void;
  clearImages: () => void;
  removeImage: (id: string) => void;
  setLoading: (loading: boolean) => void;
  setCurrentImageIndex: (index: number) => void;
  loadFromDatabase: () => Promise<void>;
}

export const useTxt2ImgGalleryStore = create<Txt2ImgGalleryState>((set) => ({
  images: [],
  isLoading: false,
  currentImageIndex: 0,
  addImages: (newImages) => set((state) => ({
    images: [...newImages.filter(newImg => !state.images.some(img => img.url === newImg.url)), ...state.images],
    isLoading: false,
    currentImageIndex: 0  // Reset to show new generation
  })),
  clearImages: () => set({ images: [], isLoading: false, currentImageIndex: 0 }),
  removeImage: (id) => set((state) => ({
    images: state.images.filter(img => img.id !== id)
  })),
  setLoading: (loading) => set({ isLoading: loading }),
  setCurrentImageIndex: (index) => set({ currentImageIndex: index }),
  loadFromDatabase: async () => {
    try {
      set({ isLoading: true });
      const response = await fetch('http://localhost:5009/api/history/txt2img');
      const data = await response.json();

      if (data.status === 'success' && data.generations) {
        // Convert database format to ImageResult format
        const images: ImageResult[] = data.generations.map((gen: HistoryImage) => ({
          id: gen.id,
          url: gen.url,
          prompt: gen.prompt || '',
          negativePrompt: gen.negative_prompt || '',
          timestamp: new Date(gen.created_at).getTime(),
          settings: gen.settings
        }));

        set((state) => ({
          images,
          isLoading: false,
          // Keep current index, but ensure it's valid
          currentImageIndex: Math.min(state.currentImageIndex, Math.max(0, images.length - 1))
        }));
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('[Txt2Img Store] Error loading from database:', error);
      set({ isLoading: false });
    }
  },
}));
