/**
 * Utility functions for ControlNet data processing
 */

import { ControlNetRequest } from '@/types/controlnet';

// Extended ControlNetUnit type that allows both File and string for input_image
interface ControlNetUnitForAPI {
  unit_index: number;
  enabled: boolean;
  input_image?: File | string | null;
  input_mode: "single" | "batch";
  batch_directory?: string;
  control_type: string;
  preprocessor: string;
  model: string;
  weight: number;
  guidance_start: number;
  guidance_end: number;
  resolution: number;
  control_mode: string;
  resize_mode: string;
  threshold_a?: number;
  threshold_b?: number;
  pixel_perfect: boolean;
  low_vram: boolean;
  allow_preview: boolean;
  effective_region_mask: boolean;
  upload_independent_control: boolean;
  loopback: boolean;
}

// Extended ControlNetRequest type for API
interface ControlNetRequestForAPI {
  enabled: boolean;
  units: ControlNetUnitForAPI[];
}

/**
 * Convert a File object to a base64 string
 */
export async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result);
      } else {
        reject(new Error('Failed to convert file to base64'));
      }
    };
    reader.onerror = error => reject(error);
  });
}

/**
 * Prepare ControlNet data for API request by converting File objects to base64
 */
export async function prepareControlNetForAPI(controlNetConfig: ControlNetRequest | null): Promise<ControlNetRequestForAPI | null> {
  if (!controlNetConfig || !controlNetConfig.enabled) {
    return null;
  }

  const preparedConfig: ControlNetRequestForAPI = {
    enabled: controlNetConfig.enabled,
    units: []
  };

  for (const unit of controlNetConfig.units) {
    if (!unit.enabled) {
      continue;
    }

    const preparedUnit: ControlNetUnitForAPI = { ...unit };

    // Convert File object to base64 if present
    if ((unit.input_image as unknown) instanceof File) {
      try {
        preparedUnit.input_image = await fileToBase64(unit.input_image as unknown as File);
      } catch (error) {
        console.error('Error converting ControlNet image to base64:', error);
        // Skip this unit if image conversion fails
        continue;
      }
    }

    preparedConfig.units.push(preparedUnit);
  }

  // Only return if we have at least one valid unit
  return preparedConfig.units.length > 0 ? preparedConfig : null;
}

/**
 * Validate ControlNet configuration before sending to API
 */
export function validateControlNetConfig(controlNetConfig: ControlNetRequest | null): boolean {
  if (!controlNetConfig || !controlNetConfig.enabled) {
    return false;
  }

  const enabledUnits = controlNetConfig.units.filter(unit => unit.enabled);
  if (enabledUnits.length === 0) {
    return false;
  }

  for (const unit of enabledUnits) {
    // Check required fields
    if (!unit.control_type || !unit.model) {
      return false;
    }

    // For img2img, we need an input image
    if (!unit.input_image) {
      return false;
    }
  }

  return true;
} 