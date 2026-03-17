import React, { useState, useEffect } from 'react';
import { UserProfile } from '../types';
import { getUserProfile, updateUserProfile } from '../services/api';

interface ProfileSettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

const DIET_OPTIONS = ["Mediterranean", "Vegetarian", "Vegan", "Keto", "Paleo", "Low-carb", "Gluten-free", "Rich in Omega3"];
const ALLERGY_OPTIONS = ["Gluten", "Dairy", "Peanuts", "Tree Nuts", "Soy", "Eggs", "Shellfish"];
const EXCLUSION_OPTIONS = ["Cilantro", "Mushrooms", "Olives", "Anchovies", "Liver", "Blue cheese", "Eggplant", "Beetroot"];
const GOAL_OPTIONS = ["Eat healthy", "Lose weight", "Build muscle", "Save money", "Save time"];
const MEAL_TYPES = ["Breakfast", "Lunch", "Dinner", "Snack"];
const COOKING_METHODS = ["Stovetop", "Oven", "Air fryer", "Grill", "Instant Pot", "Raw/No-cook", "Slow cooking", "Microwave", "Steaming", "Pressure cooking"];
const COMPLEXITY_OPTIONS = [
  { value: 'novice', label: 'Novice', desc: 'Very simple, few ingredients' },
  { value: 'basic', label: 'Basic', desc: 'Simple recipes, 30 min' },
  { value: 'intermediate', label: 'Intermediate', desc: 'Multi-step, 1h' },
  { value: 'advanced', label: 'Advanced', desc: 'Complex techniques' },
];
const COOKING_FREQ = ["Daily", "5-6 times/week", "3-4 times/week", "1-2 times/week", "Weekends only"];
const SHOPPING_FREQ = ["Daily", "2-3 times/week", "Weekly", "Bi-weekly", "Monthly"];

export const ProfileSettings: React.FC<ProfileSettingsProps> = ({ isOpen, onClose }) => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [activeTab, setActiveTab] = useState<'physical' | 'dietary' | 'preferences'>('physical');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      getUserProfile()
        .then(setProfile)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  const handleSave = async () => {
    if (!profile) return;
    setLoading(true);
    try {
      await updateUserProfile(profile);
      onClose();
    } catch (e) {
      console.error('Failed to save profile', e);
    } finally {
      setLoading(false);
    }
  };

  const updateSection = (section: keyof UserProfile, key: string, value: any) => {
    if (!profile) return;
    setProfile({ ...profile, [section]: { ...(profile[section] as any), [key]: value } });
  };

  const toggleArrayItem = (section: keyof UserProfile, key: string, item: string) => {
    if (!profile) return;
    const current = ((profile[section] as any)?.[key] as string[]) || [];
    updateSection(section, key, current.includes(item) ? current.filter(i => i !== item) : [...current, item]);
  };

  if (!isOpen) return null;
  if (loading && !profile) return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center">
      <div className="text-white">Loading profile...</div>
    </div>
  );
  if (!profile) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-white/10 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl">

        <div className="p-6 border-b border-white/10 flex justify-between items-center">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="text-blue-400">👤</span> My Profile
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors text-xl">✕</button>
        </div>

        <div className="flex border-b border-white/10 px-6 pt-4 gap-6">
          {(['physical', 'dietary', 'preferences'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-4 text-sm font-medium transition-colors border-b-2 ${activeTab === tab ? 'border-blue-500 text-white' : 'border-transparent text-gray-500 hover:text-gray-300'}`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {activeTab === 'physical' && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'Age', key: 'age', type: 'number' },
                  { label: 'Weight (kg)', key: 'weight', type: 'number' },
                  { label: 'Height (cm)', key: 'height', type: 'number' },
                ].map(({ label, key, type }) => (
                  <div key={key}>
                    <label className="block text-xs font-medium text-gray-400 mb-1">{label}</label>
                    <input
                      type={type}
                      className="w-full bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-blue-500 outline-none"
                      value={(profile.physical as any)?.[key] || ''}
                      onChange={(e) => updateSection('physical', key, e.target.value ? parseInt(e.target.value) : undefined)}
                    />
                  </div>
                ))}
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Gender</label>
                  <select
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-blue-500 outline-none"
                    value={profile.physical?.gender || ''}
                    onChange={(e) => updateSection('physical', 'gender', e.target.value)}
                  >
                    <option value="">Select...</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
              <div className="pt-4 border-t border-white/10">
                <label className="block text-sm font-medium text-white mb-3">Monthly Budget (RON)</label>
                <div className="flex gap-4 items-center">
                  <input type="number" placeholder="Min" className="w-1/3 bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white outline-none"
                    value={profile.finance?.monthly_budget?.min || ''}
                    onChange={(e) => updateSection('finance', 'monthly_budget', { ...(profile.finance?.monthly_budget || { currency: 'RON', max: 0 }), min: parseInt(e.target.value) || 0 })} />
                  <span className="text-gray-500">–</span>
                  <input type="number" placeholder="Max" className="w-1/3 bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white outline-none"
                    value={profile.finance?.monthly_budget?.max || ''}
                    onChange={(e) => updateSection('finance', 'monthly_budget', { ...(profile.finance?.monthly_budget || { currency: 'RON', min: 0 }), max: parseInt(e.target.value) || 0 })} />
                  <span className="text-gray-400 text-sm">RON/month</span>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'dietary' && (
            <div className="space-y-6">
              {[
                { label: 'Primary Diet', key: 'primary_diet', options: DIET_OPTIONS, color: 'bg-blue-600 text-white', activeClass: 'bg-blue-600 text-white' },
                { label: 'Allergies & Intolerances', key: 'allergies', options: ALLERGY_OPTIONS, activeClass: 'bg-red-500/20 text-red-200 border border-red-500/30' },
                { label: 'Food Exclusions', key: 'exclusions', options: EXCLUSION_OPTIONS, activeClass: 'bg-orange-500/20 text-orange-200 border border-orange-500/30' },
                { label: 'Goals', key: 'nutritional_goals', options: GOAL_OPTIONS, activeClass: 'bg-emerald-500/20 text-emerald-200 border border-emerald-500/30' },
              ].map(({ label, key, options, activeClass }) => (
                <div key={key}>
                  <label className="block text-sm font-medium text-white mb-2">{label}</label>
                  <div className="flex flex-wrap gap-2">
                    {options.map(opt => (
                      <button key={opt} onClick={() => toggleArrayItem('dietary', key, opt)}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${(profile.dietary as any)?.[key]?.includes(opt) ? activeClass : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">Calorie Target (kcal/day)</label>
                <input type="number" className="w-1/3 bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-blue-500 outline-none"
                  value={profile.dietary?.calorie_target || ''}
                  onChange={(e) => updateSection('dietary', 'calorie_target', e.target.value ? parseInt(e.target.value) : undefined)} />
              </div>
            </div>
          )}

          {activeTab === 'preferences' && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-white mb-2">Meals to Plan</label>
                <div className="flex flex-wrap gap-2">
                  {MEAL_TYPES.map(t => (
                    <button key={t} onClick={() => toggleArrayItem('preferences', 'meal_types', t)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${profile.preferences?.meal_types?.includes(t) ? 'bg-purple-600 text-white' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-white mb-2">Cooking Methods</label>
                <div className="flex flex-wrap gap-2">
                  {COOKING_METHODS.map(m => (
                    <button key={m} onClick={() => toggleArrayItem('preferences', 'cooking_methods', m)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${profile.preferences?.cooking_methods?.includes(m) ? 'bg-amber-600 text-white' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
                      {m}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-white mb-2">Meal Complexity</label>
                <div className="grid grid-cols-2 gap-2">
                  {COMPLEXITY_OPTIONS.map(opt => (
                    <button key={opt.value} onClick={() => updateSection('preferences', 'complexity', opt.value)}
                      className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left ${profile.preferences?.complexity === opt.value ? 'bg-indigo-600 text-white' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
                      <span className="block font-semibold">{opt.label}</span>
                      <span className="block text-[10px] opacity-70">{opt.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Adults</label>
                  <input type="number" className="w-full bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white outline-none"
                    value={profile.preferences?.family_members?.adults || 1}
                    onChange={(e) => updateSection('preferences', 'family_members', { ...profile.preferences?.family_members, adults: parseInt(e.target.value) || 1 })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Children</label>
                  <input type="number" className="w-full bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white outline-none"
                    value={profile.preferences?.family_members?.children || 0}
                    onChange={(e) => updateSection('preferences', 'family_members', { ...profile.preferences?.family_members, children: parseInt(e.target.value) || 0 })} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'Cooking Frequency', key: 'cooking_frequency', options: COOKING_FREQ },
                  { label: 'Shopping Frequency', key: 'shopping_frequency', options: SHOPPING_FREQ },
                ].map(({ label, key, options }) => (
                  <div key={key}>
                    <label className="block text-sm font-medium text-white mb-2">{label}</label>
                    <select className="w-full bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 outline-none"
                      value={(profile.preferences as any)?.[key] || ''}
                      onChange={(e) => updateSection('preferences', key, e.target.value)}>
                      <option value="">Select...</option>
                      {options.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  </div>
                ))}
              </div>

              <div className="pt-4 border-t border-white/10">
                <label className="block text-sm font-medium text-white mb-3">Favorite Foods</label>
                {(['breakfast', 'lunch', 'dinner'] as const).map(meal => (
                  <div key={meal} className="mb-3">
                    <label className="block text-xs font-medium text-gray-400 mb-1 capitalize">{meal}</label>
                    <input
                      type="text"
                      placeholder={`e.g. omleta, toast (comma separated)`}
                      className="w-full bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 outline-none placeholder-gray-600"
                      value={(profile.preferences?.favorite_foods?.[meal] || []).join(', ')}
                      onChange={(e) => {
                        const items = e.target.value.split(',').map(s => s.trim()).filter(Boolean);
                        const current = profile.preferences?.favorite_foods || {};
                        updateSection('preferences', 'favorite_foods', { ...current, [meal]: items });
                      }}
                    />
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between py-3 border-t border-white/10">
                <div>
                  <label className="block text-sm font-medium text-white">Use Leftovers</label>
                  <span className="text-[10px] text-gray-500">Reduce waste by reusing leftovers in next meals</span>
                </div>
                <button onClick={() => updateSection('preferences', 'leftovers', !profile.preferences?.leftovers)}
                  className={`w-12 h-6 rounded-full transition-colors relative ${profile.preferences?.leftovers ? 'bg-emerald-500' : 'bg-white/10'}`}>
                  <div className={`w-5 h-5 rounded-full bg-white shadow-sm absolute top-0.5 transition-transform ${profile.preferences?.leftovers ? 'translate-x-6' : 'translate-x-0.5'}`} />
                </button>
              </div>

              <div>
                <label className="block text-sm font-medium text-white mb-2">Variety per Week</label>
                <div className="flex gap-2">
                  {(['low', 'medium', 'high'] as const).map(level => (
                    <button key={level} onClick={() => updateSection('preferences', 'variety_per_week', level)}
                      className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${profile.preferences?.variety_per_week === level ? 'bg-cyan-600 text-white' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
                      {level === 'low' ? 'Low (repeat)' : level === 'medium' ? 'Medium' : 'High (new daily)'}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="p-6 border-t border-white/10 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-colors">Cancel</button>
          <button onClick={handleSave} disabled={loading}
            className="px-6 py-2 rounded-lg text-sm font-bold bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/20 transition-all disabled:opacity-50">
            {loading ? 'Saving...' : 'Save Profile'}
          </button>
        </div>
      </div>
    </div>
  );
};
