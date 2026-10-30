import type { HistoryVideo } from '@/types/api';
import { create } from 'zustand';
import { VideoResult } from '@/types/generationSettings';

interface Txt2VidGalleryState {
  videos: VideoResult[];
  isLoading: boolean;
  currentVideoIndex: number;
  addVideos: (newVideos: VideoResult[]) => void;
  clearVideos: () => void;
  removeVideo: (id: string) => void;
  setLoading: (loading: boolean) => void;
  setCurrentVideoIndex: (index: number) => void;
  loadFromDatabase: () => Promise<void>;
}

export const useTxt2VidGalleryStore = create<Txt2VidGalleryState>((set) => ({
  videos: [],
  isLoading: false,
  currentVideoIndex: 0,
  addVideos: (newVideos) => set((state) => ({
    videos: [...newVideos.filter(newVid => !state.videos.some(vid => vid.url === newVid.url)), ...state.videos],
    isLoading: false,
    currentVideoIndex: 0  // Reset to show new generation
  })),
  clearVideos: () => set({ videos: [], isLoading: false, currentVideoIndex: 0 }),
  removeVideo: (id) => set((state) => ({
    videos: state.videos.filter(vid => vid.id !== id)
  })),
  setLoading: (loading) => set({ isLoading: loading }),
  setCurrentVideoIndex: (index) => set({ currentVideoIndex: index }),
  loadFromDatabase: async () => {
    try {
      set({ isLoading: true });
      const response = await fetch('http://localhost:5009/api/history/txt2vid');
      const data = await response.json();

      if (data.status === 'success' && data.generations) {
        // Convert database format to VideoResult format
        const videos: VideoResult[] = data.generations.map((gen: HistoryVideo) => ({
          id: gen.id,
          url: gen.url,
          filename: gen.filename,
          prompt: gen.prompt || '',
          timestamp: new Date(gen.created_at).getTime(),
          settings: gen.settings
        }));

        set((state) => ({
          videos,
          isLoading: false,
          // Keep current index, but ensure it's valid
          currentVideoIndex: Math.min(state.currentVideoIndex, Math.max(0, videos.length - 1))
        }));
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('[Txt2Vid Store] Error loading from database:', error);
      set({ isLoading: false });
    }
  },
}));
