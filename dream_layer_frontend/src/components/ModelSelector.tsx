import { CirclePlus, RefreshCw, Save, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import ApiBasedModelForm from "@/components/AliasKeyInputs";
import { useEffect, useState, useCallback } from "react";
import PopupBox from "@/components/ui/pop-up"
import {
    CheckpointModel,
    fetchAvailableModels,
    addModelRefreshListener,
    ensureWebSocketConnection
} from "@/services/modelService";
import { toast } from "@/components/ui/sonner";

type ModelType = 'image' | 'video' | 'text';

interface UnifiedModel {
  id: string;
  name: string;
  filename: string;
  type: ModelType;
  category?: string; // e.g., 'luma', 'runway', 'sd-checkpoint'
}

interface ModelSelectorProps {
  onModelSelect: (modelName: string, modelType: ModelType) => void;
  currentTab?: string; // Current active tab to validate model type
}

// High-level video provider models
const videoModels: UnifiedModel[] = [
  { id: 'luma', name: 'Luma AI (Dream Machine)', filename: 'luma', type: 'video', category: 'luma' },
  { id: 'runway', name: 'Runway ML (Gen-3/Veo3)', filename: 'runway', type: 'video', category: 'runway' },
];

const getModelTypeTag = (type: ModelType) => {
  switch (type) {
    case 'image':
      return { label: 'Image', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' };
    case 'video':
      return { label: 'Video', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' };
    case 'text':
      return { label: 'Text', color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' };
  }
};

const ModelSelector: React.FC<ModelSelectorProps> = ({ onModelSelect, currentTab }) => {
  const [checkpointModels, setCheckpointModels] = useState<CheckpointModel[]>([]);
  const [allModels, setAllModels] = useState<UnifiedModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false)
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);

  // Check if there's a model type mismatch
  const hasModelTypeMismatch = () => {
    if (!currentTab || !selectedModel) return false;

    const model = allModels.find(m => m.filename === selectedModel);
    if (!model) return false;

    const isImageTab = currentTab === 'txt2img' || currentTab === 'img2img';
    const isVideoTab = currentTab === 'txt2vid' || currentTab === 'img2vid';

    // Mismatch if: image tab with video model OR video tab with image model
    return (isImageTab && model.type === 'video') || (isVideoTab && model.type === 'image');
  };

  const loadModels = useCallback(async (showSuccessToast = false) => {
    try {
      setIsLoading(true);
      setError(null);
      const availableCheckpoints = await fetchAvailableModels();
      setCheckpointModels(availableCheckpoints);

      // Convert checkpoints to unified model format
      const imageModels: UnifiedModel[] = availableCheckpoints.map(cp => ({
        id: cp.id,
        name: cp.name,
        filename: cp.filename,
        type: 'image' as ModelType,
        category: 'sd-checkpoint'
      }));

      // Fetch available video providers from backend
      let availableVideoModels: UnifiedModel[] = [];
      try {
        const providersResponse = await fetch('http://localhost:5008/api/available-providers');
        const providersData = await providersResponse.json();

        if (providersData.status === 'success' && providersData.providers) {
          // Filter video models based on API key availability
          availableVideoModels = videoModels.filter(model => {
            if (model.category === 'luma') return providersData.providers.luma;
            if (model.category === 'runway') return providersData.providers.runway;
            return false;
          });
        }
      } catch (err) {
        console.warn('Could not fetch available video providers, hiding video models:', err);
        // If we can't reach the backend, hide video models to be safe
        availableVideoModels = [];
      }

      // Combine image and available video models
      const combined = [...imageModels, ...availableVideoModels];
      setAllModels(combined);

      // If we have models and no selection, select the first one
      if (combined.length > 0 && !selectedModel) {
        setSelectedModel(combined[0].filename);
        const modelType = combined[0].type;
        onModelSelect(combined[0].filename, modelType);
      }

      // Show success toast for auto-refresh
      if (showSuccessToast) {
        toast.success(`Models refreshed! Found ${availableCheckpoints.length} image models and ${availableVideoModels.length} video models.`);
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load models');
      console.error('Error loading models:', err);
      toast.error('Failed to refresh models');
    } finally {
      setIsLoading(false);
    }
  }, [selectedModel, onModelSelect]);

  // Setup WebSocket connection and model refresh listener
  useEffect(() => {
    // Initial model load
    loadModels();

    // Setup WebSocket connection
    const setupWebSocket = async () => {
      try {
        await ensureWebSocketConnection();
        setIsWebSocketConnected(true);
      } catch (error) {
        console.warn('⚠️ ModelSelector: Failed to establish WebSocket connection:', error);
        setIsWebSocketConnected(false);
      }
    };

    setupWebSocket();

    // Subscribe to model refresh events
    const unsubscribe = addModelRefreshListener(() => {
      console.log('📡 ModelSelector: Received model refresh event, reloading models...');
      loadModels(true); // Show success toast for auto-refresh
    });

    // Cleanup on unmount
    return () => {
      unsubscribe();
    };
  }, [loadModels]);

  const handleModelChange = (value: string) => {
    setSelectedModel(value);
    const model = allModels.find(m => m.filename === value);
    if (model) {
      onModelSelect(value, model.type);
    }
  };

  const handleManualRefresh = () => {
    loadModels();
  };

    return (
        <div className="flex flex-col space-y-3 sm:flex-row sm:items-center sm:space-x-4 sm:space-y-0">
            <div className="flex flex-col flex-1">
                <PopupBox isOpen={open} onClose={() => {
                  setOpen(false);
                  handleManualRefresh();
                }} aria-label="API-Based Model">
                    <ApiBasedModelForm></ApiBasedModelForm>
                </PopupBox>
                <div className="flex items-center justify-between mb-1">
                    <label htmlFor="model" className="text-sm font-medium">
                        Select Stable Diffusion Checkpoint:
                    </label>
                    <div className="flex items-center space-x-2">
                        {/* WebSocket Connection Status */}
                        <div className="flex items-center space-x-1">
                            {isWebSocketConnected ? (
                                <Wifi className="h-3 w-3 text-green-500" aria-label="Auto-refresh enabled" />
                            ) : (
                                <WifiOff className="h-3 w-3 text-gray-400" aria-label="Auto-refresh disabled" />
                            )}
                            <span className="text-xs text-muted-foreground">
                                {isWebSocketConnected ? 'Auto' : 'Manual'}
                            </span>
                        </div>
                    </div>
                </div>
                <Select value={selectedModel} onValueChange={handleModelChange}>
                    <SelectTrigger
                        id="model"
                        className={`w-full bg-white dark:bg-[#0F172A] text-foreground dark:text-white ${
                          hasModelTypeMismatch()
                            ? 'border-amber-500 border-2 focus:ring-amber-500'
                            : 'border-input dark:border-slate-700'
                        }`}
                    >
                        <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent className="bg-white dark:bg-[#0F172A] border-input dark:border-slate-700 max-h-[400px]">
                        {allModels.map((model) => {
                          const tag = getModelTypeTag(model.type);
                          return (
                            <SelectItem key={model.id} value={model.filename}>
                              <div className="flex items-center gap-2 w-full">
                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${tag.color}`}>
                                  {tag.label}
                                </span>
                                <span className="flex-1">{model.name}</span>
                              </div>
                            </SelectItem>
                          );
                        })}
                    </SelectContent>
                </Select>
                {error && <p className="text-sm text-red-500 mt-1">{error}</p>}
                {hasModelTypeMismatch() && (
                  <p className="text-sm text-amber-600 dark:text-amber-500 mt-1 font-medium">
                    {currentTab === 'txt2img' || currentTab === 'img2img'
                      ? '⚠️ Video model selected. Please select an image model for image generation.'
                      : '⚠️ Image model selected. Please select a video model for video generation.'}
                  </p>
                )}
                {currentTab === 'img2vid' && selectedModel === 'luma' && (
                  <div className="mt-2 p-3" style={{ paddingLeft: 0, paddingRight: 0 }}>
                    <p className="text-sm text-amber-800 dark:text-amber-200">
                      ⚠️ <strong>Luma AI is disabled for image-to-video.</strong> Luma requires publicly accessible CDN URLs for images. Please use Runway ML for img2vid generation.
                    </p>
                  </div>
                )}
                {allModels.length === 0 && !isLoading && !error && (
                    <p className="text-sm text-muted-foreground mt-1">
                        No models found. Try uploading a new model file.
                    </p>
                )}
            </div>
            <div className="flex flex-1 space-x-2 sm:justify-end">
                <Button
                    variant="outline"
                    className="flex items-center space-x-2 mr-5 dark:bg-[#0F172A] dark:border-slate-700 dark:text-white dark:hover:bg-slate-800"
                    onClick={() => setOpen(true)}
                    disabled={isLoading}
                >
                    <CirclePlus className={`h-5 w-5`} />
                    <span>Add API KEY</span>
                </Button>
                <Button
                    variant="outline"
                    className="flex items-center space-x-2 dark:bg-[#0F172A] dark:border-slate-700 dark:text-white dark:hover:bg-slate-800"
                    onClick={handleManualRefresh}
                    disabled={isLoading}
                    title={isWebSocketConnected ? "Manual refresh (auto-refresh is active)" : "Refresh models"}
                >
                    <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                    <span>{isLoading ? 'Loading...' : 'Refresh Models'}</span>
                </Button>
                
            </div>
        </div>
    );
};

export default ModelSelector;
