import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Copy, ChevronDown, Calculator, PlayCircle } from 'lucide-react';

interface EvalMetricsProps {
  imageId: string;
  imagePath: string;
  prompt?: string;
  metrics?: {
    clip_score_mean?: number;
    clip_score_median?: number;
    clip_score_std?: number;
    clip_score_max?: number;
    clip_score_min?: number;
    fid_score?: number | null;
    criterion_pass_rate?: number | null;
    object_criteria_result?: { status: string; reason?: string };
    // Object Detection Metrics (YOLO)
    object_precision?: number;
    object_recall?: number;
    object_f1?: number;
    detected_objects?: Record<string, number>;
    missing_objects?: Record<string, number>;
    // Visual Composition Metrics
    composition_score?: number;
    rule_of_thirds_score?: number;
    symmetry_score?: number;
    balance_score?: number;
    // Aesthetic predictor / custom heuristics Metrics (Phase 5)
    aesthetics_score?: number;  // LAION aesthetic score (1-10)
    color_harmony_score?: number;
    saturation_balance?: number;
    value_contrast?: number;
    technical_quality_score?: number;
    sharpness_score?: number;
    noise_level?: number;
    artifact_score?: number;
    overall_aesthetic_quality?: number;
    // Legacy/additional metrics
    composition_precision?: number;
    composition_recall?: number;
    composition_f1?: number;
    lpips_score?: number;
    psnr_score?: number;
    ssim_score?: number;
    nsfw_score?: number;
    computed_at?: string;
  };
  isLoading?: boolean;
  onCalculateMetrics?: () => Promise<void>;
}

const EvalMetrics: React.FC<EvalMetricsProps> = ({
  imageId,
  imagePath,
  prompt,
  metrics,
  isLoading = false,
  onCalculateMetrics
}) => {
  const [expanded, setExpanded] = useState(true);
  const [batchLoading, setBatchLoading] = useState(false);

  const handleCalculateAll = async () => {
    setBatchLoading(true);
    try {
      const response = await fetch('http://localhost:5005/api/runs/calculate-metrics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const result = await response.json();
      console.log('Batch image metrics:', result);
      // Auto-refresh current image metrics from cache
      if (onCalculateMetrics) {
        await onCalculateMetrics();
      }
    } catch (error) {
      console.error('Error in batch image metrics:', error);
    } finally {
      setBatchLoading(false);
    }
  };

  const handleCopyMetrics = () => {
    if (!metrics) return;

    const metricsText = JSON.stringify(metrics, null, 2);
    navigator.clipboard.writeText(metricsText);
  };

  const formatScore = (score: number | undefined, decimals: number = 4) => {
    if (score === undefined) return 'N/A';
    return score.toFixed(decimals);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium">Evaluation Metrics</span>
        <div className="flex items-center gap-2">
          {onCalculateMetrics && (
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-8"
              onClick={onCalculateMetrics}
              disabled={isLoading}
            >
              <Calculator className="w-3 h-3 mr-1" />
              {isLoading ? 'Calculating...' : 'Calculate'}
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-8"
            onClick={handleCalculateAll}
            disabled={batchLoading}
          >
            <PlayCircle className="w-3 h-3 mr-1" />
            {batchLoading ? 'Scoring...' : 'Calculate All'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-8"
            onClick={handleCopyMetrics}
            disabled={!metrics}
          >
            <Copy className="w-3 h-3 mr-1" />
            Copy
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => setExpanded(!expanded)}
          >
            <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </Button>
        </div>
      </div>

      {expanded && (
        <div className="bg-muted p-3 rounded-md text-xs leading-relaxed">
          {!metrics ? (
            <div className="text-muted-foreground">
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                  <span>Computing metrics...</span>
                </div>
              ) : (
                "No metrics computed yet. Click 'Calculate' to compute evaluation metrics."
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {/* CLIP Score */}
              {metrics.clip_score_mean !== undefined && (
                <div>
                  <div className="font-semibold mb-1">CLIP cosine similarity (−1 to 1):</div>
                  <div className="text-muted-foreground">
                    <strong>Mean:</strong> {formatScore(metrics.clip_score_mean)}
                  </div>
                </div>
              )}

              <p>FID is a distribution metric. Select generated and reference sets in the Research workbench.</p>
              {metrics.object_criteria_result && <div><strong>Detected object criteria:</strong> {formatScore(metrics.criterion_pass_rate)} · {metrics.object_criteria_result.status}<p>{metrics.object_criteria_result.reason}</p></div>}

              {/* Object Detection Metrics (YOLO) */}
              {(metrics.object_precision !== undefined ||
                metrics.object_recall !== undefined ||
                metrics.object_f1 !== undefined) && (
                <div>
                  <div className="font-semibold mb-1">Legacy detector count metrics (not overall task accuracy):</div>
                  <div className="space-y-1 text-muted-foreground">
                    {metrics.object_f1 !== undefined && (
                      <div>
                        <strong>F1 Score:</strong> {formatScore(metrics.object_f1)}
                      </div>
                    )}
                    {metrics.object_precision !== undefined && (
                      <div>
                        <strong>Precision:</strong> {formatScore(metrics.object_precision)}
                      </div>
                    )}
                    {metrics.object_recall !== undefined && (
                      <div>
                        <strong>Recall:</strong> {formatScore(metrics.object_recall)}
                      </div>
                    )}
                    {metrics.detected_objects && Object.keys(metrics.detected_objects).length > 0 && (
                      <div className="text-xs">
                        <strong>Detected:</strong> {Object.entries(metrics.detected_objects).map(([k, v]) => `${k}(${v})`).join(', ')}
                      </div>
                    )}
                    {metrics.missing_objects && Object.keys(metrics.missing_objects).length > 0 && (
                      <div className="text-xs">
                        <strong>Missing:</strong> {Object.entries(metrics.missing_objects).map(([k, v]) => `${k}(${v})`).join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Visual Composition Metrics */}
              {(metrics.composition_score !== undefined ||
                metrics.rule_of_thirds_score !== undefined ||
                metrics.symmetry_score !== undefined ||
                metrics.balance_score !== undefined) && (
                <div>
                  <div className="font-semibold mb-1">Visual Composition:</div>
                  <div className="space-y-1 text-muted-foreground">
                    {metrics.composition_score !== undefined && (
                      <div>
                        <strong>Overall:</strong> {formatScore(metrics.composition_score)}
                      </div>
                    )}
                    {metrics.rule_of_thirds_score !== undefined && (
                      <div>
                        <strong>Rule of Thirds:</strong> {formatScore(metrics.rule_of_thirds_score)}
                      </div>
                    )}
                    {metrics.symmetry_score !== undefined && (
                      <div>
                        <strong>Symmetry:</strong> {formatScore(metrics.symmetry_score)}
                      </div>
                    )}
                    {metrics.balance_score !== undefined && (
                      <div>
                        <strong>Balance:</strong> {formatScore(metrics.balance_score)}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Aesthetic predictor / custom heuristics Metrics */}
              {(metrics.aesthetics_score !== undefined ||
                metrics.color_harmony_score !== undefined ||
                metrics.technical_quality_score !== undefined ||
                metrics.overall_aesthetic_quality !== undefined) && (
                <div>
                  <div className="font-semibold mb-1">Aesthetic predictor / custom heuristics:</div>
                  <div className="space-y-1 text-muted-foreground">
                    {metrics.aesthetics_score !== undefined && (
                      <div>
                        <strong>LAION Aesthetic:</strong> {formatScore(metrics.aesthetics_score, 2)}/10
                      </div>
                    )}
                    {metrics.color_harmony_score !== undefined && (
                      <div>
                        <strong>Color Harmony:</strong> {formatScore(metrics.color_harmony_score)}
                      </div>
                    )}
                    {metrics.saturation_balance !== undefined && (
                      <div className="pl-3">
                        <strong>Saturation Balance:</strong> {formatScore(metrics.saturation_balance)}
                      </div>
                    )}
                    {metrics.value_contrast !== undefined && (
                      <div className="pl-3">
                        <strong>Value Contrast:</strong> {formatScore(metrics.value_contrast)}
                      </div>
                    )}
                    {metrics.technical_quality_score !== undefined && (
                      <div>
                        <strong>Technical Quality:</strong> {formatScore(metrics.technical_quality_score)}
                      </div>
                    )}
                    {metrics.sharpness_score !== undefined && (
                      <div className="pl-3">
                        <strong>Sharpness:</strong> {formatScore(metrics.sharpness_score)}
                      </div>
                    )}
                    {metrics.noise_level !== undefined && (
                      <div className="pl-3">
                        <strong>Noise Level:</strong> {formatScore(metrics.noise_level)} <span className="opacity-60">(lower is better)</span>
                      </div>
                    )}
                    {metrics.artifact_score !== undefined && (
                      <div className="pl-3">
                        <strong>Artifacts:</strong> {formatScore(metrics.artifact_score)} <span className="opacity-60">(lower is better)</span>
                      </div>
                    )}
                    {metrics.overall_aesthetic_quality !== undefined && (
                      <div className="font-medium pt-1 border-t border-border/50">
                        <strong>Overall Aesthetic:</strong> {formatScore(metrics.overall_aesthetic_quality)}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Reference Comparison Metrics (img2img only) */}
              {(metrics.lpips_score !== undefined ||
                metrics.psnr_score !== undefined ||
                metrics.ssim_score !== undefined) && (
                <div>
                  <div className="font-semibold mb-1">Reference Comparison (img2img):</div>
                  <div className="space-y-1 text-muted-foreground">
                    {metrics.ssim_score !== undefined && (
                      <div>
                        <strong>SSIM:</strong> {formatScore(metrics.ssim_score)} <span className="opacity-60">(higher is better)</span>
                      </div>
                    )}
                    {metrics.psnr_score !== undefined && (
                      <div>
                        <strong>PSNR:</strong> {formatScore(metrics.psnr_score, 2)} dB <span className="opacity-60">(higher is better)</span>
                      </div>
                    )}
                    {metrics.lpips_score !== undefined && (
                      <div>
                        <strong>LPIPS:</strong> {formatScore(metrics.lpips_score)} <span className="opacity-60">(lower is better)</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* NSFW Score (if available) */}
              {metrics.nsfw_score !== undefined && (
                <div>
                  <div className="font-semibold mb-1">Safety:</div>
                  <div className="text-muted-foreground">
                    <strong>NSFW Score:</strong> {formatScore(metrics.nsfw_score)}
                  </div>
                </div>
              )}

              {/* Computed At */}
              {metrics.computed_at && (
                <div className="text-xs text-muted-foreground pt-2 border-t">
                  Computed at: {new Date(metrics.computed_at).toLocaleString()}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EvalMetrics;
