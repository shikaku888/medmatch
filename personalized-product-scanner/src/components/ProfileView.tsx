import React, { useState, useEffect } from 'react';
import { UserProfile, DietType, SpecialCondition, SupportedLanguage } from '../types';
import { LANGUAGE_OPTIONS } from '../i18n';
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
  onApplyPreset
}) => {
  const [profile, setProfile] = useState<UserProfile>({ ...userProfile });
  const [customTagInput, setCustomTagInput] = useState('');
  const [isSaved, setIsSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setProfile({ ...userProfile });
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

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-slate-200 p-6 rounded-xl shadow-sm">
        <div className="flex items-center space-x-3.5">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center">
            <UserCircle className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Personal Suitability Profile
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Configure your allergies, dietary preferences, and physiological parameters for automatic product validation.
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
              <span>Profile Saved!</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              <span>Save Changes</span>
            </>
          )}
        </button>
      </div>

      {/* QUICK PRESETS */}
      <div className="bg-white border border-slate-200 p-5 rounded-xl space-y-3 shadow-sm">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Quick Persona Profiles (One-Click Presets)
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
              1. Declared Allergies & Critical Exclusions (High Priority)
            </h3>
          </div>
          <p className="text-xs text-slate-500">
            Any product containing these substances will trigger a direct safety conflict alert.
          </p>
        </div>

        {/* Food Allergens */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Food Allergens
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
            Cosmetic & Skincare Sensitizers
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
            Custom Allergen & Sensitivity Keywords
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
              2. Primary Dietary Regimen
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
              3. Physiological & Health Conditions
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
              4. Display & Interface Language
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
              5. Active Prescriptions & Herb-Drug Radar
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

        {/* SECTION 6: MEDICAL CONTEXT (AGE, ORGANS, PREGNANCY) */}
        <div className="bg-white border border-slate-200 p-6 rounded-xl space-y-4 shadow-sm">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <HeartPulse className="w-5 h-5 text-rose-600" />
              <h3 className="text-base font-bold text-slate-900">
                6. Medical Context (Age, Organs, Pregnancy)
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

    </div>
  );
};
