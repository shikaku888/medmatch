/**
 * Local OCR — Tesseract.js (Apache-2.0), no API key, no cloud.
 * Replaces Gemini Vision for label/receipt photo → text.
 * First call downloads the ~15MB `eng` traineddata from the CDN and caches it.
 */
import { createWorker } from 'tesseract.js';
import type { Worker } from 'tesseract.js';

let workerPromise: Promise<Worker> | null = null;

async function getWorker(): Promise<Worker> {
  if (!workerPromise) {
    workerPromise = createWorker('eng');
  }
  return workerPromise;
}

export async function ocrImageToText(imageBase64: string, mimeType = 'image/jpeg'): Promise<string> {
  if (!imageBase64) return '';
  const worker = await getWorker();
  const buffer = Buffer.from(imageBase64, 'base64');
  const { data } = await worker.recognize(buffer);
  return (data.text || '').trim();
}
