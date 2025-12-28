
import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authenticatedFetch } from '../services/api';
import { Workspace } from '../types';

const Home: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchWorkspaces = async () => {
    setLoading(true);
    try {
      const response = await authenticatedFetch('/api/workspaces');
      if (response && response.ok) {
        const data = await response.json();
        setWorkspaces(data.workspaces || []);
      }
    } catch (e) {
      console.error("Failed to fetch workspaces:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const deleteWorkspace = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this workspace? This action cannot be undone.')) return;
    try {
      const response = await authenticatedFetch(`/api/workspaces/${id}`, { method: 'DELETE' });
      if (response && response.ok) {
        setWorkspaces(workspaces.filter(w => w.id !== id));
      }
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  const getStatusBadge = (status: Workspace['status']) => {
    const styles = {
      saved_in_workspace: 'bg-blue-900/40 text-blue-300 border-blue-800/50',
      waiting_for_approval: 'bg-yellow-900/40 text-yellow-300 border-yellow-800/50',
      approved_and_executed: 'bg-green-900/40 text-green-300 border-green-800/50',
      approved_with_results: 'bg-emerald-900/40 text-emerald-300 border-emerald-800/50',
      rejected: 'bg-red-900/40 text-red-300 border-red-800/50',
    };
    const labels = {
      saved_in_workspace: 'Saved',
      waiting_for_approval: 'Pending',
      approved_and_executed: 'Executed',
      approved_with_results: 'Executable',
      rejected: 'Rejected',
    };

    return (
      <span className={`px-2 py-0.5 text-[10px] font-black rounded border uppercase tracking-widest ${styles[status] || styles.saved_in_workspace}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="flex flex-col items-center w-full max-w-6xl mx-auto px-4 animate-in fade-in duration-700">
      {/* Hero Section */}
      <div className="flex flex-col items-center mb-16 mt-8">
        <h1 className="text-5xl font-black text-white mb-4 tracking-tighter uppercase text-center">
          Workspace <span className="text-indigo-500">Explorer</span>
        </h1>
        <p className="text-gray-500 font-medium mb-10 text-center max-w-md">Manage your SQL query environments and monitor execution approvals from a centralized dashboard.</p>

        <Link
          to="/editor"
          className="group relative w-24 h-24 flex items-center justify-center bg-gray-900 border-2 border-dashed border-gray-700 rounded-3xl text-4xl text-gray-500 hover:text-indigo-400 hover:border-indigo-500 hover:bg-gray-850 transition-all duration-500 shadow-2xl"
        >
          <div className="absolute inset-0 bg-indigo-500/5 group-hover:bg-indigo-500/10 rounded-3xl transition-colors"></div>
          <span className="relative z-10 group-hover:scale-125 transition-transform">+</span>
        </Link>
        <p className="mt-4 text-[10px] font-black text-gray-600 uppercase tracking-[0.3em]">Initialize Project</p>
      </div>

      {/* Main Table Container */}
      <div className="w-full bg-gray-900/40 rounded-3xl border border-gray-800/60 shadow-2xl overflow-hidden backdrop-blur-xl">
        <div className="px-8 py-6 border-b border-gray-800/60 bg-gray-900/60 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 bg-indigo-500 rounded-full shadow-[0_0_10px_rgba(99,102,241,0.5)]"></div>
            <h2 className="text-sm font-black text-white tracking-widest uppercase">Workspaces</h2>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-gray-950/30 text-gray-500 text-[10px] uppercase font-black tracking-[0.2em] border-b border-gray-800/40">
              <tr>
                <th className="px-8 py-4">Configuration Details</th>
                <th className="px-8 py-4">Deployment Status</th>
                <th className="px-8 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/40">
              {loading ? (
                <tr><td colSpan={3} className="px-8 py-20 text-center text-gray-600 font-bold uppercase tracking-widest text-xs animate-pulse">Syncing with server...</td></tr>
              ) : workspaces.length === 0 ? (
                <tr><td colSpan={3} className="px-8 py-20 text-center text-gray-600 font-bold uppercase tracking-widest text-xs">No active configurations found.</td></tr>
              ) : (
                workspaces.map((ws) => (
                  <tr key={ws.id} className="hover:bg-indigo-500/[0.03] transition-all group">
                    <td className="px-8 py-7">
                      <div className="flex flex-col gap-1">
                        <span className="font-black text-gray-200 group-hover:text-white transition-colors tracking-tight text-base uppercase">{ws.name}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono text-gray-600 uppercase bg-gray-950 px-1.5 py-0.5 rounded border border-gray-800">{ws.servername}</span>
                          <span className="text-[10px] text-gray-700">•</span>
                          <span className="text-xs text-gray-500 italic truncate max-w-xs">{ws.description || 'No documentation provided for this query.'}</span>
                        </div>
                      </div>
                    </td>
                    <td className="px-8 py-7">
                      {getStatusBadge(ws.status)}
                    </td>
                    <td className="px-8 py-7">
                      <div className="flex items-center justify-end gap-4">
                        {ws.status === 'approved_with_results' && ws.show_results ? (
                          <button
                            onClick={() => navigate(`/execute/${ws.id}`)}
                            className="h-10 px-6 bg-emerald-600/10 hover:bg-emerald-600 text-emerald-500 hover:text-white text-[11px] font-black rounded-xl transition-all border border-emerald-600/30 shadow-lg uppercase tracking-[0.1em] active:scale-95"
                          >
                            Execute
                          </button>
                        ) : (
                          <button
                            onClick={() => navigate(`/editor/${ws.id}`)}
                            className={`h-10 px-6 text-[11px] font-black rounded-xl transition-all border uppercase tracking-[0.1em] shadow-lg active:scale-95 ${['waiting_for_approval', 'rejected'].includes(ws.status)
                                ? 'bg-gray-800/50 border-gray-700/50 text-gray-600 cursor-not-allowed'
                                : 'bg-indigo-600/10 hover:bg-indigo-600 text-indigo-400 hover:text-white border-indigo-600/30'
                              }`}
                            disabled={['waiting_for_approval', 'rejected'].includes(ws.status)}
                          >
                            {['waiting_for_approval', 'rejected'].includes(ws.status) ? 'Locked' : 'Open'}
                          </button>
                        )}

                        <div className="w-px h-6 bg-gray-800 mx-1"></div>

                        <button
                          onClick={() => deleteWorkspace(ws.id)}
                          className="h-10 w-10 flex items-center justify-center bg-red-950/10 hover:bg-red-600 text-red-500/70 hover:text-white border border-red-900/20 hover:border-red-600 rounded-xl transition-all shadow-xl active:scale-90"
                          title="Purge Workspace"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="px-8 py-4 bg-gray-950/20 border-t border-gray-800/40 flex justify-center">
          <p className="text-[9px] font-black text-gray-700 uppercase tracking-[0.5em]">WebQuery Data Infrastructure • Secure Workspace</p>
        </div>
      </div>
    </div>
  );
};

export default Home;
