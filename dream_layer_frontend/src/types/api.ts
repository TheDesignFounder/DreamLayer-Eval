import type { CoreGenerationSettings, Txt2VidCoreSettings } from './generationSettings';
export interface HistoryImage { id: string; url: string; prompt?: string; negative_prompt?: string; created_at: string; settings: Partial<CoreGenerationSettings>; }
export interface HistoryVideo { id: string; url: string; filename: string; prompt?: string; created_at: string; settings: Partial<Txt2VidCoreSettings>; }
export interface GeneratedImage { url: string; filename?: string; }
export interface GeneratedGrid { url: string; batch_index: number; grid_layout: string; batch_size: number; }
export interface CustomWorkflow { prompt: Record<string, unknown>; [key: string]: unknown; }
