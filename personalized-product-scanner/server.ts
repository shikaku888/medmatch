import express from 'express';
import path from 'path';
import dotenv from 'dotenv';
import { createServer as createViteServer } from 'vite';
import { db } from './server/db';
import { getProductFromOFF } from './server/services/off_client';
import { searchUSDAFood } from './server/services/usda_client';
import { analyzeCosmeticIngredients } from './server/services/inci_client';
import { getPubMedResearch } from './server/services/pubmed_client';
import { parseProductImageWithGemini, parseRawIngredientsTextWithGemini } from './server/services/gemini_vision';
import { assessProductMatch } from './server/services/matcher';
import { generateSafeSwaps } from './server/services/smart_swaps';
import { askGeminiDietitian } from './server/services/ai_chat';
import { analyzeIngredientSafety, extractRegulatoryBadges } from './server/services/ingredient_safety';
import { checkHerbDrugInteractions, HERB_DRUG_DATABASE } from './server/services/herb_drug_interactions';
import { DEMO_PRODUCTS } from './server/demoData';
import { SUPERMARKET_STORES, MARKET_PRODUCTS } from './server/marketPresets';
import { parseAndAuditReceiptWithGemini } from './server/services/receipt_scanner';
import { getAllCrossReactivityRules } from './server/services/cross_reactivity';
import { extractSkincareActives, analyzeSkincareRoutineConflicts } from './server/services/skincare_conflicts';
import { ProductScanResult, FamilyProfile, UserRoutineProduct, SupportedCountry, MedMatchAnalysis, SafeSwapRecommendation } from './src/types';
import { normalizeIngredient, analyzeMedications, medMatchStats } from './server/services/medmatch_client';

dotenv.config();

/** Compute the MedMatch medical analysis for a product's ingredients + user medications. */
async function computeMedMatch(ingredientsList: string[], currentProfile: any): Promise<MedMatchAnalysis> {
  const items: any[] = [];
  const seen = new Set<string>();
  const pushHit = (raw: string, hit: any) => {
    const key = hit.kind + ':' + hit.id;
    if (seen.has(key)) return;
    seen.add(key);
    items.push({ name: raw, kind: hit.kind, matched: { kind: hit.kind, id: hit.id } });
  };
  for (const ing of (ingredientsList || []).slice(0, 20)) {
    try {
      const hit = await normalizeIngredient(ing);
      if (hit) pushHit(ing, hit);
    } catch { /* ingredient normalization is best-effort */ }
  }
  const meds = currentProfile?.medications || [];
  for (const med of (meds as string[]).slice(0, 20)) {
    try {
      const hit = await normalizeIngredient(med);
      if (hit) pushHit(med, hit);
    } catch { /* best-effort */ }
  }
  if (!items.length) {
    return { matched: [], interactions: [], unmatched: (ingredientsList || []).slice(0, 20), depletions: [] };
  }
  const patientProfile = currentProfile ? {
    age: currentProfile.age,
    gender: currentProfile.gender,
    pregnancyStatus: currentProfile.pregnancyStatus,
    kidneyFunction: currentProfile.kidneyFunction,
    liverFunction: currentProfile.liverFunction,
  } : null;
  return analyzeMedications(items, patientProfile);
}

/**
 * Verify a swap candidate against the user's medication list with the 7-layer engine.
 * Only interactions involving at least one SWAP ingredient count — pre-existing
 * medication-vs-medication findings must not penalize the candidate.
 */
async function verifySwapSafety(
  activeIngredients: string[],
  currentProfile: any
): Promise<NonNullable<SafeSwapRecommendation['medMatchVerification']>> {
  const empty = { verified: false, majorCount: 0, moderateCount: 0, minorCount: 0, clean: true };
  const ings = (activeIngredients || []).map(i => String(i).trim()).filter(Boolean).slice(0, 15);
  if (!ings.length) return empty;

  try {
    const swapRaw = new Set<string>();
    const items: any[] = [];
    for (const ing of ings) {
      const hit = await normalizeIngredient(ing);
      if (hit) {
        swapRaw.add(ing.toLowerCase());
        items.push({ name: ing, kind: hit.kind, matched: { kind: hit.kind, id: hit.id } });
      }
    }
    const meds = (currentProfile?.medications || []) as string[];
    for (const med of meds.slice(0, 20)) {
      const hit = await normalizeIngredient(med);
      if (hit) items.push({ name: med, kind: hit.kind, matched: { kind: hit.kind, id: hit.id } });
    }
    if (!items.length) return empty;

    const patientProfile = currentProfile ? {
      age: currentProfile.age,
      gender: currentProfile.gender,
      pregnancyStatus: currentProfile.pregnancyStatus,
      kidneyFunction: currentProfile.kidneyFunction,
      liverFunction: currentProfile.liverFunction,
    } : null;
    const analysis = await analyzeMedications(items, patientProfile);

    // Canonical labels/ids contributed by the SWAP (not by the user's meds)
    const swapLabels = new Set<string>();
    const swapIds = new Set<string>();
    for (const m of analysis.matched || []) {
      if (swapRaw.has(String(m.input).toLowerCase())) {
        swapLabels.add(m.label);
        swapIds.add(m.id);
      }
    }
    const relevant = (analysis.interactions || []).filter(i =>
      swapLabels.has(i.a.label) || swapLabels.has(i.b.label) ||
      swapIds.has(i.a.id) || swapIds.has(i.b.id)
    );
    const majorCount = relevant.filter(i => i.severity === 'major').length;
    const moderateCount = relevant.filter(i => i.severity === 'moderate').length;
    const minorCount = relevant.filter(i => i.severity === 'minor').length;
    return { verified: true, majorCount, moderateCount, minorCount, clean: majorCount === 0 };
  } catch (err) {
    console.warn('Swap verification failed (non-fatal):', err);
    return empty;
  }
}

async function startServer() {
  const app = express();
  const PORT = 3000;

  // JSON Body parsing (support image base64 payloads up to 15MB)
  app.use(express.json({ limit: '15mb' }));

  // --- API ROUTES ---

  // Health check
  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  });

  // MedMatch AI medical check (pure backend call, 7-layer logic lives in FastAPI)
  app.post('/api/medmatch/check', async (req, res) => {
    const { items } = req.body;
    const profile = req.body.profile || null;
    if (!Array.isArray(items) || !items.length) {
      return res.status(400).json({ error: 'items array is required' });
    }
    try {
      const normalized: any[] = [];
      const seen = new Set<string>();
      for (const it of items.slice(0, 30)) {
        const hit = await normalizeIngredient(String(it.name || ''));
        if (hit && !seen.has(hit.kind + ':' + hit.id)) {
          seen.add(hit.kind + ':' + hit.id);
          normalized.push({ name: it.name, kind: hit.kind, matched: { kind: hit.kind, id: hit.id } });
        }
      }
      const analysis = await analyzeMedications(normalized, profile);
      res.json(analysis);
    } catch (err: any) {
      res.status(502).json({ error: 'MedMatch backend unreachable: ' + (err.message || '') });
    }
  });

  app.get('/api/medmatch/stats', async (_req, res) => {
    try {
      res.json(await medMatchStats());
    } catch (err: any) {
      res.status(502).json({ error: 'MedMatch backend unreachable: ' + (err.message || '') });
    }
  });

  // User Profile Endpoints
  app.get('/api/profile', (req, res) => {
    const profile = db.getUserProfile();
    res.json(profile);
  });

  app.post('/api/profile', (req, res) => {
    const updated = db.updateUserProfile(req.body);
    res.json(updated);
  });

  // Family Profiles Multi-User Switcher Endpoints (Pro feature)
  app.get('/api/family-profiles', (req, res) => {
    res.json(db.getFamilyProfiles());
  });

  app.post('/api/family-profiles', (req, res) => {
    const updatedList = db.addOrUpdateFamilyProfile(req.body as FamilyProfile);
    res.json(updatedList);
  });

  app.put('/api/family-profiles/switch', (req, res) => {
    const { profileId } = req.body;
    if (!profileId) return res.status(400).json({ error: 'profileId is required' });
    const current = db.switchFamilyProfile(profileId);
    res.json(current);
  });

  app.delete('/api/family-profiles/:id', (req, res) => {
    const updatedList = db.deleteFamilyProfile(req.params.id);
    res.json(updatedList);
  });

  // Health Analytics & Biometric Exposure Dashboard
  app.get('/api/analytics', (req, res) => {
    const analytics = db.getHealthAnalytics();
    res.json(analytics);
  });

  // AI Dietitian & Toxicologist Chat Assistant
  app.post('/api/ai-chat', async (req, res) => {
    const { question, product, profile } = req.body;
    if (!question) return res.status(400).json({ error: 'Question is required' });

    const currentProfile = profile || db.getUserProfile();
    const answer = await askGeminiDietitian(question, product, currentProfile);
    res.json({ answer });
  });

  // Smart Safe Swaps Generator
  app.post('/api/smart-swaps', async (req, res) => {
    const { product, profile } = req.body;
    if (!product) return res.status(400).json({ error: 'Product data required' });

    const currentProfile = profile || db.getUserProfile();
    const swaps = await generateSafeSwaps(product, currentProfile);
    // Layer-7 style gate: verify every candidate against the user's meds before recommending it.
    const verified = await Promise.all(swaps.map(async swap => ({
      ...swap,
      medMatchVerification: await verifySwapSafety(swap.activeIngredients || [], currentProfile),
    })));
    verified.sort((a, b) => {
      const av = a.medMatchVerification?.verified ? (a.medMatchVerification.clean ? 0 : 1) : 2;
      const bv = b.medMatchVerification?.verified ? (b.medMatchVerification.clean ? 0 : 1) : 2;
      return av - bv;
    });
    res.json(verified);
  });

  // Supermarket & Local Store Presets Endpoints
  app.get('/api/markets', (req, res) => {
    const country = (req.query.country as SupportedCountry) || db.getUserProfile().country || 'US';
    const stores = SUPERMARKET_STORES.filter(s => s.country === 'GLOBAL' || s.country === country);
    const featuredProducts = MARKET_PRODUCTS.filter(p => p.country === 'GLOBAL' || p.country === country);

    res.json({
      stores: stores.length > 0 ? stores : SUPERMARKET_STORES,
      featuredProducts: featuredProducts.length > 0 ? featuredProducts : MARKET_PRODUCTS
    });
  });

  app.get('/api/markets/products', (req, res) => {
    const storeId = req.query.storeId as string;
    const category = req.query.category as string;
    const country = req.query.country as SupportedCountry;
    let filtered = MARKET_PRODUCTS;
    if (storeId) {
      filtered = filtered.filter(p => p.storeId === storeId);
    }
    if (country) {
      filtered = filtered.filter(p => p.country === 'GLOBAL' || p.country === country);
    }
    if (category && category !== 'All') {
      filtered = filtered.filter(p => p.category.toLowerCase().includes(category.toLowerCase()));
    }
    res.json(filtered);
  });

  // Herb-Drug Interactions Reference — proxy to the MedMatch FastAPI search
  // (hard-coded local DB removed; the medical data lives in the backend only)
  app.get('/api/herb-drug-interactions', async (req, res) => {
    const query = req.query.q as string;
    try {
      const { results } = await (await fetch(
        `${process.env.MEDMATCH_URL || 'http://127.0.0.1:8765'}/api/search?q=${encodeURIComponent(query || '')}&limit=12`
      )).json();
      res.json({ query: query || '', results });
    } catch {
      res.status(502).json({ error: 'MedMatch backend unreachable' });
    }
  });

  // Receipt & Supermarket Cart AI Audit Endpoint
  app.post('/api/scan/receipt', async (req, res) => {
    try {
      const { imageBase64, mimeType, receiptText, storeNameHint } = req.body;
      if (!imageBase64 && (!receiptText || receiptText.trim().length < 5)) {
        return res.status(400).json({ error: 'Receipt image or text content is required' });
      }

      const currentProfile = db.getUserProfile();
      const familyProfiles = db.getFamilyProfiles();

      const auditResult = await parseAndAuditReceiptWithGemini(
        { imageBase64, mimeType, receiptText, storeNameHint },
        currentProfile,
        familyProfiles
      );

      res.json(auditResult);
    } catch (err: any) {
      console.error('Receipt audit error:', err);
      res.status(500).json({ error: err.message || 'Failed to analyze grocery receipt' });
    }
  });

  // Batch / Pantry Audit Scanner Endpoint
  app.post('/api/batch-scan', async (req, res) => {
    const { barcodes, itemsText } = req.body;
    const currentProfile = db.getUserProfile();
    const results: ProductScanResult[] = [];

    // Process list of barcodes or text names
    const codes = Array.isArray(barcodes) ? barcodes : [];
    for (const code of codes.slice(0, 10)) {
      try {
        const demoItem = DEMO_PRODUCTS.find(p => p.barcode === code);
        const marketItem = MARKET_PRODUCTS.find(p => p.barcode === code);
        let productData: any = null;
        let source: ProductScanResult['source'] = 'openfoodfacts';

        if (demoItem) {
          productData = { ...demoItem, productName: demoItem.name };
          source = 'demo';
        } else if (marketItem) {
          productData = { ...marketItem, productName: marketItem.name };
          source = 'demo';
        } else {
          const offRes = await getProductFromOFF(code, currentProfile.country);
          if (offRes) {
            productData = offRes;
            source = offRes.source;
          }
        }

        if (productData) {
          const matchAssessment = await assessProductMatch(productData, currentProfile);
          const ingredientSafetyList = analyzeIngredientSafety(productData.ingredientsList || []);
          const regulatoryBadges = extractRegulatoryBadges(productData.ingredientsList || []);
          const userMeds = currentProfile.medications || [];
          const herbDrugAlerts = checkHerbDrugInteractions(productData.ingredientsList || [], userMeds);

          const fullRes: ProductScanResult = {
            barcode: code,
            productName: productData.productName,
            brand: productData.brand,
            productType: productData.productType,
            imageUrl: productData.imageUrl,
            ingredientsText: productData.ingredientsText,
            ingredientsList: productData.ingredientsList || [],
            allergens: productData.allergens || [],
            labels: productData.labels || [],
            nutrition: productData.nutrition,
            cosmetic: productData.cosmetic,
            cleanScoreBreakdown: productData.cleanScoreBreakdown,
            regulatoryBadges,
            herbDrugAlerts,
            countryOfOrigin: productData.countryOfOrigin,
            ingredientSafetyList,
            matchAssessment,
            source,
            scannedAt: new Date().toISOString()
          };
          db.addHistory(fullRes);
          results.push(fullRes);
        }
      } catch (err) {
        console.warn('Batch scan item error:', err);
      }
    }

    res.json({ results, count: results.length });
  });

  // History Endpoints
  app.get('/api/history', (req, res) => {
    const history = db.getHistory();
    res.json(history);
  });

  app.post('/api/history/favorite', (req, res) => {
    const { id } = req.body;
    if (!id) return res.status(400).json({ error: 'Missing ID' });
    const isFav = db.toggleFavorite(id);
    res.json({ id, favorite: isFav });
  });

  app.delete('/api/history', (req, res) => {
    db.clearHistory();
    res.json({ success: true });
  });

  // Demo products endpoint
  app.get('/api/demo-products', (req, res) => {
    res.json(DEMO_PRODUCTS);
  });

  // Cross-Reactivity Reference Rules Endpoint
  app.get('/api/cross-reactivity-rules', (req, res) => {
    const rules = getAllCrossReactivityRules();
    res.json(rules);
  });

  // Skincare Routine Shelf Endpoints
  app.get('/api/skincare-routine', (req, res) => {
    const routine = db.getRoutine();
    res.json(routine);
  });

  app.post('/api/skincare-routine', (req, res) => {
    const item = req.body;
    if (!item.name) return res.status(400).json({ error: 'Product name is required' });
    const updated = db.addOrUpdateRoutineItem(item);
    res.json(updated);
  });

  app.delete('/api/skincare-routine/:id', (req, res) => {
    const updated = db.deleteRoutineItem(req.params.id);
    res.json(updated);
  });

  app.post('/api/skincare-routine/audit', (req, res) => {
    const { newActives } = req.body;
    const routine = db.getRoutine();
    const auditResult = analyzeSkincareRoutineConflicts(routine, newActives || []);
    res.json(auditResult);
  });

  // PubMed Research Endpoint
  app.get('/api/pubmed', async (req, res) => {
    const ingredient = req.query.ingredient as string;
    const context = req.query.context as string | undefined;

    if (!ingredient) {
      return res.status(400).json({ error: 'Ingredient query parameter is required' });
    }

    try {
      const research = await getPubMedResearch(ingredient, context);
      res.json(research);
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // Main Barcode Scan Endpoint
  app.post('/api/scan', async (req, res) => {
    const { barcode, query } = req.body;

    if (!barcode && !query) {
      return res.status(400).json({ error: 'Barcode or search query is required' });
    }

    const currentProfile = db.getUserProfile();
    let productData: any = null;
    let source: ProductScanResult['source'] = 'openfoodfacts';

    const cleanBarcode = barcode ? barcode.trim() : '';

    // 1. Check Demo Dataset and Supermarket Market Presets first for instant testing
    const demoItem = DEMO_PRODUCTS.find(p => p.barcode === cleanBarcode);
    const marketItem = MARKET_PRODUCTS.find(p => p.barcode === cleanBarcode || (query && p.name.toLowerCase().includes(query.toLowerCase())));
    
    if (demoItem) {
      productData = {
        productName: demoItem.name,
        brand: demoItem.brand,
        productType: demoItem.type,
        imageUrl: demoItem.image,
        ingredientsText: demoItem.ingredientsText,
        ingredientsList: demoItem.ingredientsList,
        allergens: demoItem.allergens,
        labels: demoItem.labels,
        nutrition: demoItem.nutrition,
        cosmetic: demoItem.cosmetic
      };
      source = 'demo';
    } else if (marketItem) {
      productData = {
        productName: marketItem.name,
        brand: marketItem.brand,
        productType: marketItem.type,
        imageUrl: marketItem.image,
        ingredientsText: marketItem.ingredientsText,
        ingredientsList: marketItem.ingredientsList,
        allergens: marketItem.allergens,
        labels: marketItem.labels,
        nutrition: marketItem.nutrition,
        cosmetic: marketItem.cosmetic
      };
      source = 'demo';
    }

    // 2. Query Open Food Facts / Open Beauty Facts with country routing
    if (!productData && cleanBarcode) {
      const offRes = await getProductFromOFF(cleanBarcode, currentProfile.country);
      if (offRes) {
        productData = offRes;
        source = offRes.source;
      }
    }

    // 3. Query USDA FoodData Central fallback (if searching by name/query or barcode lookup)
    if (!productData && (query || cleanBarcode)) {
      const usdaRes = await searchUSDAFood(query || cleanBarcode);
      if (usdaRes) {
        productData = usdaRes;
        source = 'usda';
      }
    }

    // If still not found
    if (!productData) {
      return res.status(404).json({
        error: 'Product not found in Open Food Facts, Open Beauty Facts, or USDA databases.',
        barcode: cleanBarcode
      });
    }

    // Enhance cosmetic data if cosmetic type
    if (productData.productType === 'cosmetic' && !productData.cosmetic) {
      productData.cosmetic = analyzeCosmeticIngredients(
        productData.ingredientsList || [],
        productData.ingredientsText || ''
      );
    }

    // MedMatch AI analysis (ingredients + user medications -> FastAPI 7-layer backend)
    let medMatch;
    try {
      medMatch = await computeMedMatch(productData.ingredientsList || [], currentProfile);
    } catch (err) {
      console.warn('MedMatch analysis failed (non-fatal):', err);
      medMatch = { matched: [], interactions: [], unmatched: [], depletions: [] };
    }

    // Perform Personalized Match Assessment
    const matchAssessment = await assessProductMatch(productData, currentProfile);

    // Analyze Clean Chemistry Ingredient Toxicity & Regulatory Badges
    const ingredientSafetyList = analyzeIngredientSafety(productData.ingredientsList || []);
    const regulatoryBadges = extractRegulatoryBadges(productData.ingredientsList || []);

    // Check Herb-Drug Interaction against user's active medications
    const userMeds = currentProfile.medications || [];
    const herbDrugAlerts = checkHerbDrugInteractions(
      productData.ingredientsList || [],
      userMeds
    );

    const fullResult: ProductScanResult = {
      barcode: cleanBarcode || 'SEARCH_' + Date.now(),
      productName: productData.productName,
      brand: productData.brand,
      productType: productData.productType,
      imageUrl: productData.imageUrl,
      ingredientsText: productData.ingredientsText,
      ingredientsList: productData.ingredientsList || [],
      allergens: productData.allergens || [],
      labels: productData.labels || [],
      nutrition: productData.nutrition,
      cosmetic: productData.cosmetic,
      cleanScoreBreakdown: productData.cleanScoreBreakdown,
      regulatoryBadges,
      herbDrugAlerts,
      countryOfOrigin: productData.countryOfOrigin,
      ingredientSafetyList,
      crossReactivityAlerts: matchAssessment.crossReactivityAlerts,
      skincareActiveCheck: matchAssessment.skincareActiveCheck,
      matchAssessment,
      medMatch,
      source,
      scannedAt: new Date().toISOString()
    };

    // Save to history
    db.addHistory(fullResult);

    res.json(fullResult);
  });

  // Image Scan / OCR Endpoint (Gemini Vision)
  app.post('/api/scan/image', async (req, res) => {
    const { imageBase64, mimeType } = req.body;

    if (!imageBase64) {
      return res.status(400).json({ error: 'Image base64 data is required' });
    }

    try {
      const currentProfile = db.getUserProfile();
      const parsed = await parseProductImageWithGemini(imageBase64, mimeType || 'image/jpeg');

      let cosmeticProfile = undefined;
      if (parsed.productType === 'cosmetic') {
        cosmeticProfile = analyzeCosmeticIngredients(parsed.ingredientsList, parsed.ingredientsText);
      }

      let medMatch;
      try {
        medMatch = await computeMedMatch(parsed.ingredientsList || [], currentProfile);
      } catch (err) {
        console.warn('MedMatch analysis failed (non-fatal):', err);
        medMatch = { matched: [], interactions: [], unmatched: [], depletions: [] };
      }

      const matchAssessment = await assessProductMatch({
        productName: parsed.productName,
        productType: parsed.productType,
        ingredientsText: parsed.ingredientsText,
        ingredientsList: parsed.ingredientsList,
        allergens: parsed.allergens || [],
        labels: parsed.labels || [],
        nutrition: parsed.nutrition,
        cosmetic: cosmeticProfile
      }, currentProfile);

      const ingredientSafetyList = analyzeIngredientSafety(parsed.ingredientsList || []);
      const regulatoryBadges = extractRegulatoryBadges(parsed.ingredientsList || []);
      const userMeds = currentProfile.medications || [];
      const herbDrugAlerts = checkHerbDrugInteractions(parsed.ingredientsList || [], userMeds);

      const fullResult: ProductScanResult = {
        barcode: `PHOTO_${Date.now()}`,
        productName: parsed.productName,
        brand: parsed.brand,
        productType: parsed.productType,
        ingredientsText: parsed.ingredientsText,
        ingredientsList: parsed.ingredientsList,
        allergens: parsed.allergens || [],
        labels: parsed.labels || [],
        nutrition: parsed.nutrition,
        cosmetic: cosmeticProfile,
        cleanScoreBreakdown: {
          totalScore: matchAssessment.score,
          cleanScore: matchAssessment.score,
          ratingLevel: matchAssessment.score >= 75 ? 'excellent' : matchAssessment.score >= 50 ? 'good' : matchAssessment.score >= 30 ? 'mediocre' : 'bad',
          nutritionalQualityScore: 40,
          nutritionPoints: 40,
          additivesSafetyScore: 30,
          additivesPoints: 30,
          organicBioBonus: 0
        },
        regulatoryBadges,
        herbDrugAlerts,
        ingredientSafetyList,
        crossReactivityAlerts: matchAssessment.crossReactivityAlerts,
        skincareActiveCheck: matchAssessment.skincareActiveCheck,
        matchAssessment,
        medMatch,
        source: 'gemini_vision',
        scannedAt: new Date().toISOString()
      };

      db.addHistory(fullResult);
      res.json(fullResult);
    } catch (err: any) {
      console.error('Image scan OCR error:', err);
      res.status(500).json({ error: err.message || 'Failed to analyze product image' });
    }
  });

  // Raw Ingredient Text Scan
  app.post('/api/scan/text', async (req, res) => {
    const { text, name } = req.body;

    if (!text || text.trim().length < 3) {
      return res.status(400).json({ error: 'Ingredient text is required' });
    }

    try {
      const currentProfile = db.getUserProfile();
      const parsed = await parseRawIngredientsTextWithGemini(text, name);

      let cosmeticProfile = undefined;
      if (parsed.productType === 'cosmetic') {
        cosmeticProfile = analyzeCosmeticIngredients(parsed.ingredientsList, parsed.ingredientsText);
      }

      let medMatch;
      try {
        medMatch = await computeMedMatch(parsed.ingredientsList || [], currentProfile);
      } catch (err) {
        console.warn('MedMatch analysis failed (non-fatal):', err);
        medMatch = { matched: [], interactions: [], unmatched: [], depletions: [] };
      }

      const matchAssessment = await assessProductMatch({
        productName: parsed.productName,
        productType: parsed.productType,
        ingredientsText: parsed.ingredientsText,
        ingredientsList: parsed.ingredientsList,
        allergens: parsed.allergens || [],
        labels: parsed.labels || [],
        cosmetic: cosmeticProfile
      }, currentProfile);

      const ingredientSafetyList = analyzeIngredientSafety(parsed.ingredientsList || []);
      const regulatoryBadges = extractRegulatoryBadges(parsed.ingredientsList || []);
      const userMeds = currentProfile.medications || [];
      const herbDrugAlerts = checkHerbDrugInteractions(parsed.ingredientsList || [], userMeds);

      const fullResult: ProductScanResult = {
        barcode: `TEXT_${Date.now()}`,
        productName: parsed.productName,
        brand: parsed.brand,
        productType: parsed.productType,
        ingredientsText: parsed.ingredientsText,
        ingredientsList: parsed.ingredientsList,
        allergens: parsed.allergens || [],
        labels: parsed.labels || [],
        cosmetic: cosmeticProfile,
        cleanScoreBreakdown: {
          totalScore: matchAssessment.score,
          cleanScore: matchAssessment.score,
          ratingLevel: matchAssessment.score >= 75 ? 'excellent' : matchAssessment.score >= 50 ? 'good' : matchAssessment.score >= 30 ? 'mediocre' : 'bad',
          nutritionalQualityScore: 40,
          nutritionPoints: 40,
          additivesSafetyScore: 30,
          additivesPoints: 30,
          organicBioBonus: 0
        },
        regulatoryBadges,
        herbDrugAlerts,
        ingredientSafetyList,
        crossReactivityAlerts: matchAssessment.crossReactivityAlerts,
        skincareActiveCheck: matchAssessment.skincareActiveCheck,
        matchAssessment,
        medMatch,
        source: 'gemini_vision',
        scannedAt: new Date().toISOString()
      };

      db.addHistory(fullResult);
      res.json(fullResult);
    } catch (err: any) {
      console.error('Text analysis error:', err);
      res.status(500).json({ error: err.message || 'Failed to analyze text' });
    }
  });

  // --- VITE MIDDLEWARE ---
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa'
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
