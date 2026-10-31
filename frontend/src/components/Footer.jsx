import React from 'react';
import { ShieldCheck, Phone, Mail, ExternalLink } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="bg-slate-950 text-slate-400 border-t border-slate-800 text-sm mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Col 1 */}
          <div className="md:col-span-1 space-y-3">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded bg-amber-500 flex items-center justify-center text-slate-950 font-bold">
                दृ
              </div>
              <span className="text-white font-bold text-lg tracking-tight">DRISHTI AICTE</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Integrated Multi-Bureau Grievance Monitoring & AI Semantic Correlation Platform for AICTE.
            </p>
            <div className="flex items-center space-x-1.5 text-xs text-emerald-400 font-medium">
              <ShieldCheck className="w-4 h-4" />
              <span>Immutable Audit Trail Protection</span>
            </div>
          </div>

          {/* Col 2 */}
          <div>
            <h4 className="text-white text-xs font-semibold uppercase tracking-wider mb-3">
              AICTE Bureaus & Cells
            </h4>
            <ul className="space-y-1.5 text-xs text-slate-400">
              <li>Higher Education Cell</li>
              <li>Technical Education Bureau</li>
              <li>Student Welfare & Anti-Ragging Cell</li>
              <li>Approval & Affiliation Division</li>
              <li>Governance & Administration</li>
            </ul>
          </div>

          {/* Col 3 */}
          <div>
            <h4 className="text-white text-xs font-semibold uppercase tracking-wider mb-3">
              Citizen Helplines
            </h4>
            <ul className="space-y-2 text-xs text-slate-400">
              <li className="flex items-center gap-2">
                <Phone className="w-3.5 h-3.5 text-amber-400" />
                <span>Anti-Ragging Toll Free: 1800-180-5522</span>
              </li>
              <li className="flex items-center gap-2">
                <Phone className="w-3.5 h-3.5 text-amber-400" />
                <span>AICTE Helpdesk: 011-29581000</span>
              </li>
              <li className="flex items-center gap-2">
                <Mail className="w-3.5 h-3.5 text-amber-400" />
                <span>support@drishti.aicte.gov.in</span>
              </li>
            </ul>
          </div>

          {/* Col 4 */}
          <div>
            <h4 className="text-white text-xs font-semibold uppercase tracking-wider mb-3">
              Smart India Hackathon 2026
            </h4>
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs space-y-1.5">
              <p className="text-amber-400 font-semibold">Demo Evaluation Credentials</p>
              <p className="text-[11px] text-slate-300">
                <strong>Admin:</strong> admin@drishti.test<br />
                <strong>Official:</strong> official.he@drishti.test<br />
                <strong>Student:</strong> student@drishti.test<br />
                <strong>Password:</strong> Drishti@2026
              </p>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-800 mt-8 pt-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500">
          <p>© 2026 All India Council for Technical Education (AICTE), Ministry of Education, Govt. of India.</p>
          <p className="mt-2 sm:mt-0">Designed & Developed for Smart India Hackathon 2026</p>
        </div>
      </div>
    </footer>
  );
}
