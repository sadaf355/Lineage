// Real, client-side analysis of an uploaded file. No backend, no network call.
// This is genuinely computed from the file's pixel data — not looked up from
// a fixture. It is NOT a trained deepfake classifier: the "signal score" is a
// simple heuristic (edge irregularity + compression density) that stands in
// for one, and is labeled as such everywhere it's shown.

export type AnalysisResult = {
  kind: "image" | "video";
  fileName: string;
  fileSizeKB: number;
  width: number;
  height: number;
  previewUrl: string;
  averageHash: string; // real 64-bit average hash, hex-encoded
  edgeIrregularity: number; // 0-100, real computation on pixel data
  compressionDensity: number; // 0-100, real computation from bytes/pixel
  signalScore: number; // 0-100 combined heuristic
  frameTimestamp?: string; // for video, which frame was analyzed
};

const HASH_SIZE = 8; // 8x8 -> 64-bit hash

function drawToHashCanvas(source: CanvasImageSource, srcW: number, srcH: number) {
  const canvas = document.createElement("canvas");
  canvas.width = HASH_SIZE;
  canvas.height = HASH_SIZE;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(source, 0, 0, srcW, srcH, 0, 0, HASH_SIZE, HASH_SIZE);
  return ctx.getImageData(0, 0, HASH_SIZE, HASH_SIZE);
}

function averageHashFrom(imageData: ImageData): string {
  const gray: number[] = [];
  for (let i = 0; i < imageData.data.length; i += 4) {
    const r = imageData.data[i];
    const g = imageData.data[i + 1];
    const b = imageData.data[i + 2];
    gray.push(0.299 * r + 0.587 * g + 0.114 * b);
  }
  const avg = gray.reduce((a, b) => a + b, 0) / gray.length;
  let bits = "";
  for (const v of gray) bits += v >= avg ? "1" : "0";
  // pack 64 bits into 16 hex chars
  let hex = "";
  for (let i = 0; i < bits.length; i += 4) {
    hex += parseInt(bits.slice(i, i + 4), 2).toString(16);
  }
  return hex;
}

// Full-resolution grayscale sample (capped) used for the edge/compression heuristics.
function sampleFullRes(source: CanvasImageSource, srcW: number, srcH: number) {
  const cap = 256; // keep this fast regardless of source resolution
  const scale = Math.min(1, cap / Math.max(srcW, srcH));
  const w = Math.max(1, Math.round(srcW * scale));
  const h = Math.max(1, Math.round(srcH * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(source, 0, 0, srcW, srcH, 0, 0, w, h);
  return { imageData: ctx.getImageData(0, 0, w, h), w, h };
}

function edgeIrregularityScore(imageData: ImageData, w: number, h: number): number {
  // Simple Laplacian-style gradient magnitude, then look at how *uneven* the
  // edge energy is across the frame (variance of local gradient magnitude).
  // Real manipulated regions often blend unevenly with their surroundings,
  // which tends to show up as irregular local edge energy — this is a crude
  // proxy for that, not a real forensic technique.
  const gray = new Float32Array(w * h);
  for (let i = 0, p = 0; i < imageData.data.length; i += 4, p++) {
    gray[p] = 0.299 * imageData.data[i] + 0.587 * imageData.data[i + 1] + 0.114 * imageData.data[i + 2];
  }
  const mags: number[] = [];
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const idx = y * w + x;
      const gx = gray[idx + 1] - gray[idx - 1];
      const gy = gray[idx + w] - gray[idx - w];
      mags.push(Math.sqrt(gx * gx + gy * gy));
    }
  }
  if (mags.length === 0) return 0;
  const mean = mags.reduce((a, b) => a + b, 0) / mags.length;
  const variance = mags.reduce((a, b) => a + (b - mean) * (b - mean), 0) / mags.length;
  const stdDev = Math.sqrt(variance);
  // Normalize into a rough 0-100 band. These constants are tuned by hand
  // against a handful of sample photos, not statistically derived.
  const normalized = Math.min(100, (stdDev / 60) * 100);
  return Math.round(normalized);
}

function compressionDensityScore(fileSizeBytes: number, width: number, height: number): number {
  const pixels = Math.max(1, width * height);
  const bytesPerPixel = fileSizeBytes / pixels;
  // Typical, un-suspicious photo JPEGs land roughly in 0.15–1.2 bytes/px.
  // Push the score up the further outside that band the file falls.
  let score = 0;
  if (bytesPerPixel < 0.15) score = ((0.15 - bytesPerPixel) / 0.15) * 100;
  else if (bytesPerPixel > 1.2) score = Math.min(100, ((bytesPerPixel - 1.2) / 1.2) * 60);
  return Math.round(Math.min(100, score));
}

async function analyzeImageElement(
  img: HTMLImageElement,
  fileName: string,
  fileSizeBytes: number,
  previewUrl: string
): Promise<AnalysisResult> {
  const w = img.naturalWidth;
  const h = img.naturalHeight;
  const hashData = drawToHashCanvas(img, w, h);
  const averageHash = averageHashFrom(hashData);
  const { imageData, w: sw, h: sh } = sampleFullRes(img, w, h);
  const edgeIrregularity = edgeIrregularityScore(imageData, sw, sh);
  const compressionDensity = compressionDensityScore(fileSizeBytes, w, h);
  const signalScore = Math.round(edgeIrregularity * 0.65 + compressionDensity * 0.35);

  return {
    kind: "image",
    fileName,
    fileSizeKB: Math.round(fileSizeBytes / 1024),
    width: w,
    height: h,
    previewUrl,
    averageHash,
    edgeIrregularity,
    compressionDensity,
    signalScore,
  };
}

async function analyzeVideoElement(
  video: HTMLVideoElement,
  fileName: string,
  fileSizeBytes: number
): Promise<AnalysisResult> {
  const w = video.videoWidth;
  const h = video.videoHeight;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(video, 0, 0, w, h);
  const previewUrl = canvas.toDataURL("image/jpeg", 0.85);

  const hashData = drawToHashCanvas(canvas, w, h);
  const averageHash = averageHashFrom(hashData);
  const { imageData, w: sw, h: sh } = sampleFullRes(canvas, w, h);
  const edgeIrregularity = edgeIrregularityScore(imageData, sw, sh);
  const compressionDensity = compressionDensityScore(fileSizeBytes, w, h);
  const signalScore = Math.round(edgeIrregularity * 0.65 + compressionDensity * 0.35);

  return {
    kind: "video",
    fileName,
    fileSizeKB: Math.round(fileSizeBytes / 1024),
    width: w,
    height: h,
    previewUrl,
    averageHash,
    edgeIrregularity,
    compressionDensity,
    signalScore,
    frameTimestamp: video.currentTime.toFixed(2) + "s",
  };
}

export function analyzeFile(file: File): Promise<AnalysisResult> {
  const isVideo = file.type.startsWith("video/");
  const isImage = file.type.startsWith("image/");

  if (isImage) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        analyzeImageElement(img, file.name, file.size, url).then(resolve).catch(reject);
      };
      img.onerror = () => reject(new Error("Could not read this image file."));
      img.src = url;
    });
  }

  if (isVideo) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const video = document.createElement("video");
      video.preload = "auto";
      video.muted = true;
      video.src = url;
      video.onloadedmetadata = () => {
        video.currentTime = Math.min(video.duration / 2, video.duration - 0.05);
      };
      video.onseeked = () => {
        analyzeVideoElement(video, file.name, file.size)
          .then((r) => {
            URL.revokeObjectURL(url);
            resolve(r);
          })
          .catch(reject);
      };
      video.onerror = () => reject(new Error("Could not read this video file."));
    });
  }

  return Promise.reject(new Error("Unsupported file type — upload an image or video."));
}
