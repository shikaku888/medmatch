import crypto from 'node:crypto';

export type ScanInputType = 'code' | 'ingredient_photo' | 'text';

export interface ScanDraft {
  id: string;
  inputType: ScanInputType;
  inputValue?: string;
  imageBase64?: string;
  mimeType?: string;
  product: Record<string, unknown>;
  ingredientsList: string[];
  ingredientsText?: string;
  source: string;
  createdAt: string;
  expiresAt: number;
}

const drafts = new Map<string, ScanDraft>();
const TTL_MS = 15 * 60 * 1000;

function purgeExpired(now = Date.now()): void {
  for (const [id, draft] of drafts) {
    if (draft.expiresAt <= now) drafts.delete(id);
  }
}

export function createScanDraft(input: Omit<ScanDraft, 'id' | 'createdAt' | 'expiresAt'>): ScanDraft {
  purgeExpired();
  const now = Date.now();
  const draft: ScanDraft = {
    ...input,
    id: `draft_${now}_${crypto.randomBytes(4).toString('hex')}`,
    createdAt: new Date(now).toISOString(),
    expiresAt: now + TTL_MS,
  };
  drafts.set(draft.id, draft);
  return draft;
}

export function getScanDraft(id: string): ScanDraft | undefined {
  purgeExpired();
  return drafts.get(id);
}

export function deleteScanDraft(id: string): void {
  drafts.delete(id);
}
