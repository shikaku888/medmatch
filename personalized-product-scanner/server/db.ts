import fs from 'fs';
import path from 'path';
import { UserProfile, ScanHistoryItem, ProductScanResult, FamilyProfile, HealthAnalyticsData, UserRoutineProduct } from '../src/types';

interface CacheEntry {
  key: string;
  data: any;
  cachedAt: number;
}

const STORAGE_FILE = path.join(process.cwd(), 'data_storage.json');

const DEFAULT_ROUTINE: UserRoutineProduct[] = [
  {
    id: 'routine_1',
    name: 'CeraVe Hydrating Cleanser',
    brand: 'CeraVe',
    step: 'cleanser',
    timeOfDay: 'both',
    activeIngredients: ['Ceramides', 'Hyaluronic Acid']
  },
  {
    id: 'routine_2',
    name: 'The Ordinary Niacinamide 10% + Zinc 1% Serum',
    brand: 'The Ordinary',
    step: 'serum',
    timeOfDay: 'am',
    activeIngredients: ['Niacinamide (Vitamin B3)', 'Zinc PCA']
  },
  {
    id: 'routine_3',
    name: 'Paula’s Choice 1% Retinol Treatment',
    brand: 'Paula’s Choice',
    step: 'treatment',
    timeOfDay: 'pm',
    activeIngredients: ['Retinol', 'Peptides']
  },
  {
    id: 'routine_4',
    name: 'La Roche-Posay Anthelios UVMune 400 Sunscreen',
    brand: 'La Roche-Posay',
    step: 'sunscreen',
    timeOfDay: 'am',
    activeIngredients: ['Mexoryl 400', 'Chemical UV Filters']
  }
];

// Default initial user profile
const DEFAULT_PROFILE: UserProfile = {
  id: 'profile_primary',
  name: 'Alex Rivera',
  role: 'Primary Account',
  avatarColor: 'blue',
  allergies: ['peanut', 'milk'],
  customAllergens: [],
  dietType: 'omnivore',
  specialConditions: [],
  updatedAt: new Date().toISOString()
};

const DEFAULT_FAMILY_PROFILES: FamilyProfile[] = [
  {
    id: 'profile_primary',
    name: 'Alex Rivera',
    role: 'Self (Primary)',
    avatarColor: 'blue',
    allergies: ['peanut', 'milk'],
    customAllergens: [],
    dietType: 'omnivore',
    specialConditions: []
  },
  {
    id: 'profile_child',
    name: 'Liam (6 y/o)',
    role: 'Child',
    avatarColor: 'amber',
    allergies: ['peanut', 'tree_nut', 'egg', 'sesame'],
    customAllergens: ['red 40', 'titanium dioxide'],
    dietType: 'omnivore',
    specialConditions: ['eczema']
  },
  {
    id: 'profile_partner',
    name: 'Elena',
    role: 'Partner',
    avatarColor: 'purple',
    allergies: ['fragrance', 'salicylic_acid', 'parabens'],
    customAllergens: [],
    dietType: 'vegan',
    specialConditions: ['pregnant', 'sensitive_skin']
  },
  {
    id: 'profile_parent',
    name: 'Arthur (Senior)',
    role: 'Parent',
    avatarColor: 'emerald',
    allergies: ['gluten'],
    customAllergens: ['high fructose corn syrup'],
    dietType: 'low_sodium',
    specialConditions: ['hypertension']
  }
];

class StorageDatabase {
  private cache: Map<string, CacheEntry> = new Map();
  private userProfile: UserProfile = { ...DEFAULT_PROFILE };
  private familyProfiles: FamilyProfile[] = [...DEFAULT_FAMILY_PROFILES];
  private routine: UserRoutineProduct[] = [...DEFAULT_ROUTINE];
  private history: ScanHistoryItem[] = [];

  constructor() {
    this.loadFromDisk();
  }

  private loadFromDisk() {
    try {
      if (fs.existsSync(STORAGE_FILE)) {
        const raw = fs.readFileSync(STORAGE_FILE, 'utf-8');
        const data = JSON.parse(raw);
        if (data.userProfile) this.userProfile = data.userProfile;
        if (Array.isArray(data.familyProfiles) && data.familyProfiles.length > 0) {
          this.familyProfiles = data.familyProfiles;
        }
        if (Array.isArray(data.routine) && data.routine.length > 0) {
          this.routine = data.routine;
        }
        if (Array.isArray(data.history)) this.history = data.history;
        if (data.cache && typeof data.cache === 'object') {
          for (const [k, v] of Object.entries(data.cache)) {
            this.cache.set(k, v as CacheEntry);
          }
        }
      }
    } catch (e) {
      console.warn('Could not load storage from disk, using in-memory default:', e);
    }
  }

  private saveToDisk() {
    try {
      const cacheObj: Record<string, CacheEntry> = {};
      // Save top 200 cache items to prevent file bloat
      let count = 0;
      for (const [k, v] of this.cache.entries()) {
        if (count++ > 200) break;
        cacheObj[k] = v;
      }
      const data = {
        userProfile: this.userProfile,
        familyProfiles: this.familyProfiles,
        routine: this.routine,
        history: this.history.slice(0, 100),
        cache: cacheObj
      };
      fs.writeFileSync(STORAGE_FILE, JSON.stringify(data, null, 2), 'utf-8');
    } catch (e) {
      console.warn('Could not persist storage to disk:', e);
    }
  }

  // Cache methods
  getCache<T>(key: string, maxAgeMs: number = 1000 * 60 * 60 * 24 * 7): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;
    if (Date.now() - entry.cachedAt > maxAgeMs) {
      this.cache.delete(key);
      return null;
    }
    return entry.data as T;
  }

  setCache(key: string, data: any) {
    this.cache.set(key, {
      key,
      data,
      cachedAt: Date.now()
    });
    this.saveToDisk();
  }

  // User profile
  getUserProfile(): UserProfile {
    return this.userProfile;
  }

  updateUserProfile(profile: Partial<UserProfile>): UserProfile {
    this.userProfile = {
      ...this.userProfile,
      ...profile,
      updatedAt: new Date().toISOString()
    };

    // Keep active profile synced in familyProfiles if it matches
    const idx = this.familyProfiles.findIndex(p => p.id === this.userProfile.id);
    if (idx !== -1) {
      this.familyProfiles[idx] = {
        ...this.familyProfiles[idx],
        name: this.userProfile.name || this.familyProfiles[idx].name,
        allergies: this.userProfile.allergies,
        customAllergens: this.userProfile.customAllergens,
        dietType: this.userProfile.dietType,
        specialConditions: this.userProfile.specialConditions
      };
    }

    this.saveToDisk();
    return this.userProfile;
  }

  // Family profiles
  getFamilyProfiles(): FamilyProfile[] {
    return this.familyProfiles;
  }

  switchFamilyProfile(profileId: string): UserProfile {
    const found = this.familyProfiles.find(p => p.id === profileId);
    if (found) {
      this.userProfile = {
        id: found.id,
        name: found.name,
        role: found.role,
        avatarColor: found.avatarColor,
        allergies: [...found.allergies],
        customAllergens: [...found.customAllergens],
        dietType: found.dietType,
        specialConditions: [...found.specialConditions],
        updatedAt: new Date().toISOString()
      };
      this.saveToDisk();
    }
    return this.userProfile;
  }

  addOrUpdateFamilyProfile(profile: FamilyProfile): FamilyProfile[] {
    const existingIndex = this.familyProfiles.findIndex(p => p.id === profile.id);
    if (existingIndex >= 0) {
      this.familyProfiles[existingIndex] = profile;
    } else {
      this.familyProfiles.push(profile);
    }
    if (this.userProfile.id === profile.id) {
      this.userProfile = {
        ...this.userProfile,
        name: profile.name,
        role: profile.role,
        allergies: profile.allergies,
        customAllergens: profile.customAllergens,
        dietType: profile.dietType,
        specialConditions: profile.specialConditions
      };
    }
    this.saveToDisk();
    return this.familyProfiles;
  }

  deleteFamilyProfile(id: string): FamilyProfile[] {
    if (this.familyProfiles.length <= 1) return this.familyProfiles;
    this.familyProfiles = this.familyProfiles.filter(p => p.id !== id);
    if (this.userProfile.id === id && this.familyProfiles.length > 0) {
      this.switchFamilyProfile(this.familyProfiles[0].id);
    }
    this.saveToDisk();
    return this.familyProfiles;
  }

  // Skincare Routine Shelf
  getRoutine(): UserRoutineProduct[] {
    return this.routine;
  }

  setRoutine(routine: UserRoutineProduct[]): UserRoutineProduct[] {
    this.routine = routine;
    this.saveToDisk();
    return this.routine;
  }

  addOrUpdateRoutineItem(item: UserRoutineProduct): UserRoutineProduct[] {
    const idx = this.routine.findIndex(r => r.id === item.id);
    if (idx >= 0) {
      this.routine[idx] = item;
    } else {
      this.routine.push({
        ...item,
        id: item.id || `routine_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`
      });
    }
    this.saveToDisk();
    return this.routine;
  }

  deleteRoutineItem(id: string): UserRoutineProduct[] {
    this.routine = this.routine.filter(r => r.id !== id);
    this.saveToDisk();
    return this.routine;
  }

  // Analytics
  getHealthAnalytics(): HealthAnalyticsData {
    const history = this.history;
    const total = history.length;
    if (total === 0) {
      return {
        averageCompatibilityScore: 100,
        totalProductsScanned: 0,
        safeCount: 0,
        warningCount: 0,
        dangerCount: 0,
        ultraProcessedCount: 0,
        ultraProcessedPercentage: 0,
        topAllergensAvoided: [],
        flaggedAdditivesEncountered: [],
        cleanProductRatio: 100
      };
    }

    const safeCount = history.filter(h => h.status === 'safe').length;
    const warningCount = history.filter(h => h.status === 'warning' || h.status === 'caution').length;
    const dangerCount = history.filter(h => h.status === 'danger').length;
    const totalScore = history.reduce((sum, h) => sum + (h.score || 0), 0);
    const avgScore = Math.round(totalScore / total);

    const ultraProcessed = history.filter(h => h.fullResult?.nutrition?.novaGroup === 4).length;
    const novaPercentage = Math.round((ultraProcessed / total) * 100);

    const allergenMap: Record<string, number> = {};
    const additiveMap: Record<string, { count: number; risk: string }> = {};

    history.forEach(h => {
      if (h.fullResult?.matchAssessment.warnings) {
        h.fullResult.matchAssessment.warnings.forEach(w => {
          if (w.category === 'allergy') {
            allergenMap[w.matchedItem] = (allergenMap[w.matchedItem] || 0) + 1;
          } else {
            additiveMap[w.matchedItem || w.title] = {
              count: ((additiveMap[w.matchedItem || w.title]?.count) || 0) + 1,
              risk: w.message
            };
          }
        });
      }
    });

    const topAllergensAvoided = Object.entries(allergenMap)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    const flaggedAdditivesEncountered = Object.entries(additiveMap)
      .map(([name, val]) => ({ name, count: val.count, risk: val.risk }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    const cleanProductRatio = Math.round((safeCount / total) * 100);

    return {
      averageCompatibilityScore: avgScore,
      totalProductsScanned: total,
      safeCount,
      warningCount,
      dangerCount,
      ultraProcessedCount: ultraProcessed,
      ultraProcessedPercentage: novaPercentage,
      topAllergensAvoided,
      flaggedAdditivesEncountered,
      cleanProductRatio
    };
  }

  // History
  getHistory(): ScanHistoryItem[] {
    return this.history;
  }

  addHistory(result: ProductScanResult): ScanHistoryItem {
    const item: ScanHistoryItem = {
      id: `scan_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      barcode: result.barcode,
      productName: result.productName,
      brand: result.brand,
      productType: result.productType,
      imageUrl: result.imageUrl,
      status: result.matchAssessment.status,
      score: result.matchAssessment.score,
      warningCount: result.matchAssessment.warnings.length,
      scannedAt: result.scannedAt,
      fullResult: result,
      favorite: false
    };

    // Remove older scan of same barcode if duplicate to keep history clean
    this.history = [item, ...this.history.filter(h => h.barcode !== result.barcode)].slice(0, 100);
    this.saveToDisk();
    return item;
  }

  toggleFavorite(historyId: string): boolean {
    const item = this.history.find(h => h.id === historyId);
    if (item) {
      item.favorite = !item.favorite;
      this.saveToDisk();
      return !!item.favorite;
    }
    return false;
  }

  clearHistory(): void {
    this.history = [];
    this.saveToDisk();
  }
}

export const db = new StorageDatabase();

