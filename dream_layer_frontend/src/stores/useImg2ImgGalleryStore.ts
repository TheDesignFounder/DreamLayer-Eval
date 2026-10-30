import type { HistoryImage } from '@/types/api';
import { create } from 'zustand';
import { ImageResult, CoreGenerationSettings, defaultCoreSettings } from '@/types/generationSettings';

interface InputImage {
  url: string;
  file: File;
}

interface Img2ImgGalleryState {
  images: ImageResult[];
  isLoading: boolean;
  currentImageIndex: number;
  inputImage: InputImage | null;
  coreSettings: CoreGenerationSettings;
  customWorkflow: import('@/types/api').CustomWorkflow | null;
  addImages: (newImages: ImageResult[]) => void;
  clearImages: () => void;
  removeImage: (id: string) => void;
  setLoading: (loading: boolean) => void;
  setCurrentImageIndex: (index: number) => void;
  setInputImage: (image: InputImage | null) => void;
  setCustomWorkflow: (workflow: import('@/types/api').CustomWorkflow | null) => void;
  updateCoreSettings: (updates: Partial<CoreGenerationSettings>) => void;
  handlePromptChange: (value: string, isNegative?: boolean) => void;
  handleSamplingSettingsChange: (sampler: string, scheduler: string, steps: number, cfg: number) => void;
  handleSizeSettingsChange: (width: number, height: number) => void;
  handleBatchSettingsChange: (batchCount: number, batchSize: number) => void;
  handleSeedChange: (seed: number, random?: boolean) => void;
  handleDenoisingStrengthChange: (strength: number) => void;
  handleAdvancedSettingsChange: (settings: Partial<CoreGenerationSettings>) => void;
  loadFromDatabase: () => Promise<void>;
}

export const useImg2ImgGalleryStore = create<Img2ImgGalleryState>((set) => ({
  images: [],
  isLoading: false,
  currentImageIndex: 0,
  inputImage: null,
  coreSettings: defaultCoreSettings,
  customWorkflow: null,
  addImages: (newImages) => set((state) => ({
    images: [...newImages, ...state.images],
    currentImageIndex: 0  // Reset to show new generation
  })),
  clearImages: () => set((state) => ({
    images: [],
    isLoading: state.isLoading, // Preserve the current loading state
    currentImageIndex: 0
  })),
  removeImage: (id) => set((state) => ({
    images: state.images.filter(img => img.id !== id)
  })),
  setLoading: (loading) => set({ isLoading: loading }),
  setCurrentImageIndex: (index) => set({ currentImageIndex: index }),
  setInputImage: (image) => set((state) => {
    if (image) {
      // When setting a new input image, also update the input_image field in coreSettings
      const reader = new FileReader();
      reader.onload = () => {
        set((state) => ({
          coreSettings: {
            ...state.coreSettings,
            input_image: reader.result as string
          }
        }));
      };
      reader.readAsDataURL(image.file);
    }
    return { inputImage: image };
  }),
  setCustomWorkflow: (workflow) => set({ customWorkflow: workflow }),
  updateCoreSettings: (updates) => set((state) => ({
    coreSettings: { ...state.coreSettings, ...updates }
  })),
  handlePromptChange: (value, isNegative = false) => set((state) => ({
    coreSettings: {
      ...state.coreSettings,
      [isNegative ? 'negative_prompt' : 'prompt']: value
    }
  })),
  handleSamplingSettingsChange: (sampler, scheduler, steps, cfg) => set((state) => ({
    coreSettings: {
      ...state.coreSettings,
      sampler_name: sampler,
      scheduler: scheduler,
      steps: steps,
      cfg_scale: cfg
    }
  })),
  handleSizeSettingsChange: (width, height) => set((state) => ({
    coreSettings: {
      ...state.coreSettings,
      width,
      height
    }
  })),
  handleBatchSettingsChange: (batchCount, batchSize) => set((state) => ({
    coreSettings: {
      ...state.coreSettings,
      batch_count: batchCount,
      batch_size: batchSize
    }
  })),
  handleSeedChange: (seed, random = true) => set((state) => ({
    coreSettings: {
      ...state.coreSettings,
      seed,
      random_seed: random
    }
  })),
  handleDenoisingStrengthChange: (strength) => set((state) => ({
    coreSettings: {
      ...state.coreSettings,
      denoising_strength: Math.max(0, Math.min(1, strength))
    }
  })),
  handleAdvancedSettingsChange: (settings) => set((state) => ({
    coreSettings: {
      ...state.coreSettings,
      ...settings
    }
  })),
  loadFromDatabase: async () => {
    try {
      set({ isLoading: true });
      const response = await fetch('http://localhost:5009/api/history/img2img');
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
      console.error('[Img2Img Store] Error loading from database:', error);
      set({ isLoading: false });
    }
  }
}));
