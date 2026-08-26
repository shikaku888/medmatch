import React, { useState } from 'react';
import { 
  Sparkles, 
  ShieldCheck, 
  Check, 
  X, 
  Users, 
  FileText, 
  Zap, 
  HeartHandshake, 
  Award,
  Lock,
  ArrowRight
} from 'lucide-react';

interface ProUpgradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpgradeSuccess: () => void;
  isProUser: boolean;
}

export const ProUpgradeModal: React.FC<ProUpgradeModalProps> = ({
  isOpen,
  onClose,
  onUpgradeSuccess,
  isProUser
}) => {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('yearly');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubscribe = () => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      onUpgradeSuccess();
      onClose();
    }, 800);
  };

  const proFeatures = [
    {
      title: 'AI Smart Safe Swaps Engine',
      desc: 'Instant 90+ compatibility score alternative recommendations avoiding all your exact allergens.',
      icon: Sparkles
    },
    {
      title: 'Ask Clinical Dietitian',
      desc: 'Interactive AI consultation to evaluate toxicological risk, child safety, and preparation tips.',
      icon: Zap
    },
    {
      title: 'Household & Family Protection Network',
      desc: 'Unlimited family profiles to safeguard children with severe allergies, pregnant partners, and seniors.',
      icon: Users
    },
    {
      title: 'Toxic Additive & Endocrine Disruptor Radar',
      desc: 'Deep clean chemistry screen for banned EU additives, synthetic dyes, titanium dioxide, and parabens.',
      icon: ShieldCheck
    },
    {
      title: 'Printable Clinical Dietitian & Doctor Reports',
      desc: 'One-click clinical summaries of all scanned foods and allergen intercepts ready for pediatricians.',
      icon: FileText
    }
  ];

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-xl w-full overflow-hidden text-slate-900 animate-in fade-in zoom-in-95 duration-200">
        
        {/* Banner */}
        <div className="p-8 bg-gradient-to-br from-slate-950 via-blue-950 to-indigo-950 text-white relative overflow-hidden">
          <div className="flex items-start justify-between relative z-10">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-amber-400/20 border border-amber-300/40 text-amber-300 text-xs font-bold">
              <Sparkles className="w-3.5 h-3.5" />
              <span>MEDMATCH AI PRO MEMBERSHIP</span>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <h2 className="text-2xl sm:text-3xl font-black text-white mt-3 tracking-tight">
            Elevate Your Family's Biological Safety
          </h2>
          <p className="text-sm text-slate-300 mt-2 max-w-md">
            Unlock advanced toxicological screening, AI-powered smart swaps, and comprehensive family health monitoring.
          </p>

          {/* Pricing Toggle */}
          <div className="mt-6 inline-flex p-1 rounded-xl bg-slate-900/80 border border-slate-800 backdrop-blur-xs">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                billingCycle === 'monthly'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Monthly ($7.99/mo)
            </button>
            <button
              onClick={() => setBillingCycle('yearly')}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 ${
                billingCycle === 'yearly'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>Annual ($4.99/mo)</span>
              <span className="px-1.5 py-0.2 rounded-full bg-emerald-500 text-white text-[9px] font-extrabold uppercase">
                Save 37%
              </span>
            </button>
          </div>
        </div>

        {/* Features Checklist */}
        <div className="p-6 space-y-4">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Included in SuitSafe Pro Tier:
          </h4>

          <div className="space-y-3">
            {proFeatures.map((feat, idx) => {
              const Icon = feat.icon;
              return (
                <div key={idx} className="flex items-start space-x-3 text-xs">
                  <div className="p-1.5 rounded-lg bg-blue-50 text-blue-700 border border-blue-200 shrink-0 mt-0.5">
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <h5 className="font-bold text-slate-900">{feat.title}</h5>
                    <p className="text-slate-600 leading-normal mt-0.5">{feat.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pricing and CTA */}
          <div className="mt-6 pt-4 border-t border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <span className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                {billingCycle === 'yearly' ? 'Billed annually at $59.99/yr' : 'Billed monthly at $7.99/mo'}
              </span>
              <span className="text-2xl font-black text-slate-900">
                {billingCycle === 'yearly' ? '$4.99' : '$7.99'}
                <span className="text-xs text-slate-500 font-normal"> / month</span>
              </span>
            </div>

            <button
              onClick={handleSubscribe}
              disabled={loading}
              className="px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-all shadow-md flex items-center justify-center space-x-2 shrink-0"
            >
              {loading ? (
                <span>Activating Pro Access...</span>
              ) : isProUser ? (
                <span>Manage Subscription</span>
              ) : (
                <>
                  <span>Start 7-Day Free Trial</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>

          <p className="text-[10px] text-center text-slate-400">
            Cancel anytime in 1-click. 100% money-back guarantee within 30 days.
          </p>
        </div>
      </div>
    </div>
  );
};
