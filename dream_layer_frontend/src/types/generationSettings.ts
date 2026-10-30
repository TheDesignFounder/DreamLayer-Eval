import { ControlNetRequest } from './controlnet';
import { LoraRequest } from './lora';

export interface CoreGenerationSettings {
  // Basic Settings
  prompt: string;
  negative_prompt: string;
  model_name: string;
  lora: LoraRequest | null;  // LoRA configuration, null if none selected

  // Sampling Settings
  sampler_name: string;  // e.g., "euler", "dpm++", etc.
  scheduler: string;     // e.g., "normal", "karras", etc.
  steps: number;         // Range: 1-150, Default: 20
  cfg_scale: number;     // Range: 1-20, Default: 7.0
  denoising_strength?: number; // Range: 0-1, Default: 0.75 (for img2img)

  // Size Settings
  width: number;         // Range: 64-2048, Default: 512
  height: number;        // Range: 64-2048, Default: 512
  resize_mode?: string;  // e.g., "just_resize", "crop_and_resize", "fill"

  // Batch Settings
  batch_size: number;    // Default: 1
  batch_count: number;   // Default: 1

  // Seed Settings
  seed: number;         // -1 for random, or specific seed value
  random_seed: boolean; // Whether to use random seed each time

  // Image Input Settings (for img2img)
  input_image?: string;  // Base64 encoded image data
  mask?: string;        // Base64 encoded mask data for inpainting

  // Advanced Settings
  vae_name?: string;    // Name of the VAE model to use
  clip_skip?: number;   // Number of CLIP layers to skip
  tiling?: boolean;     // Enable seamless tiling
  tile_size?: number;   // Tile size for tiling (default: 512)
  tile_overlap?: number; // Overlap between tiles (default: 64)
  hires_fix?: boolean;  // Enable hires fix
  karras_sigmas?: boolean; // Use Karras sigmas scheduling

  // Hires.fix Settings
  hires_fix_enabled?: boolean;        // Enable hires fix
  hires_fix_upscale_method?: string;  // "upscale-by" or "resize-to"
  hires_fix_upscale_factor?: number;  // Range: 1-10, Default: 2.5
  hires_fix_hires_steps?: number;     // Range: 1-30, Default: 15
  hires_fix_denoising_strength?: number; // Range: 0-1, Default: 0.5
  hires_fix_resize_width?: number;    // Range: 64-8192, Default: 4000
  hires_fix_resize_height?: number;   // Range: 64-8192, Default: 4000
  hires_fix_upscaler?: string;        // Upscaler model name, Default: "4x-ultrasharp"

  // Face Restoration Settings
  restore_faces?: boolean;        // Enable face restoration
  face_restoration_model?: string; // "codeformer" or "gfpgan"
  codeformer_weight?: number;     // Range: 0-1, Default: 0.5
  gfpgan_weight?: number;         // Range: 0-1, Default: 0.5

  // Refiner Settings
  refiner_enabled?: boolean;
  refiner_model?: string;
  refiner_switch_at?: number;
}

// Default values for core generation settings
export const defaultCoreSettings: CoreGenerationSettings = {
  prompt: '',
  negative_prompt: '',
  model_name: 'v1-6-pruned-emaonly-fp16.safetensors',
  sampler_name: 'euler',
  scheduler: 'normal',
  steps: 20,
  cfg_scale: 7.0,
  denoising_strength: 0.75,
  width: 512,
  height: 512,
  batch_size: 1,
  batch_count: 1,
  seed: -1,
  random_seed: true,
  clip_skip: 1,
  tiling: false,
  tile_size: 512,
  tile_overlap: 64,
  hires_fix: false,
  karras_sigmas: false,
  lora: null,
  restore_faces: false,
  face_restoration_model: 'codeformer',
  codeformer_weight: 0.5,
  gfpgan_weight: 0.5,
  // Hires.fix defaults
  hires_fix_enabled: false,
  hires_fix_upscale_method: 'upscale-by',
  hires_fix_upscale_factor: 2.5,
  hires_fix_hires_steps: 15,
  hires_fix_denoising_strength: 0.5,
  hires_fix_resize_width: 4000,
  hires_fix_resize_height: 4000,
  hires_fix_upscaler: '4x-ultrasharp',
  refiner_enabled: false,
  refiner_model: 'none',
  refiner_switch_at: 0.8
};

// Type for the response from the backend
export interface GenerationResponse {
  status: 'success' | 'error';
  message: string;
  comfy_response?: {
    prompt_id: string;
    generated_images?: Array<{
      filename: string;
      type: string;
      subfolder?: string;
      url: string;
    }>;
  };
  workflow?: unknown;
  error?: string;
}

// Type for the gallery image results
export interface ImageResult {
  id: string;
  url: string;
  prompt: string;
  negativePrompt: string;
  timestamp: number;
  settings: Partial<CoreGenerationSettings>;
}

// Type for txt2img specific settings
export type Txt2ImgCoreSettings = CoreGenerationSettings;

// Default values for txt2img settings
export const defaultTxt2ImgSettings: Txt2ImgCoreSettings = {
  ...defaultCoreSettings,
  // Override unknown default values specific to txt2img here
};

// Type for txt2vid specific settings
export interface Txt2VidCoreSettings {
  // Basic Settings
  prompt: string;
  model: 'luma' | 'runway';

  // Luma-specific settings
  luma_model?: 'ray-2' | 'ray-flash-2';
  aspect_ratio?: '16:9' | '9:16' | '4:3' | '3:4' | '21:9' | '9:21' | '1:1';
  loop?: boolean;
  resolution?: '180p' | '360p' | '540p' | '720p' | '1080p' | '4k';

  // Runway-specific settings
  runway_mode?: 'text2vid' | 'img2vid'; // Text-to-video or Image-to-video
  runway_model?: 'veo3.1' | 'veo3.1_fast' | 'veo3' | 'gen4_turbo' | 'gen3a_turbo' | 'gen4_aleph';
  ratio?: '1280:720' | '720:1280' | '1080:1920' | '1920:1080' | '1104:832' | '832:1104' | '960:960' | '1584:672';
  duration?: 4 | 6 | 8; // Only 4, 6, or 8 seconds allowed
  seed?: number;
  audio?: boolean; // Enable audio generation (costs 2x credits) - only for veo models
  input_image?: string; // Base64 encoded image for image-to-video
}

// Default values for txt2vid settings
export const defaultTxt2VidSettings: Txt2VidCoreSettings = {
  prompt: '',
  model: 'luma',
  luma_model: 'ray-2',
  aspect_ratio: '16:9',
  loop: true,
  resolution: '1080p',
  runway_mode: 'text2vid',
  runway_model: 'veo3.1',
  ratio: '1280:720',
  duration: 4,
  seed: -1,
  audio: false // Default to false to save credits (20 vs 40 credits/sec)
};

// Type for video result
export interface VideoResult {
  id: string;
  url: string;
  filename: string;
  prompt: string;
  timestamp: number;
  settings: Partial<Txt2VidCoreSettings>;
  run_id?: string;
}