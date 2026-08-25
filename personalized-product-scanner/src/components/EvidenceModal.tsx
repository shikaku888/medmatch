import React from 'react';
import { ResearchData, PubMedCitation } from '../types';
import { BookOpen, ExternalLink, X, Award, CheckCircle2, FileText, Search } from 'lucide-react';

interface EvidenceModalProps {
  research: ResearchData | null;
  onClose: () => void;
}

export const EvidenceModal: React.FC<EvidenceModalProps> = ({ research, onClose }) => {
  if (!research) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-fade-in">
      <div 
        id="pubmed-evidence-modal"
        className="bg-white border border-slate-200 rounded-xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-xl overflow-hidden text-slate-900"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/70">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shadow-2xs">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="font-bold text-lg text-slate-900 tracking-tight">
                  NCBI PubMed Clinical Evidence
                </h3>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 uppercase tracking-wider">
                  Peer-Reviewed
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Evaluated Compound: <span className="text-slate-800 font-bold uppercase">{research.ingredient}</span>
              </p>
            </div>
          </div>
          <button
            id="close-evidence-modal-btn"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Research Metric Banner */}
          <div className="p-4 rounded-xl bg-blue-50/60 border border-blue-200 flex items-start space-x-3.5 shadow-2xs">
            <div className="p-2 rounded-lg bg-blue-100 text-blue-700 mt-0.5">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <h4 className="font-bold text-sm text-blue-950">
                Evidence-Based Scientific Grounding
              </h4>
              <p className="text-xs text-slate-700 mt-1 leading-relaxed">
                Queried National Library of Medicine (NCBI PubMed) archives for randomized trials, toxicology indices, and allergen research concerning <strong className="text-slate-900 font-semibold">{research.ingredient}</strong>.
              </p>
              <div className="mt-3 flex items-center space-x-3 text-xs">
                <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-white text-blue-800 font-semibold border border-blue-200 shadow-2xs">
                  ~{research.studyCount}+ Indexed Publications
                </span>
                <span className="text-slate-500 font-medium">Source: NCBI PubMed E-utilities API</span>
              </div>
            </div>
          </div>

          {/* Citations List */}
          <div>
            <h5 className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-3 flex items-center space-x-2">
              <FileText className="w-3.5 h-3.5 text-slate-500" />
              <span>Representative Studies & Citations</span>
            </h5>

            <div className="space-y-3">
              {research.citations.map((cite: PubMedCitation, idx: number) => (
                <div
                  key={cite.id || idx}
                  className="p-4 rounded-xl bg-white border border-slate-200 hover:border-slate-300 shadow-2xs transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1.5">
                      <h6 className="font-bold text-sm text-slate-900 leading-snug">
                        {cite.title}
                      </h6>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        {cite.journal && (
                          <span className="text-slate-700 font-semibold">{cite.journal}</span>
                        )}
                        {cite.year && (
                          <>
                            <span>•</span>
                            <span>{cite.year}</span>
                          </>
                        )}
                        {cite.id && cite.id !== 'PMC_REF' && cite.id !== 'PUBMED_SEARCH' && (
                          <>
                            <span>•</span>
                            <span className="font-mono text-blue-700 font-semibold">PMID: {cite.id}</span>
                          </>
                        )}
                      </div>
                    </div>

                    <a
                      href={cite.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold border border-blue-200 transition-colors shadow-2xs"
                    >
                      <span>Read Study</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Direct Search Outbound */}
          <div className="pt-2">
            <a
              href={`https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(research.ingredient + ' safety allergy health')}`}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors border border-slate-300 shadow-2xs"
            >
              <Search className="w-4 h-4 text-slate-500" />
              <span>Explore all PubMed publications for "{research.ingredient}"</span>
              <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
            </a>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50/70 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 text-xs font-semibold transition-colors shadow-2xs cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
