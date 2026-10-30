import { create } from 'zustand';
import { ReportBundleState, ReportBundleActions } from '@/types/reportBundle';

type ReportBundleStore = ReportBundleState & ReportBundleActions;

const API_BASE_URL = 'http://localhost:5006/api';

export const useReportBundleStore = create<ReportBundleStore>((set, get) => ({
  // Initial state
  generating: false,
  error: null,
  downloadUrl: null,

  // Actions
  generateReport: async (runIds?: string[]) => {
    set({ generating: true, error: null });
    try {
      const response = await fetch(`${API_BASE_URL}/report-bundle`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          run_ids: runIds || []
        }),
      });

      const data = await response.json();

      if (data.success === true) {
        set({ 
          generating: false,
          downloadUrl: data.download_url
        });
      } else {
        set({ 
          error: data.message || 'Failed to generate report bundle', 
          generating: false 
        });
      }
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to generate report bundle', 
        generating: false 
      });
    }
  },

  downloadReport: async () => {
    const { downloadUrl } = get();
    if (!downloadUrl) {
      set({ error: 'No report bundle available for download' });
      return;
    }

    try {
      const response = await fetch(downloadUrl);
      if (response.ok) {
        const blob = await response.blob();
        
        // Ensure blob has correct MIME type
        const zipBlob = new Blob([blob], { type: 'application/zip' });
        
        const url = window.URL.createObjectURL(zipBlob);
        const a = document.createElement('a');
        a.href = url;
        
        // Extract filename from download URL or use default
        const urlParts = downloadUrl.split('/');
        const filename = urlParts[urlParts.length - 1] || 'dreamlayer_report.zip';
        
        // Ensure .zip extension
        a.download = filename.endsWith('.zip') ? filename : filename + '.zip';
        
        // Force download on Mac Safari
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        
        // Clean up after a delay to ensure download starts
        setTimeout(() => {
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        }, 100);
      } else {
        set({ error: 'Failed to download report bundle' });
      }
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to download report bundle'
      });
    }
  },

  validateSchema: async (csvContent: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/report-bundle/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          csv_content: csvContent
        }),
      });

      const data = await response.json();
      return data.status === 'success' && data.valid;
    } catch (error) {
      console.error('Schema validation failed:', error);
      return false;
    }
  },

  clearError: () => {
    set({ error: null });
  },
})); 