import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Copy, ChevronDown, Calculator, Download, PlayCircle } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface VideoMetrics {
  fvd_score?: number | null;
  video_ssim_mean?: number;
  video_ssim_std?: number;
  video_psnr_mean?: number;
  video_psnr_std?: number;
  video_lpips_mean?: number;
  video_lpips_std?: number;
  video_ssim_per_frame?: number[];
  video_psnr_per_frame?: number[];
  video_lpips_per_frame?: number[];
  // Phase 2: No-reference quality metrics
  adjacent_pixel_stability?: number;
  per_frame_flicker?: number[];
  whole_frame_anchored_dino_cosine?: number;
  per_frame_subject_sim?: number[];
  whole_frame_adjacent_dino_cosine?: number;
  per_frame_bg_sim?: number[];
  flow_magnitude_stability?: number;
  per_frame_motion?: number[];
  video_aesthetic_mean?: number;
  video_aesthetic_min?: number;
  video_aesthetic_std?: number;
  per_frame_aesthetic?: number[];
  video_fps?: number;
  computed_at?: string;
  _cached?: boolean;
  _errors?: string[];
}

interface VideoEvalMetricsProps {
  videoId: string;
  videoPath: string;
  prompt?: string;
  metrics?: VideoMetrics;
  isLoading?: boolean;
  onCalculateMetrics?: () => Promise<void>;
}

const VideoEvalMetrics: React.FC<VideoEvalMetricsProps> = ({
  videoId,
  videoPath,
  prompt,
  metrics,
  isLoading = false,
  onCalculateMetrics
}) => {
  const [expanded, setExpanded] = useState(true);
  const [chartExpanded, setChartExpanded] = useState(false);
  const [qualityChartExpanded, setQualityChartExpanded] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);

  const handleCalculateAll = async () => {
    setBatchLoading(true);
    try {
      const response = await fetch('http://localhost:5008/api/calculate-all-video-metrics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const result = await response.json();
      if (result.stats) {
        console.log('Batch video metrics:', result.stats);
      }
      // Auto-refresh current video metrics from cache
      if (onCalculateMetrics) {
        await onCalculateMetrics();
      }
    } catch (error) {
      console.error('Error in batch video metrics:', error);
    } finally {
      setBatchLoading(false);
    }
  };

  const handleExportCSV = () => {
    window.open('http://localhost:5008/api/export-video-metrics', '_blank');
  };

  const handleCopyMetrics = () => {
    if (!metrics) return;
    const metricsText = JSON.stringify(metrics, null, 2);
    navigator.clipboard.writeText(metricsText);
  };

  const formatScore = (score: number | undefined | null, decimals: number = 4) => {
    if (score === undefined || score === null) return 'N/A';
    return score.toFixed(decimals);
  };

  // Build chart data from per-frame metrics
  const chartData = React.useMemo(() => {
    if (!metrics) return [];
    const maxLen = Math.max(
      metrics.video_ssim_per_frame?.length || 0,
      metrics.video_psnr_per_frame?.length || 0,
      metrics.video_lpips_per_frame?.length || 0
    );
    if (maxLen === 0) return [];

    return Array.from({ length: maxLen }, (_, i) => ({
      frame: i + 1,
      ssim: metrics.video_ssim_per_frame?.[i],
      psnr: metrics.video_psnr_per_frame?.[i],
      lpips: metrics.video_lpips_per_frame?.[i],
    }));
  }, [metrics]);

  // Build chart data from per-frame quality metrics
  const qualityChartData = React.useMemo(() => {
    if (!metrics) return [];
    const maxLen = Math.max(
      metrics.per_frame_flicker?.length || 0,
      metrics.per_frame_subject_sim?.length || 0,
      metrics.per_frame_bg_sim?.length || 0,
      metrics.per_frame_motion?.length || 0,
      metrics.per_frame_aesthetic?.length || 0
    );
    if (maxLen === 0) return [];

    return Array.from({ length: maxLen }, (_, i) => ({
      frame: i + 1,
      flicker: metrics.per_frame_flicker?.[i],
      subjectSim: metrics.per_frame_subject_sim?.[i],
      bgSim: metrics.per_frame_bg_sim?.[i],
      motion: metrics.per_frame_motion?.[i],
      aesthetic: metrics.per_frame_aesthetic?.[i],
    }));
  }, [metrics]);

  const hasReferenceMetrics = metrics && (
    metrics.video_ssim_mean !== undefined ||
    metrics.video_psnr_mean !== undefined ||
    metrics.video_lpips_mean !== undefined
  );

  const hasQualityMetrics = metrics && (
    metrics.adjacent_pixel_stability !== undefined ||
    metrics.whole_frame_anchored_dino_cosine !== undefined ||
    metrics.whole_frame_adjacent_dino_cosine !== undefined ||
    metrics.flow_magnitude_stability !== undefined ||
    metrics.video_aesthetic_mean !== undefined
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium">Video Evaluation Metrics</span>
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
            onClick={handleExportCSV}
          >
            <Download className="w-3 h-3 mr-1" />
            Export CSV
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
                  <span>Computing video metrics...</span>
                </div>
              ) : (
                "No metrics computed yet. Click 'Calculate' to compute video evaluation metrics."
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {/* FVD Score */}
              {metrics.fvd_score !== undefined && metrics.fvd_score !== null && (
                <div>
                  <div className="font-semibold mb-1">FVD (Frechet Video Distance):</div>
                  <div className="text-muted-foreground">
                    {formatScore(metrics.fvd_score, 2)} <span className="opacity-60">(lower is better)</span>
                  </div>
                </div>
              )}

              {/* Video Quality Metrics (No-Reference) */}
              {hasQualityMetrics && (
                <div>
                  <div className="font-semibold mb-1">Video Quality:</div>
                  <div className="space-y-1 text-muted-foreground">
                    {metrics.adjacent_pixel_stability !== undefined && (
                      <div>
                        <strong>Adjacent pixel stability (custom):</strong> {formatScore(metrics.adjacent_pixel_stability)}
                        <span className="opacity-60"> (higher is better, 1.0 = no flicker)</span>
                      </div>
                    )}
                    {metrics.whole_frame_anchored_dino_cosine !== undefined && (
                      <div>
                        <strong>Whole-frame anchored DINO cosine:</strong> {formatScore(metrics.whole_frame_anchored_dino_cosine)}
                        <span className="opacity-60"> (higher is better)</span>
                      </div>
                    )}
                    {metrics.whole_frame_adjacent_dino_cosine !== undefined && (
                      <div>
                        <strong>Whole-frame adjacent DINO cosine:</strong> {formatScore(metrics.whole_frame_adjacent_dino_cosine)}
                        <span className="opacity-60"> (higher is better)</span>
                      </div>
                    )}
                    {metrics.flow_magnitude_stability !== undefined && (
                      <div>
                        <strong>Flow magnitude stability (custom):</strong> {formatScore(metrics.flow_magnitude_stability)}
                        <span className="opacity-60"> (higher is better)</span>
                      </div>
                    )}
                    {metrics.video_aesthetic_mean !== undefined && (
                      <div>
                        <strong>Aesthetic Quality:</strong> {formatScore(metrics.video_aesthetic_mean, 2)}
                        {metrics.video_aesthetic_min !== undefined && (
                          <span className="opacity-60"> (min: {formatScore(metrics.video_aesthetic_min, 2)})</span>
                        )}
                        {metrics.video_aesthetic_std !== undefined && (
                          <span className="opacity-60"> (std: {formatScore(metrics.video_aesthetic_std, 2)})</span>
                        )}
                        <span className="opacity-60"> (1-10 scale)</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Quality Per-Frame Charts */}
              {qualityChartData.length > 0 && (
                <div>
                  <div
                    className="font-semibold mb-1 cursor-pointer flex items-center gap-1"
                    onClick={() => setQualityChartExpanded(!qualityChartExpanded)}
                  >
                    Quality Temporal Analysis:
                    <ChevronDown className={`w-3 h-3 transition-transform ${qualityChartExpanded ? 'rotate-180' : ''}`} />
                  </div>
                  {qualityChartExpanded && (
                    <div className="space-y-3 mt-2">
                      {/* Flicker (MAE between consecutive frames) */}
                      {metrics.per_frame_flicker && metrics.per_frame_flicker.length > 0 && (
                        <div>
                          <div className="text-muted-foreground mb-1">Frame-to-Frame Flicker (MAE):</div>
                          <div className="h-32 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={qualityChartData}>
                                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                <XAxis dataKey="frame" tick={{ fontSize: 10 }} />
                                <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
                                <Tooltip contentStyle={{ fontSize: 11 }} labelFormatter={(v) => { if (!metrics?.video_fps) return `Frame ${v}`; const secs = Number(v) / metrics.video_fps; const m = Math.floor(secs / 60); const s = Math.floor(secs % 60); const ms = Math.round((secs % 1) * 100); return `Frame ${v} (${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(2,'0')})`; }} />
                                <Line type="monotone" dataKey="flicker" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="Flicker (MAE)" />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}

                      {/* Subject & Whole-frame adjacent DINO cosine */}
                      {((metrics.per_frame_subject_sim && metrics.per_frame_subject_sim.length > 0) ||
                        (metrics.per_frame_bg_sim && metrics.per_frame_bg_sim.length > 0)) && (
                        <div>
                          <div className="text-muted-foreground mb-1">Consistency (DINO Similarity):</div>
                          <div className="h-32 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={qualityChartData}>
                                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                <XAxis dataKey="frame" tick={{ fontSize: 10 }} />
                                <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
                                <Tooltip contentStyle={{ fontSize: 11 }} labelFormatter={(v) => { if (!metrics?.video_fps) return `Frame ${v}`; const secs = Number(v) / metrics.video_fps; const m = Math.floor(secs / 60); const s = Math.floor(secs % 60); const ms = Math.round((secs % 1) * 100); return `Frame ${v} (${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(2,'0')})`; }} />
                                <Legend wrapperStyle={{ fontSize: 10 }} />
                                {metrics.per_frame_subject_sim && metrics.per_frame_subject_sim.length > 0 && (
                                  <Line type="monotone" dataKey="subjectSim" stroke="#8b5cf6" dot={false} strokeWidth={1.5} name="Subject" />
                                )}
                                {metrics.per_frame_bg_sim && metrics.per_frame_bg_sim.length > 0 && (
                                  <Line type="monotone" dataKey="bgSim" stroke="#06b6d4" dot={false} strokeWidth={1.5} name="Background" />
                                )}
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}

                      {/* Motion (optical flow magnitude) */}
                      {metrics.per_frame_motion && metrics.per_frame_motion.length > 0 && (
                        <div>
                          <div className="text-muted-foreground mb-1">Motion Flow Magnitude:</div>
                          <div className="h-32 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={qualityChartData}>
                                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                <XAxis dataKey="frame" tick={{ fontSize: 10 }} />
                                <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
                                <Tooltip contentStyle={{ fontSize: 11 }} labelFormatter={(v) => { if (!metrics?.video_fps) return `Frame ${v}`; const secs = Number(v) / metrics.video_fps; const m = Math.floor(secs / 60); const s = Math.floor(secs % 60); const ms = Math.round((secs % 1) * 100); return `Frame ${v} (${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(2,'0')})`; }} />
                                <Line type="monotone" dataKey="motion" stroke="#10b981" dot={false} strokeWidth={1.5} name="Flow Magnitude" />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}

                      {/* Aesthetic per frame */}
                      {metrics.per_frame_aesthetic && metrics.per_frame_aesthetic.length > 0 && (
                        <div>
                          <div className="text-muted-foreground mb-1">Aesthetic Score per Frame:</div>
                          <div className="h-32 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={qualityChartData}>
                                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                <XAxis dataKey="frame" tick={{ fontSize: 10 }} />
                                <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
                                <Tooltip contentStyle={{ fontSize: 11 }} labelFormatter={(v) => { if (!metrics?.video_fps) return `Frame ${v}`; const secs = Number(v) / metrics.video_fps; const m = Math.floor(secs / 60); const s = Math.floor(secs % 60); const ms = Math.round((secs % 1) * 100); return `Frame ${v} (${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(2,'0')})`; }} />
                                <Line type="monotone" dataKey="aesthetic" stroke="#ec4899" dot={false} strokeWidth={1.5} name="Aesthetic" />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Reference Comparison Metrics */}
              {hasReferenceMetrics && (
                <div>
                  <div className="font-semibold mb-1">Video Reference Comparison:</div>
                  <div className="space-y-1 text-muted-foreground">
                    {metrics.video_ssim_mean !== undefined && (
                      <div>
                        <strong>SSIM:</strong> {formatScore(metrics.video_ssim_mean)}
                        {metrics.video_ssim_std !== undefined && (
                          <span className="opacity-60"> (std: {formatScore(metrics.video_ssim_std)})</span>
                        )}
                        <span className="opacity-60"> (higher is better)</span>
                      </div>
                    )}
                    {metrics.video_psnr_mean !== undefined && (
                      <div>
                        <strong>PSNR:</strong> {formatScore(metrics.video_psnr_mean, 2)} dB
                        {metrics.video_psnr_std !== undefined && (
                          <span className="opacity-60"> (std: {formatScore(metrics.video_psnr_std, 2)})</span>
                        )}
                        <span className="opacity-60"> (higher is better)</span>
                      </div>
                    )}
                    {metrics.video_lpips_mean !== undefined && (
                      <div>
                        <strong>LPIPS:</strong> {formatScore(metrics.video_lpips_mean)}
                        {metrics.video_lpips_std !== undefined && (
                          <span className="opacity-60"> (std: {formatScore(metrics.video_lpips_std)})</span>
                        )}
                        <span className="opacity-60"> (lower is better)</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Per-Frame Temporal Chart */}
              {chartData.length > 0 && (
                <div>
                  <div
                    className="font-semibold mb-1 cursor-pointer flex items-center gap-1"
                    onClick={() => setChartExpanded(!chartExpanded)}
                  >
                    Temporal Analysis (Per-Frame):
                    <ChevronDown className={`w-3 h-3 transition-transform ${chartExpanded ? 'rotate-180' : ''}`} />
                  </div>
                  {chartExpanded && (
                    <div className="space-y-3 mt-2">
                      {/* SSIM over time */}
                      {metrics.video_ssim_per_frame && metrics.video_ssim_per_frame.length > 0 && (
                        <div>
                          <div className="text-muted-foreground mb-1">SSIM per Frame:</div>
                          <div className="h-32 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                <XAxis dataKey="frame" tick={{ fontSize: 10 }} />
                                <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
                                <Tooltip contentStyle={{ fontSize: 11 }} labelFormatter={(v) => { if (!metrics?.video_fps) return `Frame ${v}`; const secs = Number(v) / metrics.video_fps; const m = Math.floor(secs / 60); const s = Math.floor(secs % 60); const ms = Math.round((secs % 1) * 100); return `Frame ${v} (${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(2,'0')})`; }} />
                                <Line type="monotone" dataKey="ssim" stroke="#22c55e" dot={false} strokeWidth={1.5} name="SSIM" />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}

                      {/* PSNR over time */}
                      {metrics.video_psnr_per_frame && metrics.video_psnr_per_frame.length > 0 && (
                        <div>
                          <div className="text-muted-foreground mb-1">PSNR per Frame:</div>
                          <div className="h-32 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                <XAxis dataKey="frame" tick={{ fontSize: 10 }} />
                                <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
                                <Tooltip contentStyle={{ fontSize: 11 }} labelFormatter={(v) => { if (!metrics?.video_fps) return `Frame ${v}`; const secs = Number(v) / metrics.video_fps; const m = Math.floor(secs / 60); const s = Math.floor(secs % 60); const ms = Math.round((secs % 1) * 100); return `Frame ${v} (${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(2,'0')})`; }} />
                                <Line type="monotone" dataKey="psnr" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="PSNR (dB)" />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}

                      {/* LPIPS over time */}
                      {metrics.video_lpips_per_frame && metrics.video_lpips_per_frame.length > 0 && (
                        <div>
                          <div className="text-muted-foreground mb-1">LPIPS per Frame:</div>
                          <div className="h-32 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                <XAxis dataKey="frame" tick={{ fontSize: 10 }} />
                                <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
                                <Tooltip contentStyle={{ fontSize: 11 }} labelFormatter={(v) => { if (!metrics?.video_fps) return `Frame ${v}`; const secs = Number(v) / metrics.video_fps; const m = Math.floor(secs / 60); const s = Math.floor(secs % 60); const ms = Math.round((secs % 1) * 100); return `Frame ${v} (${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(2,'0')})`; }} />
                                <Line type="monotone" dataKey="lpips" stroke="#ef4444" dot={false} strokeWidth={1.5} name="LPIPS" />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Info note when no reference */}
              {!hasReferenceMetrics && (
                <div className="text-muted-foreground italic text-[11px]">
                  Reference-based metrics (SSIM, PSNR, LPIPS, FVD) require a reference video for comparison.
                </div>
              )}

              {/* Errors */}
              {metrics._errors && metrics._errors.length > 0 && (
                <div>
                  <div className="font-semibold mb-1 text-yellow-500">Warnings:</div>
                  <div className="text-muted-foreground">
                    {metrics._errors.map((err, i) => (
                      <div key={i}>{err}</div>
                    ))}
                  </div>
                </div>
              )}

              {/* Computed At */}
              {metrics.computed_at && (
                <div className="text-xs text-muted-foreground pt-2 border-t">
                  Computed at: {new Date(metrics.computed_at).toLocaleString()}
                  {metrics._cached && <span className="ml-2 opacity-60">(cached)</span>}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default VideoEvalMetrics;
