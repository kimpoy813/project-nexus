import { useState } from 'react';
import './App.css';

/* Mock proposal data for demonstration */
const mockProposals = [
  { id: 1, title: 'Community-Based Extension Program — Campus A', type: 'PROGRAM', status: 'Submitted', scope: 'Program', campus: 'Campus A', created: 'Mar 15, 2026', progress: 35 },
  { id: 2, title: 'Technology Transfer Initiative — Campus B', type: 'PROJECT', status: 'Under Review', scope: 'Project', campus: 'Campus B', created: 'Feb 28, 2026', progress: 55 },
  { id: 3, title: 'Collaborative Research Agreement — Campus C', type: 'RESEARCH', status: 'MOA Draft', scope: 'Research', campus: 'Campus C', created: 'Jan 10, 2026', progress: 20 },
  { id: 4, title: 'Adult Education Outreach — Campus D', type: 'ACTIVITY', status: 'Draft', scope: 'Activity', campus: 'Campus D', created: 'Jun 05, 2026', progress: 5 },
  { id: 5, title: 'Environmental Protection Drive — Campus E', type: 'PROGRAM', status: 'Approved', scope: 'Program', campus: 'Campus E', created: 'Apr 22, 2026', progress: 100 },
];

function ProposalCard({ proposal }) {
  return (
    <div className="neo-card group">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-bold text-slate-800 leading-snug line-clamp-2 group-hover:text-emerald-700 transition-colors">
            {proposal.title}
          </h3>
          <p className="text-[11px] text-slate-500 mt-1">{proposal.scope} · {proposal.campus}</p>
        </div>
        <span className={`text-[10px] font-extrabold uppercase tracking-wide px-2.5 py-1 rounded-md whitespace-nowrap shadow-sm ${
          proposal.status === 'Draft' ? 'text-amber-700 bg-amber-100' :
          proposal.status === 'Submitted' ? 'text-emerald-700 bg-emerald-100' :
          proposal.status === 'Under Review' ? 'text-blue-700 bg-blue-100' :
          proposal.status === 'MOA Draft' ? 'text-rose-700 bg-rose-100' :
          'text-violet-700 bg-violet-100'
        }`}>
          {proposal.status}
        </span>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="w-16 h-16 relative shrink-0">
          <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
            <circle cx="50" cy="50" r="40" fill="none" stroke="#dde2e3" strokeWidth="10" />
            <circle cx="50" cy="50" r="40" fill="none" stroke={
              proposal.status === 'Draft' ? '#b45309' :
              proposal.status === 'Submitted' ? '#047857' :
              proposal.status === 'Under Review' ? '#1d4ed8' :
              proposal.status === 'MOA Draft' ? '#9f1239' :
              '#7c3aed'
            } strokeWidth="10"
              strokeDasharray={`${(2 * Math.PI * 40) * proposal.progress / 100}, ${(2 * Math.PI * 40)}`}
              strokeLinecap="round"
              style={{ transition: 'stroke-dasharray 1s ease' }} />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-xs font-black text-slate-700">{proposal.progress}%</span>
        </div>
        <div className="min-w-0 flex-1 space-y-0.5">
          <p className="text-xs text-slate-500">Created: <span className="font-semibold text-slate-700">{proposal.created}</span></p>
          <p className="text-xs text-slate-500">Type: <span className="font-semibold text-slate-700">{proposal.type}</span></p>
          <p className="text-xs text-slate-500">Scope: <span className="font-semibold text-slate-700">{proposal.scope}</span></p>
        </div>
      </div>

      <a href="#" className="neo-btn w-full text-center text-sm" aria-label={`View ${proposal.title}`}>
        View Details
      </a>
    </div>
  );
}

function ProposalTable({ proposals }) {
  return (
    <div className="overflow-x-auto rounded-2xl shadow-xl">
      <table className="neo-table min-w-full">
        <thead>
          <tr>
            <th>Title</th>
            <th>Type</th>
            <th>Scope</th>
            <th>Campus</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Created</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {proposals.map((p) => (
            <tr key={p.id}>
              <td>
                <a href="#" className="font-bold text-emerald-700 hover:underline">{p.title}</a>
              </td>
              <td><span className="text-xs font-semibold text-slate-500">{p.type}</span></td>
              <td><span className="text-xs text-slate-600">{p.scope}</span></td>
              <td><span className="text-xs text-slate-600">{p.campus}</span></td>
              <td>
                <span className={`text-[10px] font-extrabold uppercase tracking-wide px-2.5 py-1 rounded-md whitespace-nowrap ${
                  p.status === 'Draft' ? 'text-amber-700 bg-amber-100' :
                  p.status === 'Submitted' ? 'text-emerald-700 bg-emerald-100' :
                  p.status === 'Under Review' ? 'text-blue-700 bg-blue-100' :
                  p.status === 'MOA Draft' ? 'text-rose-700 bg-rose-100' :
                  'text-violet-700 bg-violet-100'
                }`}>
                  {p.status}
                </span>
              </td>
              <td>
                <div className="w-16 bg-slate-200 rounded-full h-1.5 overflow-hidden">
                  <div className={`h-1.5 rounded-full ${
                    p.status === 'Draft' ? 'bg-amber-500' :
                    p.status === 'Submitted' ? 'bg-emerald-600' :
                    p.status === 'Under Review' ? 'bg-blue-600' :
                    p.status === 'MOA Draft' ? 'bg-rose-600' :
                    'bg-violet-600'
                  }`} style={{ width: `${p.progress}%` }} />
                </div>
                <span className="text-[10px] font-black text-slate-600">{p.progress}%</span>
              </td>
              <td><span className="text-xs text-slate-500">{p.created}</span></td>
              <td>
                <a href="#" className="text-xs font-bold text-emerald-700 hover:underline">View →</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function App() {
  const [viewMode, setViewMode] = useState('cards');

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(135deg, #e8ecec 0%, #dde2e3 100%)' }}>
      <header className="max-w-5xl mx-auto px-6 pt-10 pb-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-800">Proposal Explorer</h1>
        <p className="text-slate-500 mt-1">Neomorphism design with cards and table toggle.</p>
      </header>

      <main className="max-w-5xl mx-auto px-6 pb-20">
        {/* Toggle Filter */}
        <div className="flex items-center justify-between mb-6">
          <div className="neo-toggle-group">
            <button
              className={viewMode === 'cards' ? 'active' : ''}
              onClick={() => setViewMode('cards')}
              aria-pressed={viewMode === 'cards'}
              aria-label="Cards view"
            >
              Cards
            </button>
            <button
              className={viewMode === 'table' ? 'active' : ''}
              onClick={() => setViewMode('table')}
              aria-pressed={viewMode === 'table'}
              aria-label="Table view"
            >
              Table
            </button>
          </div>
          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">
            Showing {mockProposals.length} proposals
          </span>
        </div>

        {/* View content */}
        {viewMode === 'cards' ? (
          <section aria-label="Proposal cards" className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {mockProposals.map(p => (
              <ProposalCard key={p.id} proposal={p} />
            ))}
          </section>
        ) : (
          <section aria-label="Proposal table">
            <ProposalTable proposals={mockProposals} />
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
