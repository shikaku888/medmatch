import React, { useState, useEffect, useRef } from 'react';
import { ScheduleTimeline } from './ScheduleTimeline';
import { ReminderSettings } from './ReminderSettings';
import { MedicationPhotoIntake } from './MedicationPhotoIntake';
import { Clock, Download, Trash2 } from 'lucide-react';
import { UserProfile, DietType, SpecialCondition, SupportedLanguage, MedicationDetail, LabContext, PharmacogenomicsContext } from '../types';
import { LANGUAGE_OPTIONS, getTranslation } from '../i18n';
import { 
  UserCircle, 
  ShieldAlert, 
  Utensils, 
  HeartPulse, 
  Sparkles, 
  Check, 
  Plus, 
  X, 
  Save, 
  Info,
  Layers,
  Baby,
  Activity,
  Globe,
  Pill,
  Languages
} from 'lucide-react';

interface ProfileViewProps {
  userProfile: UserProfile;
  onSaveProfile: (updated: UserProfile) => Promise<void>;
  onApplyPreset: (presetKey: string) => void;
  onExportData: () => Promise<void>;
  onDeleteData: () => Promise<void>;
  language?: SupportedLanguage;
}

interface PharmacogenomicsCheckResult {
  status?: string;
  message?: string;
  recommendation?: string | null;
  relationships?: unknown[];
}

const FOOD_ALLERGENS = [
  { key: 'peanut', label: 'Peanuts & Groundnuts' },
  { key: 'tree_nut', label: 'Tree Nuts (Almond, Walnut, Cashew, Hazelnut)' },
  { key: 'milk', label: 'Milk & Dairy (Lactose, Whey, Casein)' },
  { key: 'gluten', label: 'Gluten & Wheat (Barley, Rye, Spelt)' },
  { key: 'egg', label: 'Eggs & Albumin' },
  { key: 'soy', label: 'Soybeans & Soy Lecithin' },
  { key: 'fish', label: 'Fish & Marine Derivatives' },
  { key: 'shellfish', label: 'Shellfish & Crustaceans (Shrimp, Crab)' },
  { key: 'sesame', label: 'Sesame Seeds & Tahini' },
  { key: 'sulfite', label: 'Sulfites & Preservatives (E220-E228)' },
  { key: 'mustard', label: 'Mustard' },
  { key: 'celery', label: 'Celery & Celeriac' }
];

const COSMETIC_ALLERGENS = [
  { key: 'fragrance', label: 'Fragrance / Parfum / Linalool / Limonene' },
  { key: 'parabens', label: 'Parabens (Methyl-, Propyl-, Butylparaben)' },
  { key: 'sulfates', label: 'Harsh Sulfates (SLS, SLES)' },
  { key: 'alcohol', label: 'Drying Denatured Alcohols (Alcohol Denat)' },
  { key: 'essential_oils', label: 'Essential Oils & Botanical Sensitizers' },
  { key: 'retinoid', label: 'Retinoids (Retinol, Retinal, Tretinoin)' },
  { key: 'salicylic_acid', label: 'Salicylic Acid (BHA)' }
];

const DIET_TYPES: { key: DietType; label: string; desc: string }[] = [
  { key: 'omnivore', label: 'Standard / Omnivore', desc: 'No dietary restrictions' },
  { key: 'vegan', label: 'Strict Vegan', desc: 'Zero animal meat, dairy, eggs, gelatin, honey or animal cosmetics' },
  { key: 'vegetarian', label: 'Vegetarian', desc: 'No meat, poultry, fish, gelatin or animal rennet' },
  { key: 'keto', label: 'Ketogenic / Low-Carb', desc: 'Flags products with >15g carbs or high added sugars' },
  { key: 'halal', label: 'Halal', desc: 'Flags pork, lard, non-halal gelatin, and ethyl alcohol' },
  { key: 'kosher', label: 'Kosher', desc: 'Flags pork, shellfish, and non-kosher processing' },
  { key: 'diabetic', label: 'Diabetic / Low Glycemic', desc: 'Flags high fructose corn syrup, maltodextrin, high sugars' },
  { key: 'gluten_free', label: 'Gluten-Free Diet', desc: 'Strict avoidance of wheat, rye, barley, spelt' },
  { key: 'low_sodium', label: 'Low Sodium / DASH', desc: 'Flags high sodium foods >400mg/100g' }
];

const SPECIAL_CONDITIONS: { key: SpecialCondition; label: string; desc: string; icon: any }[] = [
  { key: 'pregnant', label: 'Pregnant / Expecting', desc: 'Flags teratogenic retinoids, high salicylic acid, unpasteurized products', icon: Baby },
  { key: 'nursing', label: 'Nursing / Breastfeeding', desc: 'Flags active harsh chemicals and systemic penetrators', icon: HeartPulse },
  { key: 'sensitive_skin', label: 'Sensitive Skin / Eczema / Rosacea', desc: 'Flags synthetic fragrances, drying alcohols, and harsh surfactants', icon: Sparkles },
  { key: 'acne_prone', label: 'Acne-Prone Skin', desc: 'Flags comedogenic pore-clogging ingredients (rating 4-5)', icon: Activity },
  { key: 'hypertension', label: 'Hypertension / High Blood Pressure', desc: 'Strict sodium monitoring (<400mg/serving)', icon: HeartPulse }
];

export const ProfileView: React.FC<ProfileViewProps> = ({
  userProfile,
  onSaveProfile,
  onApplyPreset,
  onExportData,
  onDeleteData,
  language = 'en'
}) => {
  const t = (key: string, fb: string) => getTranslation(language, key, fb);
  const [profile, setProfile] = useState<UserProfile>({ ...userProfile });
  const [customTagInput, setCustomTagInput] = useState('');
  const [isSaved, setIsSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [dataAction, setDataAction] = useState<'export' | 'delete' | null>(null);
  const [dataActionError, setDataActionError] = useState<string | null>(null);
  const [pgxMedication, setPgxMedication] = useState((userProfile.medications || [])[0] || '');
  const [pgxCheck, setPgxCheck] = useState<PharmacogenomicsCheckResult | null>(null);
  const [isCheckingPgx, setIsCheckingPgx] = useState(false);
  const saveTimerRef = useRef<number | null>(null);

  useEffect(() => {
    setProfile({ ...userProfile });
    setPgxMedication((current) => userProfile.medications?.includes(current) ? current : (userProfile.medications || [])[0] || '');
    setPgxCheck(null);
  }, [userProfile]);

  const [daySchedule, setDaySchedule] = useState<{ a: string; b: string; min_hours: number; reason: string }[]>([]);

  useEffect(() => {
    const meds = (userProfile.medications || []).filter(Boolean);
    if (meds.length < 1) { setDaySchedule([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/api/medmatch/check', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items: meds.map((name) => ({ name })), profile: { age: userProfile.age } })
        });
        if (!res.ok) return;
        const analysis = await res.json();
        if (!cancelled) setDaySchedule(analysis.schedule || []);
      } catch { /* offline — timeline ẩn */ }
    })();
    return () => { cancelled = true; };
  }, [userProfile]);

  const toggleAllergy = (key: string) => {
    const exists = profile.allergies.includes(key);
    const updated = exists 
      ? profile.allergies.filter(k => k !== key)
      : [...profile.allergies, key];
    setProfile({ ...profile, allergies: updated });
    setIsSaved(false);
  };

  const toggleCondition = (key: SpecialCondition) => {
    const exists = profile.specialConditions.includes(key);
    const updated = exists
      ? profile.specialConditions.filter(k => k !== key)
      : [...profile.specialConditions, key];
    setProfile({ ...profile, specialConditions: updated });
    setIsSaved(false);
  };

  const addCustomAllergen = () => {
    const tag = customTagInput.trim();
    if (tag && !profile.customAllergens.includes(tag)) {
      setProfile({
        ...profile,
        customAllergens: [...profile.customAllergens, tag]
      });
      setCustomTagInput('');
      setIsSaved(false);
    }
  };

  const removeCustomAllergen = (tag: string) => {
    setProfile({
      ...profile,
      customAllergens: profile.customAllergens.filter(t => t !== tag)
    });
    setIsSaved(false);
  };

  const handleSave = async () => {
    setIsSaving(true);
    await onSaveProfile(profile);
    setIsSaving(false);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
  };

  const updatePharmacogenomics = (patch: Partial<PharmacogenomicsContext>) => {
    setProfile({
      ...profile,
      pharmacogenomics: { ...(profile.pharmacogenomics || {}), ...patch },
    });
    setIsSaved(false);
  };

  const handlePharmacogenomicsCheck = async () => {
    const drugId = pgxMedication.trim();
    if (!drugId) return;
    setIsCheckingPgx(true);
    setPgxCheck(null);
    try {
      const response = await fetch('/api/pharmacogenomics/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          drug_id: drugId,
          genotype: profile.pharmacogenomics?.genotype || null,
          phenotype: profile.pharmacogenomics?.phenotype || null,
          indication: profile.pharmacogenomics?.indication || null,
        }),
      });
      const result = await response.json();
      setPgxCheck(response.ok ? result : { status: 'error', message: result.detail || 'Could not check pharmacogenomics evidence.' });
    } catch {
      setPgxCheck({ status: 'error', message: 'Pharmacogenomics service unavailable.' });
    } finally {
      setIsCheckingPgx(false);
    }
  };

  const handleExport = async () => {
    setDataActionError(null);
    setDataAction('export');
    try {
      await onExportData();
    } catch {
      setDataActionError(t('dataExportError', 'Could not export your data. Please try again.'));
    } finally {
      setDataAction(null);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(t('dataDeleteConfirm', 'Delete all MedMatch data for this device? This cannot be undone.'))) return;
    setDataActionError(null);
    setDataAction('delete');
    try {
      await onDeleteData();
    } catch {
      setDataActionError(t('dataDeleteError', 'Could not delete your data. Please try again.'));
      setDataAction(null);
    }
  };
  const updateMedicationDetail = (medication: string, patch: Partial<MedicationDetail>) => {
    const current = profile.medicationDetails || [];
    const existing = current.find((item) => item.ingredient.toLowerCase() === medication.toLowerCase());
    const next: MedicationDetail = {
      ingredient: medication,
      ...(existing || {}),
      ...patch,
    };
    const without = current.filter((item) => item.ingredient.toLowerCase() !== medication.toLowerCase());
    setProfile({ ...profile, medicationDetails: [...without, next] });
    setIsSaved(false);
  };

  const updateLab = (index: number, patch: Partial<LabContext>) => {
    const labs = [...(profile.labs || [])];
    labs[index] = { ...(labs[index] || { name: '' }), ...patch };
    setProfile({ ...profile, labs });
    setIsSaved(false);
  };

  const removeLab = (index: number) => {
    setProfile({ ...profile, labs: (profile.labs || []).filter((_, i) => i !== index) });
    setIsSaved(false);
  };


  return (
    <div className="space-y-6">
      {/* My Day — medication timing from the 7-layer engine */}
      {daySchedule.length > 0 && (
        <div className="bg-white border border-teal-200 p-5 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-teal-600" />
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wide">
              {userProfile.language === 'vi' ? 'Giờ uống gợi ý hôm nay' : 'My day — suggested timing'}
            </h3>
          </div>
          <ScheduleTimeline
            schedule={daySchedule}
            herbAlerts={[]}
            language={userProfile.language}
            overrides={profile.scheduleTimes || {}}
            onOverride={(entity, time) => {
              const nextTimes = { ...(profile.scheduleTimes || {}), [entity]: time };
              const updated = { ...profile, scheduleTimes: nextTimes };
              setProfile(updated);
              setIsSaved(false);
              if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
              saveTimerRef.current = window.setTimeout(async () => {
                setIsSaving(true);
                await onSaveProfile(updated);
                setIsSaving(false);
                setIsSaved(true);
                setTimeout(() => setIsSaved(false), 2500);
              }, 700);
            }}
          />
        </div>
      )}

      <ReminderSettings profile={profile} language={language} />

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-slate-200 p-6 rounded-xl shadow-sm">
        <div className="flex items-center space-x-3.5">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center">
            <UserCircle className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              {t('profileTitle', 'Personal Suitability Profile')}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {t('profileSubtitle', 'Configure your allergies, dietary preferences, and physiological parameters for automatic product validation.')}
            </p>
          </div>
        </div>

        <button
          id="save-profile-btn"
          onClick={handleSave}
          disabled={isSaving}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold text-xs rounded-lg transition-all shadow-sm flex items-center justify-center space-x-2"
        >
          {isSaved ? (
            <>
              <Check className="w-4 h-4" />
              <span>{t('profileSavedSuccess', 'Profile Saved!')}</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              <span>{t('saveProfileBtn', 'Save Changes')}</span>
            </>
          )}
        </button>
      </div>

      {/* QUICK PRESETS */}
      <div className="bg-white border border-slate-200 p-5 rounded-xl space-y-3 shadow-sm">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            {t('pvPresets', 'Quick Persona Profiles (One-Click Presets)')}
          </h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          <button
            onClick={() => onApplyPreset('pregnant_sensitive')}
            className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 hover:border-blue-400 hover:bg-blue-50/20 text-left transition-all text-xs space-y-1 cursor-pointer shadow-2xs"
          >
            <span className="font-bold text-slate-900 block">🤰 Expecting & Sensitive Skin</span>
            <span className="text-[11px] text-slate-500 block">Avoids retinoids, BHA, fragrance, alcohol</span>
          </button>

          <button
            onClick={() => onApplyPreset('vegan_nut')}
            className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 hover:border-blue-400 hover:bg-blue-50/20 text-left transition-all text-xs space-y-1 cursor-pointer shadow-2xs"
          >
            <span className="font-bold text-slate-900 block">🌱 Strict Vegan + Nut Allergy</span>
            <span className="text-[11px] text-slate-500 block">Avoids animal byproducts & tree nuts</span>
          </button>

          <button
            onClick={() => onApplyPreset('diabetic_heart')}
            className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 hover:border-blue-400 hover:bg-blue-50/20 text-left transition-all text-xs space-y-1 cursor-pointer shadow-2xs"
          >
            <span className="font-bold text-slate-900 block">🩺 Diabetic + Blood Pressure</span>
            <span className="text-[11px] text-slate-500 block">Low glycemic, flags HFCS & sodium</span>
          </button>

          <button
            onClick={() => onApplyPreset('gluten_dairy')}
            className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 hover:border-blue-400 hover:bg-blue-50/20 text-left transition-all text-xs space-y-1 cursor-pointer shadow-2xs"
          >
            <span className="font-bold text-slate-900 block">🌾 Celiac + Lactose Free</span>
            <span className="text-[11px] text-slate-500 block">Zero gluten, dairy, whey, casein</span>
          </button>
        </div>
      </div>

      {/* SECTION 1: FOOD & COSMETIC ALLERGENS */}
      <div className="bg-white border border-slate-200 p-6 rounded-xl space-y-6 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-5 h-5 text-rose-600" />
            <h3 className="text-base font-bold text-slate-900">
              {t('pvSectionAllergies', '1. Declared Allergies & Critical Exclusions (High Priority)')}
            </h3>
          </div>
          <p className="text-xs text-slate-500">
            Any product containing these substances will trigger a direct safety conflict alert.
          </p>
        </div>

        {/* Food Allergens */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            {t('pvFoodAllergens', 'Food Allergens')}
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            {FOOD_ALLERGENS.map((item) => {
              const isSelected = profile.allergies.includes(item.key);
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => toggleAllergy(item.key)}
                  className={`p-3 rounded-lg border text-left transition-all flex items-start justify-between gap-2 cursor-pointer shadow-2xs ${
                    isSelected
                      ? 'bg-rose-50 border-rose-300 text-rose-950 font-semibold'
                      : 'bg-slate-50 border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-white'
                  }`}
                >
                  <span className="text-xs font-medium leading-snug">{item.label}</span>
                  <span className={`w-4 h-4 rounded flex items-center justify-center shrink-0 mt-0.5 ${
                    isSelected ? 'bg-rose-600 text-white' : 'border border-slate-300 bg-white'
                  }`}>
                    {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Cosmetic Allergens */}
        <div className="space-y-3 pt-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            {t('pvCosmeticSensitizers', 'Cosmetic & Skincare Sensitizers')}
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            {COSMETIC_ALLERGENS.map((item) => {
              const isSelected = profile.allergies.includes(item.key);
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => toggleAllergy(item.key)}
                  className={`p-3 rounded-lg border text-left transition-all flex items-start justify-between gap-2 cursor-pointer shadow-2xs ${
                    isSelected
                      ? 'bg-rose-50 border-rose-300 text-rose-950 font-semibold'
                      : 'bg-slate-50 border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-white'
                  }`}
                >
                  <span className="text-xs font-medium leading-snug">{item.label}</span>
                  <span className={`w-4 h-4 rounded flex items-center justify-center shrink-0 mt-0.5 ${
                    isSelected ? 'bg-rose-600 text-white' : 'border border-slate-300 bg-white'
                  }`}>
                    {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Custom User Allergens Tag Input */}
        <div className="space-y-3 pt-4 border-t border-slate-200">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            {t('pvCustomKeywords', 'Custom Allergen & Sensitivity Keywords')}
          </h4>
          <p className="text-xs text-slate-500">
            Add specific custom ingredients for the evaluator to monitor (e.g. "MSG", "Caffeine", "Coconut oil", "Aspartame").
          </p>

          <div className="flex gap-2">
            <input
              type="text"
              value={customTagInput}
              onChange={(e) => setCustomTagInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomAllergen(); } }}
              placeholder="Type custom ingredient name..."
              className="flex-1 px-4 py-2 bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 text-xs focus:outline-none focus:border-blue-600 focus:bg-white"
            />
            <button
              onClick={addCustomAllergen}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold rounded-lg transition-colors flex items-center space-x-1.5 shadow-2xs"
            >
              <Plus className="w-4 h-4" />
              <span>Add</span>
            </button>
          </div>

          {profile.customAllergens.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-2">
              {profile.customAllergens.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-md bg-rose-50 text-rose-800 border border-rose-200 text-xs font-semibold shadow-2xs"
                >
                  <span>{tag}</span>
                  <button
                    onClick={() => removeCustomAllergen(tag)}
                    className="p-0.5 hover:text-rose-950 rounded cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* SECTION 2: DIETARY REGIMEN */}
      <div className="bg-white border border-slate-200 p-6 rounded-xl space-y-4 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <Utensils className="w-5 h-5 text-blue-600" />
            <h3 className="text-base font-bold text-slate-900">
              {t('pvSectionDiet', '2. Primary Dietary Regimen')}
            </h3>
          </div>
          <p className="text-xs text-slate-500">
            Matches product nutrition facts and ingredients against your chosen dietary standard.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {DIET_TYPES.map((diet) => {
            const isSelected = profile.dietType === diet.key;
            return (
              <button
                key={diet.key}
                type="button"
                onClick={() => { setProfile({ ...profile, dietType: diet.key }); setIsSaved(false); }}
                className={`p-4 rounded-lg border text-left transition-all space-y-1.5 cursor-pointer shadow-2xs ${
                  isSelected
                    ? 'bg-blue-50/60 border-blue-500 text-blue-950 font-medium'
                    : 'bg-slate-50 border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900">{diet.label}</span>
                  <span className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center ${
                    isSelected ? 'border-blue-600 bg-blue-600' : 'border-slate-300 bg-white'
                  }`}></span>
                </div>
                <p className="text-[11px] text-slate-500 leading-normal">{diet.desc}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* SECTION 3: SPECIAL HEALTH CONDITIONS */}
      <div className="bg-white border border-slate-200 p-6 rounded-xl space-y-4 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <HeartPulse className="w-5 h-5 text-blue-600" />
            <h3 className="text-base font-bold text-slate-900">
              {t('pvSectionConditions', '3. Physiological & Health Conditions')}
            </h3>
          </div>
          <p className="text-xs text-slate-500">
            Applies scientific contraindications and safety guidelines for sensitive physiology and chronic considerations.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {SPECIAL_CONDITIONS.map((cond) => {
            const isSelected = profile.specialConditions.includes(cond.key);
            const Icon = cond.icon;
            return (
              <button
                key={cond.key}
                type="button"
                onClick={() => toggleCondition(cond.key)}
                className={`p-4 rounded-lg border text-left transition-all flex items-start space-x-3.5 cursor-pointer shadow-2xs ${
                  isSelected
                    ? 'bg-blue-50/60 border-blue-500 text-blue-950'
                    : 'bg-slate-50 border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-white'
                }`}
              >
                <div className={`p-2 rounded-lg mt-0.5 ${
                  isSelected ? 'bg-blue-100 text-blue-700' : 'bg-white border border-slate-200 text-slate-500'
                }`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="space-y-1 flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">{cond.label}</span>
                    <span className={`w-4 h-4 rounded flex items-center justify-center shrink-0 ${
                      isSelected ? 'bg-blue-600 text-white font-bold' : 'border border-slate-300 bg-white'
                    }`}>
                      {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-normal">{cond.desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* SECTION 4: DISPLAY & INTERFACE LANGUAGE */}
      <div className="bg-white border border-slate-200 p-6 rounded-xl space-y-4 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <Languages className="w-5 h-5 text-blue-600" />
            <h3 className="text-base font-bold text-slate-900">
              {t('pvSectionLanguage', '4. Display & Interface Language')}
            </h3>
          </div>
          <p className="text-xs text-slate-500">
            Select your preferred language for ingredient analysis, allergen warnings, and clinical toxicology breakdowns.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
          {LANGUAGE_OPTIONS.map((l) => {
            const isSelected = (profile.language || 'en') === l.code;
            return (
              <button
                key={l.code}
                type="button"
                onClick={() => {
                  const updated = { ...profile, language: l.code as SupportedLanguage };
                  setProfile(updated);
                  setIsSaved(false);
                  onSaveProfile(updated);
                }}
                className={`p-3 rounded-xl border text-center transition-all flex flex-col items-center justify-center space-y-1 cursor-pointer ${
                  isSelected
                    ? 'bg-blue-50/70 border-blue-500 ring-2 ring-blue-500/20 text-blue-950 font-bold'
                    : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-white'
                }`}
              >
                <span className="text-2xl">{l.flag}</span>
                <span className="text-xs font-bold">{l.name}</span>
                <span className="text-[10px] text-slate-500">{l.code.toUpperCase()}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* SECTION 5: ACTIVE MEDICATIONS (HERB-DRUG RADAR) */}
      <div className="bg-white border border-slate-200 p-6 rounded-xl space-y-4 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <Pill className="w-5 h-5 text-rose-600" />
            <h3 className="text-base font-bold text-slate-900">
              {t('pvSectionPrescriptions', '5. Active Prescriptions & Herb-Drug Radar')}
            </h3>
          </div>
          <p className="text-xs text-slate-500">
            Automatically check herbal foods, supplements, botanical extracts, and skincare against your active pharmaceutical prescriptions.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {['Warfarin', 'Aspirin', 'Metformin', 'Levothyroxine', 'Atorvastatin', 'Lisinopril', 'Sertraline', 'Ciprofloxacin'].map(med => {
            const hasMed = (profile.medications || []).some(m => m.toLowerCase() === med.toLowerCase());
            return (
              <button
                key={med}
                type="button"
                onClick={() => {
                  const currentMeds = profile.medications || [];
                  const updated = hasMed
                    ? currentMeds.filter(m => m.toLowerCase() !== med.toLowerCase())
                    : [...currentMeds, med];
                  setProfile({ ...profile, medications: updated });
                  setIsSaved(false);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all cursor-pointer ${
                  hasMed
                    ? 'bg-rose-600 text-white shadow-2xs font-bold'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200'
                }`}
              >
                <Pill className="w-3 h-3" />
                <span>{med}</span>
                {hasMed && <Check className="w-3 h-3 ml-0.5" />}
              </button>
            );
          })}
        </div>
      </div>
      <MedicationPhotoIntake
        language={language}
        onAdd={(newMedications) => {
          const current = profile.medications || [];
          const additions = newMedications.filter((medication) => !current.some((item) => item.toLowerCase() === medication.toLowerCase()));
          if (additions.length > 0) {
            setProfile({ ...profile, medications: [...current, ...additions] });
            setIsSaved(false);
          }
        }}
      />
      {(profile.medications || []).length > 0 && (
        <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-6 space-y-4">
          <div>
            <h4 className="text-sm font-bold text-slate-900">Medication details</h4>
            <p className="mt-1 text-xs text-slate-600">Add the prescribed strength and schedule. This metadata is carried into matching; it never changes the prescribed dose.</p>
          </div>
          <div className="space-y-4">
            {(profile.medications || []).map((medication) => {
              const detail = (profile.medicationDetails || []).find((item) => item.ingredient.toLowerCase() === medication.toLowerCase()) || { ingredient: medication };
              const fields: { key: keyof MedicationDetail; label: string; placeholder: string }[] = [
                { key: 'strength', label: 'Strength', placeholder: 'e.g. 5 mg' },
                { key: 'dose', label: 'Dose', placeholder: 'e.g. 1' },
                { key: 'unit', label: 'Unit', placeholder: 'mg' },
                { key: 'route', label: 'Route', placeholder: 'oral' },
                { key: 'formulation', label: 'Formulation', placeholder: 'tablet' },
                { key: 'frequency', label: 'Frequency', placeholder: 'once daily' },
                { key: 'timing', label: 'Timing', placeholder: '08:00 / with food' },
              ];
              return (
                <div key={medication} className="rounded-lg border border-white bg-white p-3">
                  <div className="mb-3 flex items-center gap-2 text-xs font-bold text-rose-900"><Pill className="h-3.5 w-3.5" />{medication}</div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {fields.map((field) => (
                      <label key={field.key} className="space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">{field.label}</span>
                        <input
                          type={field.key === 'dose' ? 'text' : 'text'}
                          value={detail[field.key] == null ? '' : String(detail[field.key])}
                          placeholder={field.placeholder}
                          onChange={(e) => updateMedicationDetail(medication, { [field.key]: e.target.value })}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-500/20"
                        />
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

        {/* SECTION 6: MEDICAL CONTEXT (AGE, ORGANS, PREGNANCY) */}
        <div className="bg-white border border-slate-200 p-6 rounded-xl space-y-4 shadow-sm">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <HeartPulse className="w-5 h-5 text-rose-600" />
              <h3 className="text-base font-bold text-slate-900">
                {t('pvSectionMedical', '6. Medical Context (Age, Organs, Pregnancy)')}
              </h3>
            </div>
            <p className="text-xs text-slate-500">
              Drives Beers Criteria (age 65+), QT-prolongation risk stacking, and renal/hepatic dose cautions in the MedMatch AI engine.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">Age</label>
              <input
                type="number"
                min={0}
                max={120}
                value={profile.age ?? ''}
                onChange={(e) => {
                  const v = e.target.value === '' ? undefined : Math.max(0, Math.min(120, Number(e.target.value)));
                  setProfile({ ...profile, age: v, pregnancyStatus: v !== undefined && v < 12 ? 'not_applicable' : profile.pregnancyStatus });
                  setIsSaved(false);
                }}
                placeholder="e.g. 67"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">Gender</label>
              <select
                value={profile.gender ?? ''}
                onChange={(e) => {
                  const g = (e.target.value || undefined) as UserProfile['gender'];
                  setProfile({ ...profile, gender: g, pregnancyStatus: g !== 'female' ? 'not_applicable' : profile.pregnancyStatus });
                  setIsSaved(false);
                }}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 outline-none"
              >
                <option value="">Not specified</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>

            {profile.gender === 'female' && (
              <>
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">Pregnancy Status</label>
                <select
                  value={profile.pregnancyStatus ?? 'not_applicable'}
                  onChange={(e) => { setProfile({ ...profile, pregnancyStatus: e.target.value as UserProfile['pregnancyStatus'] }); setIsSaved(false); }}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 outline-none"
                >
                  <option value="not_applicable">Not applicable</option>
                  <option value="trying_to_conceive">Trying to conceive</option>
                  <option value="pregnant">Pregnant</option>
                  <option value="breastfeeding">Breastfeeding</option>
                </select>
              </div>
              {profile.pregnancyStatus === 'pregnant' && (
                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase tracking-wide text-slate-700">Pregnancy trimester</label>
                  <select
                    value={profile.pregnancyTrimester ?? ''}
                    onChange={(e) => { setProfile({ ...profile, pregnancyTrimester: e.target.value ? Number(e.target.value) : undefined }); setIsSaved(false); }}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
                  >
                    <option value="">Unknown</option>
                    <option value="1">First</option>
                    <option value="2">Second</option>
                    <option value="3">Third</option>
                  </select>
                </div>
              )}
              </>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">Kidney Function</label>
              <select
                value={profile.kidneyFunction ?? 'normal'}
                onChange={(e) => { setProfile({ ...profile, kidneyFunction: e.target.value as UserProfile['kidneyFunction'] }); setIsSaved(false); }}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 outline-none"
              >
                <option value="normal">Normal</option>
                <option value="mild_impairment">Mild impairment</option>
                <option value="moderate_impairment">Moderate impairment</option>
                <option value="severe_impairment">Severe impairment</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wide text-slate-700">eGFR (optional)</label>
              <input
                type="number"
                min={0}
                max={200}
                value={profile.eGFR ?? ''}
                onChange={(e) => { setProfile({ ...profile, eGFR: e.target.value === '' ? undefined : Number(e.target.value) }); setIsSaved(false); }}
                placeholder="mL/min/1.73m²"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">Liver Function</label>
              <select
                value={profile.liverFunction ?? 'normal'}
                onChange={(e) => { setProfile({ ...profile, liverFunction: e.target.value as UserProfile['liverFunction'] }); setIsSaved(false); }}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 outline-none"
              >
                <option value="normal">Normal</option>
                <option value="mild_impairment">Mild impairment</option>
                <option value="moderate_impairment">Moderate impairment</option>
                <option value="severe_impairment">Severe impairment</option>
              </select>
            </div>
          </div>
        </div>

      <div className="rounded-xl border border-cyan-200 bg-cyan-50/40 p-6 space-y-4">
        <div>
          <h4 className="text-sm font-bold text-slate-900">7. Pharmacogenomics context (optional)</h4>
          <p className="mt-1 text-xs text-slate-600">
            Store only a genotype or phenotype reported by a qualified laboratory or clinician. MedMatch shows evidence for review; it never infers a result or recommends a dose.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">Genotype / variant</span>
            <input
              value={profile.pharmacogenomics?.genotype || ''}
              maxLength={240}
              placeholder="e.g. CYP2C19 *2/*2"
              onChange={(e) => updatePharmacogenomics({ genotype: e.target.value })}
              className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
            />
          </label>
          <label className="space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">Phenotype</span>
            <input
              value={profile.pharmacogenomics?.phenotype || ''}
              maxLength={120}
              placeholder="e.g. poor metabolizer"
              onChange={(e) => updatePharmacogenomics({ phenotype: e.target.value })}
              className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
            />
          </label>
          <label className="space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">Indication / context</span>
            <input
              value={profile.pharmacogenomics?.indication || ''}
              maxLength={240}
              placeholder="e.g. anticoagulation"
              onChange={(e) => updatePharmacogenomics({ indication: e.target.value })}
              className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
            />
          </label>
        </div>
        {(profile.medications || []).length > 0 && (
          <div className="rounded-lg border border-cyan-200 bg-white/80 p-3 space-y-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <label className="min-w-0 flex-1 space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">Medication to review</span>
                <select
                  value={pgxMedication}
                  onChange={(e) => { setPgxMedication(e.target.value); setPgxCheck(null); }}
                  className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                >
                  {(profile.medications || []).map((medication) => <option key={medication} value={medication}>{medication}</option>)}
                </select>
              </label>
              <button
                type="button"
                onClick={handlePharmacogenomicsCheck}
                disabled={isCheckingPgx || !pgxMedication}
                className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white hover:bg-cyan-800 disabled:opacity-50"
              >
                {isCheckingPgx ? 'Checking…' : 'Review evidence'}
              </button>
            </div>
            {pgxCheck && (
              <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-3 text-xs text-cyan-950">
                <p className="font-bold uppercase tracking-wide">{pgxCheck.status || 'unknown'}</p>
                <p className="mt-1">{pgxCheck.message || pgxCheck.recommendation || 'No automatic recommendation is available.'}</p>
                <p className="mt-1 text-cyan-800">
                  {pgxCheck.relationships?.length || 0} evidence relationship(s). Confirm interpretation with a clinician.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-6 space-y-4">
        <div>
          <h4 className="text-sm font-bold text-slate-900">Lab context (optional)</h4>
          <p className="mt-1 text-xs text-slate-600">Record observed values with units, date, and reference range. The engine only surfaces a clinician-review action; it never calculates a dose.</p>
        </div>
        <div className="space-y-3">
          {(profile.labs || []).map((lab, index) => (
            <div key={lab.id || index} className="grid grid-cols-1 gap-2 rounded-lg border border-white bg-white p-3 sm:grid-cols-5">
              {([
                ['name', 'Test', 'INR / eGFR / AST'],
                ['value', 'Value', 'e.g. 3.2'],
                ['unit', 'Unit', 'ratio / mL/min'],
                ['observedAt', 'Observed', 'YYYY-MM-DD'],
                ['referenceRange', 'Reference range', 'e.g. 0.8–1.2'],
              ] as const).map(([key, label, placeholder]) => (
                <label key={key} className="space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">{label}</span>
                  <input
                    value={lab[key] == null ? '' : String(lab[key])}
                    placeholder={placeholder}
                    onChange={(e) => updateLab(index, { [key]: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-2.5 py-2 text-xs outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  />
                </label>
              ))}
              <button type="button" onClick={() => removeLab(index)} className="self-end rounded-lg px-2 py-2 text-xs font-bold text-rose-700 hover:bg-rose-50">Remove</button>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setProfile({ ...profile, labs: [...(profile.labs || []), { id: `lab-${Date.now()}`, name: '' }] })}
          className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-300 bg-white px-3 py-2 text-xs font-bold text-indigo-800 hover:bg-indigo-50"
        >
          <Plus className="h-3.5 w-3.5" /> Add lab value
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-3">
        <div>
          <h4 className="text-sm font-bold text-slate-900">Your data</h4>
          <p className="mt-1 text-xs text-slate-600">
            Export a copy or permanently delete the profile, medications, routines, reminders, and scan history stored for this device.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleExport}
            disabled={dataAction !== null}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            {dataAction === 'export' ? 'Preparing export…' : 'Export my data'}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={dataAction !== null}
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-xs font-bold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {dataAction === 'delete' ? 'Deleting…' : 'Delete all data'}
          </button>
        </div>
        {dataActionError && <p className="text-xs font-medium text-rose-700">{dataActionError}</p>}
      </div>
    </div>
  );
};
