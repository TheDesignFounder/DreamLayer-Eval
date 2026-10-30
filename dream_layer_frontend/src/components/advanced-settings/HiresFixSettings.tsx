
import React from "react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import Slider from "@/components/Slider";
import SizingSettings from "@/components/SizingSettings";
import upscalingModels, { UpscalingModelData } from "./models/upscalingModels";
import { Card } from "@/components/ui/card";

interface HiresFixSettingsProps {
  upscaleMethod: string;
  setUpscaleMethod: (value: string) => void;
  upscaleFactor: number;
  setUpscaleFactor: (value: number) => void;
  hiresSteps: number;
  setHiresSteps: (value: number) => void;
  denoisingStrength: number;
  setDenoisingStrength: (value: number) => void;
  resizeWidth: number;
  setResizeWidth: (value: number) => void;
  resizeHeight: number;
  setResizeHeight: (value: number) => void;
  selectedUpscaler: string;
  setSelectedUpscaler: (value: string) => void;
}

const HiresFixSettings: React.FC<HiresFixSettingsProps> = ({
  upscaleMethod,
  setUpscaleMethod,
  upscaleFactor,
  setUpscaleFactor,
  hiresSteps,
  setHiresSteps,
  denoisingStrength,
  setDenoisingStrength,
  resizeWidth,
  setResizeWidth,
  resizeHeight,
  setResizeHeight,
  selectedUpscaler,
  setSelectedUpscaler,
}) => {
  // Get current upscaler information
  const currentUpscaler: UpscalingModelData = upscalingModels[selectedUpscaler] || upscalingModels["4x-ultrasharp"];

  return (
    <>
      <div className="mt-4 mb-3">
        <div className="text-sm font-medium text-foreground mb-2">a) Set Upscale Size:</div>
        <RadioGroup 
          value={upscaleMethod} 
          onValueChange={setUpscaleMethod}
          className="grid grid-cols-2 gap-3"
        >
          <div className="relative">
            <Card className={`flex items-center gap-3 p-3 cursor-pointer border ${upscaleMethod === "upscale-by" ? "border-blue-600 bg-blue-50/50" : "border-gray-200"}`}>
              <RadioGroupItem id="upscale-by" value="upscale-by" className="h-4 w-4" />
              <label htmlFor="upscale-by" className="text-sm font-medium cursor-pointer w-full">Upscale by</label>
            </Card>
          </div>
          
          <div className="relative">
            <Card className={`flex items-center gap-3 p-3 cursor-pointer border ${upscaleMethod === "resize-to" ? "border-blue-600 bg-blue-50/50" : "border-gray-200"}`}>
              <RadioGroupItem id="resize-to" value="resize-to" className="h-4 w-4" />
              <label htmlFor="resize-to" className="text-sm font-medium cursor-pointer w-full">Resize to</label>
            </Card>
          </div>
        </RadioGroup>
      </div>
      
      {upscaleMethod === "upscale-by" ? (
        <div className="mb-6">
          <Slider
            min={1}
            max={10}
            step={0.1}
            defaultValue={upscaleFactor}
            label="Upscale"
            onChange={(value) => setUpscaleFactor(value)}
            inputWidth="w-16"
          />
        </div>
      ) : (
        <div className="my-6">
          <SizingSettings 
             
            width={resizeWidth} 
            height={resizeHeight}
            onChange={(w, h) => { setResizeWidth(w); setResizeHeight(h); }}
          />
        </div>
      )}
      
      <div className="my-6">
        <div className="text-sm font-medium text-foreground mb-2">b) Upscaling Model</div>
        <Select 
          defaultValue={selectedUpscaler} 
          onValueChange={(value) => setSelectedUpscaler(value)}
        >
          <SelectTrigger className="w-full" id="upscaling-model">
            <SelectValue placeholder="Select an upscaling model" />
          </SelectTrigger>
          <SelectContent>
            {Object.values(upscalingModels).map((model) => (
              <SelectItem key={model.id} value={model.id}>
                {model.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="mt-4 mx-4 text-sm text-muted-foreground">
          <p className="mb-1">
            <span className="font-medium">About The Upscaler:</span> {currentUpscaler.description} Speed: {currentUpscaler.speed}.
          </p>
        </div>
      </div>
      
      <div className="mb-6">
        <Slider
          min={1}
          max={30}
          step={1}
          defaultValue={hiresSteps}
          label={`c) Hires Steps | <span style='color: #64748B;'>Optimal Level: ${currentUpscaler.optimalHiresSteps}</span>`}
          onChange={(value) => setHiresSteps(value)}
          inputWidth="w-16"
        />
      </div>
      
      <div className="mb-4">
        <Slider
          min={0}
          max={1}
          step={0.05}
          defaultValue={denoisingStrength}
          label={`d) Denoising Strength | <span style='color: #64748B;'>Optimal Accuracy: ${currentUpscaler.optimalDenoisingStrength}</span>`}
          onChange={(value) => setDenoisingStrength(value)}
          inputWidth="w-16"
        />
      </div>
    </>
  );
};

export default HiresFixSettings;
