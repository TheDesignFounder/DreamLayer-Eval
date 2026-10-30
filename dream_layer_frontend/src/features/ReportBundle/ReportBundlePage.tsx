import React, { useState } from 'react';
import { useReportBundleStore } from '@/stores/useReportBundleStore';
import { useRunRegistryStore } from '@/stores/useRunRegistryStore';
import { Download, FileText, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { format } from 'date-fns';

const ReportBundlePage: React.FC = () => {
  const { 
    generating, 
    error, 
    downloadUrl, 
    generateReport, 
    downloadReport, 
    clearError 
  } = useReportBundleStore();
  
  const { runs, fetchRuns } = useRunRegistryStore();
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set());

  React.useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const handleGenerateReport = async () => {
    const runIds = selectedRuns.size > 0 ? Array.from(selectedRuns) : undefined;
    await generateReport(runIds);
  };

  const handleDownloadReport = async () => {
    await downloadReport();
  };

  const toggleRunSelection = (runId: string) => {
    const newSelected = new Set(selectedRuns);
    if (newSelected.has(runId)) {
      newSelected.delete(runId);
    } else {
      newSelected.add(runId);
    }
    setSelectedRuns(newSelected);
  };

  const selectAllRuns = () => {
    setSelectedRuns(new Set(runs.map(run => run.run_id)));
  };

  const clearSelection = () => {
    setSelectedRuns(new Set());
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      return format(new Date(timestamp), 'MMM dd, yyyy HH:mm:ss');
    } catch {
      return timestamp;
    }
  };

  const getGenerationTypeColor = (type: string) => {
    return type === 'txt2img' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Report Bundle</h2>
        <div className="flex items-center space-x-2">
          <Button 
            onClick={selectAllRuns} 
            variant="outline" 
            size="sm"
          >
            Select All
          </Button>
          <Button 
            onClick={clearSelection} 
            variant="outline" 
            size="sm"
          >
            Clear Selection
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error}
            <Button variant="link" onClick={clearError} className="ml-2 p-0 h-auto">
              Dismiss
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {downloadUrl && (
        <Alert>
          <CheckCircle className="h-4 w-4" />
          <AlertDescription>
            Report bundle generated successfully! 
            <Button variant="link" onClick={handleDownloadReport} className="ml-2 p-0 h-auto">
              Download report.zip
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <FileText className="h-5 w-5" />
            <span>Generate Report Bundle</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {selectedRuns.size > 0 
                  ? `Selected ${selectedRuns.size} runs for report bundle`
                  : 'No runs selected - will include all runs'
                }
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                The report bundle will contain results.csv, config.json, selected images, and README.md
              </p>
            </div>
            <Button 
              onClick={handleGenerateReport} 
              disabled={generating}
              className="min-w-[140px]"
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4 mr-2" />
                  Generate Report
                </>
              )}
            </Button>
          </div>

          <Separator />

          <div className="space-y-2">
            <h4 className="font-medium">Select Runs to Include</h4>
            <p className="text-sm text-muted-foreground">
              Leave all unchecked to include all runs in the report bundle
            </p>
            
            {runs.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No runs available</p>
                <p className="text-sm">Complete some image generations to see them here</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {runs.map((run) => (
                  <div 
                    key={run.run_id} 
                    className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-muted/50"
                  >
                    <Checkbox
                      checked={selectedRuns.has(run.run_id)}
                      onCheckedChange={() => toggleRunSelection(run.run_id)}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2 mb-1">
                        <Badge variant="outline" className="font-mono text-xs">
                          {run.run_id.slice(0, 8)}...
                        </Badge>
                        <Badge className={getGenerationTypeColor(run.generation_type)}>
                          {(run.generation_type || '').toUpperCase()}
                        </Badge>
                        <span className="text-sm text-muted-foreground">
                          {formatTimestamp(run.timestamp)}
                        </span>
                      </div>
                      <p className="text-sm font-medium line-clamp-1">{run.prompt}</p>
                      <div className="flex items-center space-x-4 text-xs text-muted-foreground mt-1">
                        <span>Model: {run.model}</span>
                        <span>Seed: {run.seed}</span>
                        <span>Steps: {run.steps}</span>
                        <span>CFG: {run.cfg_scale}</span>
                        <span>Images: {run.generated_images?.length || 0}</span>
                        {run.clip_score_mean !== null && (
                          <span>CLIP cosine: {run.clip_score_mean?.toFixed(3) ?? "N/A"}</span>
                        )}
                        {run.macro_precision !== undefined && (
                          <span>Legacy detector precision: {run.macro_precision?.toFixed(3) ?? "N/A"}</span>
                        )}
                        {run.macro_recall !== undefined && (
                          <span>Legacy detector recall: {run.macro_recall?.toFixed(3) ?? "N/A"}</span>
                        )}
                        {run.macro_f1 !== undefined && (
                          <span>Legacy detector F1: {run.macro_f1?.toFixed(3) ?? "N/A"}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Report Bundle Contents</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center space-x-3">
              <FileText className="h-4 w-4 text-blue-500" />
              <span className="font-medium">results.csv</span>
              <span className="text-sm text-muted-foreground">
                - Tabular data with all run metadata and configurations
              </span>
            </div>
            <div className="flex items-center space-x-3">
              <FileText className="h-4 w-4 text-green-500" />
              <span className="font-medium">config.json</span>
              <span className="text-sm text-muted-foreground">
                - Detailed configuration data for each run
              </span>
            </div>
            <div className="flex items-center space-x-3">
              <FileText className="h-4 w-4 text-purple-500" />
              <span className="font-medium">images/</span>
              <span className="text-sm text-muted-foreground">
                - Generated images from all included runs
              </span>
            </div>
            <div className="flex items-center space-x-3">
              <FileText className="h-4 w-4 text-orange-500" />
              <span className="font-medium">README.md</span>
              <span className="text-sm text-muted-foreground">
                - Documentation and schema information
              </span>
            </div>
          </div>
          
          <Separator className="my-4" />
          
          <div className="text-sm text-muted-foreground">
            <p><strong>CSV Schema:</strong> run_id, timestamp, model, vae, prompt, negative_prompt, seed, sampler, steps, cfg_scale, width, height, batch_size, batch_count, generation_type, image_paths, loras, controlnets, workflow_hash</p>
            <p className="mt-2"><strong>Validation:</strong> All required CSV columns are verified, and all image paths resolve to files present in the zip bundle.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ReportBundlePage; 
