import { createContext, useContext, useState, ReactNode, useCallback } from "react";
import { analyzeFile, AnalysisResult } from "../lib/imageAnalysis";

type UploadState = {
  result: AnalysisResult | null;
  isAnalyzing: boolean;
  error: string | null;
  upload: (file: File) => Promise<void>;
  reset: () => void;
};

const UploadContext = createContext<UploadState | null>(null);

export function UploadProvider({ children }: { children: ReactNode }) {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(async (file: File) => {
    setIsAnalyzing(true);
    setError(null);
    try {
      const r = await analyzeFile(file);
      setResult(r);
    } catch (e: any) {
      setError(e?.message || "Could not analyze this file.");
      setResult(null);
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return (
    <UploadContext.Provider value={{ result, isAnalyzing, error, upload, reset }}>
      {children}
    </UploadContext.Provider>
  );
}

export function useUpload() {
  const ctx = useContext(UploadContext);
  if (!ctx) throw new Error("useUpload must be used within UploadProvider");
  return ctx;
}
