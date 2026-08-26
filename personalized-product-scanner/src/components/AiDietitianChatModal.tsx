import React, { useState } from 'react';
import { ProductScanResult, UserProfile, SupportedLanguage } from '../types';
import { getTranslation } from '../i18n';
import { 
  Sparkles, 
  Send, 
  Bot, 
  User, 
  X, 
  MessageSquare, 
  ShieldAlert, 
  HelpCircle, 
  RefreshCw,
  Award
} from 'lucide-react';

interface AiDietitianChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  product: ProductScanResult;
  userProfile: UserProfile;
  language?: SupportedLanguage;
}

interface Message {
  role: 'user' | 'assistant';
  text: string;
  time: string;
}

export const AiDietitianChatModal: React.FC<AiDietitianChatModalProps> = ({
  isOpen,
  onClose,
  product,
  userProfile,
  language = 'en'
}) => {
  const t = (key: string, fb: string) => getTranslation(language, key, fb);
  const medAlerts = product.medMatch?.interactions || [];
  const sevRank = (s: typeof medAlerts[number]['severity']) => (s === 'major' ? 0 : s === 'moderate' ? 1 : s === 'minor' ? 2 : 3);
  const topAlert = [...medAlerts].sort((a, b) => sevRank(a.severity) - sevRank(b.severity))[0];

  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      text: t('aiGreeting', 'Hi! I\'m the supplementary AI advisor of MedMatch AI. The engine already checked "{name}" against verified databases{alerts}. I can explain what the alerts mean and what to ask your doctor, but the alerts themselves — not this chat — are the authority.')
        .replace('{name}', product.productName)
        .replace('{alerts}', medAlerts.length ? ` — ${medAlerts.length} ${t('aiAlertsOnFile', 'interaction alert(s) on file')}` : ` — ${t('aiNoAlerts', 'no interaction alerts on file')}`),
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const quickPrompts = [
    topAlert
      ? `Explain the ${topAlert.severity ?? 'evidence'} finding for ${topAlert.a.label} and ${topAlert.b.label} in plain language`
      : 'Does this product interact with my current medications?',
    'How do my medications change what I should avoid here?',
    'What does the published research (DOI) say about these alerts?',
    'What should I ask my doctor or pharmacist about this product?'
  ];

  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend || input;
    if (!query.trim() || loading) return;

    const userMsg: Message = {
      role: 'user',
      text: query,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/ai-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: query,
          product,
          profile: userProfile
        })
      });

      if (res.ok) {
        const data = await res.json();
        const aiMsg: Message = {
          role: 'assistant',
          text: data.answer,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages((prev) => [...prev, aiMsg]);
      } else {
        throw new Error('API failed');
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: 'I apologize, but I encountered an error connecting to the clinical advisory service. Please ensure your query is specific and try again.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-xl w-full h-[600px] max-h-[90vh] flex flex-col overflow-hidden text-slate-900 animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="p-4 bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 text-white flex items-center justify-between shrink-0 shadow-xs">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-blue-500/20 text-blue-300 border border-blue-400/30">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <h3 className="text-sm font-bold">{t('aiTitle', 'Ask AI Health Advisor')}</h3>
                <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-blue-500 text-white uppercase">
                  Pro AI
                </span>
              </div>
              <p className="text-[11px] text-slate-300 truncate max-w-[280px]">
                {product.productName} — MedMatch: {medAlerts.length} alert(s) on file
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Role separation: MedMatch engine is authoritative, this chat is supplementary */}
        <div className="px-4 py-2 bg-amber-50 border-b border-amber-200 flex items-start space-x-2 shrink-0">
          <ShieldAlert className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
          <p className="text-[10px] leading-snug text-amber-800 font-medium">
            {t('aiDisclaimer', 'Supplementary AI advisory (Pro) — safety verdicts come from the MedMatch engine (SUPP.AI · DDInter · DailyMed · FDA). This chat explains the alerts; it never overrides or replaces them.')}
          </p>
        </div>

        {/* Chat Messages Log */}
        <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-slate-50">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex items-start space-x-2.5 ${
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-full bg-blue-100 border border-blue-200 flex items-center justify-center text-blue-700 shrink-0 mt-0.5 font-bold text-xs">
                  AI
                </div>
              )}

              <div
                className={`p-3.5 rounded-2xl max-w-[82%] text-xs leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-tr-xs shadow-2xs font-medium'
                    : 'bg-white text-slate-800 border border-slate-200 rounded-tl-xs shadow-2xs'
                }`}
              >
                <p className="whitespace-pre-line">{msg.text}</p>
                <span
                  className={`block text-[9px] mt-1.5 text-right ${
                    msg.role === 'user' ? 'text-blue-200' : 'text-slate-400'
                  }`}
                >
                  {msg.time}
                </span>
              </div>

              {msg.role === 'user' && (
                <div className="w-7 h-7 rounded-full bg-slate-800 text-white flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold">
                  U
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex items-center space-x-2 text-xs text-slate-500 bg-white p-3 rounded-xl border border-slate-200 w-fit">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-600" />
              <span>{t('aiLoading', 'Analyzing biomedical database & formulating advice...')}</span>
            </div>
          )}
        </div>

        {/* Quick Suggestion Chips */}
        <div className="p-2.5 bg-white border-t border-slate-200 flex items-center space-x-1.5 overflow-x-auto shrink-0 scrollbar-none">
          {quickPrompts.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(q)}
              disabled={loading}
              className="px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] whitespace-nowrap font-medium transition-colors border border-slate-200"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Input Footer */}
        <div className="p-3 bg-white border-t border-slate-200 flex items-center space-x-2 shrink-0">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder={t('aiPlaceholder', 'Ask a clinical question about this product...')}
            disabled={loading}
            className="flex-1 px-3 py-2 text-xs border border-slate-300 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={loading || !input.trim()}
            className="p-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors shadow-2xs"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        <p className="px-3 py-1.5 bg-slate-100 border-t border-slate-200 text-[9px] text-slate-500 font-medium shrink-0">
          {t('aiFooter', 'AI chat is not a medical alert or diagnosis — always confirm with the interaction alerts above and a healthcare professional.')}
        </p>
      </div>
    </div>
  );
};
