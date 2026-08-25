import React, { useState, useEffect } from 'react';
import { FamilyProfile, UserProfile, AllergenKey, DietType, SpecialCondition } from '../types';
import { 
  Users, 
  UserPlus, 
  ShieldCheck, 
  Check, 
  Trash2, 
  Edit3, 
  X, 
  Heart, 
  Sparkles,
  AlertCircle
} from 'lucide-react';

interface FamilyProfilesModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeProfile: UserProfile;
  onProfileSwitched: (newProfile: UserProfile) => void;
}

export const FamilyProfilesModal: React.FC<FamilyProfilesModalProps> = ({
  isOpen,
  onClose,
  activeProfile,
  onProfileSwitched
}) => {
  const [profiles, setProfiles] = useState<FamilyProfile[]>([]);
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<Partial<FamilyProfile>>({
    name: '',
    role: 'Child',
    avatarColor: 'blue',
    allergies: [],
    customAllergens: [],
    dietType: 'omnivore',
    specialConditions: []
  });

  useEffect(() => {
    if (isOpen) {
      fetchProfiles();
    }
  }, [isOpen]);

  const fetchProfiles = async () => {
    try {
      const res = await fetch('/api/family-profiles');
      if (res.ok) {
        const data = await res.json();
        setProfiles(data);
      }
    } catch (e) {
      console.warn('Could not fetch family profiles:', e);
    }
  };

  const handleSwitchProfile = async (profileId: string) => {
    try {
      const res = await fetch('/api/family-profiles/switch', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profileId })
      });
      if (res.ok) {
        const current = await res.json();
        onProfileSwitched(current);
        onClose();
      }
    } catch (e) {
      console.warn('Profile switch failed:', e);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editData.name) return;

    const newProfile: FamilyProfile = {
      id: editData.id || `profile_${Date.now()}_${Math.random().toString(36).substring(2, 5)}`,
      name: editData.name,
      role: editData.role || 'Member',
      avatarColor: editData.avatarColor || 'blue',
      allergies: editData.allergies || [],
      customAllergens: editData.customAllergens || [],
      dietType: (editData.dietType as DietType) || 'omnivore',
      specialConditions: editData.specialConditions || []
    };

    try {
      const res = await fetch('/api/family-profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProfile)
      });
      if (res.ok) {
        const updatedList = await res.json();
        setProfiles(updatedList);
        setIsEditing(false);
        if (activeProfile.id === newProfile.id) {
          onProfileSwitched({
            ...activeProfile,
            name: newProfile.name,
            allergies: newProfile.allergies,
            customAllergens: newProfile.customAllergens,
            dietType: newProfile.dietType,
            specialConditions: newProfile.specialConditions
          });
        }
      }
    } catch (e) {
      console.warn('Error saving profile:', e);
    }
  };

  const handleDeleteProfile = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (profiles.length <= 1) return;
    try {
      const res = await fetch(`/api/family-profiles/${id}`, { method: 'DELETE' });
      if (res.ok) {
        const updated = await res.json();
        setProfiles(updated);
        if (activeProfile.id === id && updated.length > 0) {
          onProfileSwitched({
            id: updated[0].id,
            name: updated[0].name,
            role: updated[0].role,
            allergies: updated[0].allergies,
            customAllergens: updated[0].customAllergens,
            dietType: updated[0].dietType,
            specialConditions: updated[0].specialConditions
          });
        }
      }
    } catch (e) {
      console.warn('Error deleting profile:', e);
    }
  };

  if (!isOpen) return null;

  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-600 text-white border-blue-700',
    amber: 'bg-amber-600 text-white border-amber-700',
    purple: 'bg-purple-600 text-white border-purple-700',
    emerald: 'bg-emerald-600 text-white border-emerald-700',
    rose: 'bg-rose-600 text-white border-rose-700'
  };

  const standardAllergens: AllergenKey[] = [
    'peanut', 'tree_nut', 'milk', 'gluten', 'egg', 'soy', 'fish', 'shellfish', 'sesame', 'fragrance'
  ];

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-2xl w-full overflow-hidden text-slate-900 animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="p-6 bg-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-blue-500/20 text-blue-300 border border-blue-400/30">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold">Household & Family Profiles</h3>
              <p className="text-xs text-slate-400">
                Switch profiles to instantly re-evaluate products against each member's biological safety profile.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {!isEditing ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Select Active Household Member
                </h4>
                <button
                  onClick={() => {
                    setEditData({
                      name: '',
                      role: 'Child',
                      avatarColor: 'emerald',
                      allergies: [],
                      customAllergens: [],
                      dietType: 'omnivore',
                      specialConditions: []
                    });
                    setIsEditing(true);
                  }}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-xs font-bold transition-colors"
                >
                  <UserPlus className="w-3.5 h-3.5" />
                  <span>Add Family Member</span>
                </button>
              </div>

              {/* Profiles List */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {profiles.map((p) => {
                  const isActive = activeProfile.id === p.id || (!activeProfile.id && p.id === 'profile_primary');
                  return (
                    <div
                      key={p.id}
                      onClick={() => handleSwitchProfile(p.id)}
                      className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                        isActive
                          ? 'bg-blue-50/50 border-blue-500 shadow-sm ring-2 ring-blue-500/20'
                          : 'bg-white hover:bg-slate-50 border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <div>
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-3">
                            <div className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm border ${colorClasses[p.avatarColor] || colorClasses.blue}`}>
                              {p.name.charAt(0)}
                            </div>
                            <div>
                              <div className="flex items-center space-x-1.5">
                                <h5 className="font-bold text-sm text-slate-900">{p.name}</h5>
                                {isActive && (
                                  <span className="px-1.5 py-0.2 rounded bg-blue-600 text-white text-[9px] font-bold uppercase">
                                    Active
                                  </span>
                                )}
                              </div>
                              <span className="text-xs text-slate-500 font-medium">{p.role}</span>
                            </div>
                          </div>

                          <div className="flex items-center space-x-1">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditData(p);
                                setIsEditing(true);
                              }}
                              className="p-1.5 text-slate-400 hover:text-slate-700 rounded transition-colors"
                              title="Edit Member Profile"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            {profiles.length > 1 && (
                              <button
                                onClick={(e) => handleDeleteProfile(p.id, e)}
                                className="p-1.5 text-slate-400 hover:text-rose-600 rounded transition-colors"
                                title="Remove Profile"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Summary tags */}
                        <div className="mt-3 pt-3 border-t border-slate-100 space-y-1.5 text-xs text-slate-600">
                          <div>
                            <span className="text-[10px] uppercase font-bold text-slate-400 block">Allergies:</span>
                            <span className="text-slate-800 font-medium">
                              {p.allergies.length > 0 ? p.allergies.join(', ') : 'None recorded'}
                            </span>
                          </div>
                          <div className="flex items-center space-x-2">
                            <span className="text-[10px] uppercase font-bold text-slate-400">Diet:</span>
                            <span className="capitalize font-semibold text-slate-800">{p.dietType}</span>
                          </div>
                        </div>
                      </div>

                      <div className="mt-4 pt-2">
                        <span className={`block w-full text-center py-1.5 rounded-lg text-xs font-bold ${
                          isActive ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'
                        }`}>
                          {isActive ? 'Currently Active' : 'Click to Switch'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Member Profile Form */
            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-200">
                <h4 className="text-sm font-bold text-slate-900">
                  {editData.id ? 'Edit Household Member' : 'Add New Household Member'}
                </h4>
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="text-xs text-slate-500 hover:text-slate-800 font-semibold"
                >
                  Cancel
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Full Name</label>
                  <input
                    type="text"
                    required
                    value={editData.name || ''}
                    onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                    placeholder="e.g. Liam, Elena, Grandpa"
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Relationship / Role</label>
                  <select
                    value={editData.role || 'Child'}
                    onChange={(e) => setEditData({ ...editData, role: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="Self">Self (Primary)</option>
                    <option value="Child">Child</option>
                    <option value="Partner">Partner / Spouse</option>
                    <option value="Parent">Parent / Senior</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              {/* Diet Type */}
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Diet Standard</label>
                <select
                  value={editData.dietType || 'omnivore'}
                  onChange={(e) => setEditData({ ...editData, dietType: e.target.value as DietType })}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 capitalize"
                >
                  {['omnivore', 'vegan', 'vegetarian', 'keto', 'halal', 'kosher', 'diabetic', 'low_sugar', 'gluten_free', 'low_sodium'].map(d => (
                    <option key={d} value={d} className="capitalize">{d.replace('_', ' ')}</option>
                  ))}
                </select>
              </div>

              {/* Allergens Selector */}
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">
                  Select Allergies & Intolerances
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {standardAllergens.map((alg) => {
                    const isSelected = editData.allergies?.includes(alg);
                    return (
                      <button
                        type="button"
                        key={alg}
                        onClick={() => {
                          const current = editData.allergies || [];
                          const updated = isSelected 
                            ? current.filter(a => a !== alg) 
                            : [...current, alg];
                          setEditData({ ...editData, allergies: updated });
                        }}
                        className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-all ${
                          isSelected
                            ? 'bg-rose-50 border-rose-400 text-rose-800 font-bold'
                            : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        {alg}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="pt-3 border-t border-slate-200 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-sm"
                >
                  Save Member Profile
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
