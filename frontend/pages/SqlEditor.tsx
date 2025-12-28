
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AceEditor from '../components/AceEditor';
import Modal from '../components/Modal';
import { authenticatedFetch } from '../services/api';
import { DatabaseInfo, Workspace, QueryResult } from '../types';
import * as XLSX from 'xlsx';

const SqlEditor: React.FC = () => {
  const { workspaceId } = useParams();
  const navigate = useNavigate();

  const [query, setQuery] = useState('-- WebQuery SQL Studio\nSELECT * FROM table_name LIMIT 10;');
  const [servers, setServers] = useState<DatabaseInfo>({});
  const [selectedServer, setSelectedServer] = useState('');
  const [selectedDatabase, setSelectedDatabase] = useState('');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(null);

  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveDesc, setSaveDesc] = useState('');

  const [wsOpen, setWsOpen] = useState(false);
  const [srvOpen, setSrvOpen] = useState(false);
  const [dbOpen, setDbOpen] = useState(false);

  useEffect(() => {
    fetchServers();
    fetchWorkspaces();
    if (workspaceId) {
      loadWorkspace(parseInt(workspaceId));
    }
  }, [workspaceId]);

  useEffect(() => {
    if (selectedServer && servers[selectedServer]) {
      const dbs = servers[selectedServer].databases;
      if (dbs.length > 0 && (!selectedDatabase || !dbs.includes(selectedDatabase))) {
        setSelectedDatabase(dbs[0]);
      }
    } else {
      setSelectedDatabase('');
    }
  }, [selectedServer, servers]);

  const fetchServers = async () => {
    try {
      const res = await authenticatedFetch('/api/database_information');
      if (res?.ok) {
        const data = await res.json();
        if (data.db_info) {
          setServers(data.db_info);
          const firstSrv = Object.keys(data.db_info)[0];
          if (firstSrv && !selectedServer) setSelectedServer(firstSrv);
        }
      }
    } catch (e) {
      console.error("Failed to fetch server info:", e);
    }
  };

  const fetchWorkspaces = async () => {
    try {
      const res = await authenticatedFetch('/api/workspaces');
      if (res?.ok) {
        const data = await res.json();
        setWorkspaces(data.workspaces || []);
      }
    } catch (e) {
      console.error("Failed to fetch workspaces:", e);
    }
  };

  const loadWorkspace = async (id: number) => {
    setLoading(true);
    try {
      const res = await authenticatedFetch(`/api/get_workspace_by_id/${id}`);
      if (res?.ok) {
        const data = await res.json();
        setCurrentWorkspace(data);
        setQuery(data.query);
        setSelectedServer(data.servername);
        setSelectedDatabase(data.database_name);
      }
    } catch (e) {
      console.error("Failed to load workspace:", e);
    }
    setLoading(false);
  };

  const executeQuery = async () => {
    if (!selectedServer || !selectedDatabase) {
      alert("Please select a server and database.");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await authenticatedFetch('/api/execute_query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, servername: selectedServer, database_name: selectedDatabase })
      });
      if (res) {
        const data = await res.json();
        if (res.ok) {
          setResult(data);
        } else {
          setResult({ error: data.error || data.detail || 'Execution failed' });
        }
      }
    } catch (e: any) {
      setResult({ error: "Failed to connect to the execution server." });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveWorkspace = async () => {
    if (!saveName) return;
    setLoading(true);
    try {
      const res = await authenticatedFetch('/api/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: saveName,
          description: saveDesc,
          query: query,
          servername: selectedServer,
          database_name: selectedDatabase
        })
      });
      if (res?.ok) {
        const newItem = await res.json();
        setShowSaveModal(false);
        fetchWorkspaces();
        if (newItem.id) navigate(`/editor/${newItem.id}`);
      }
    } catch (e) {
      console.error("Save failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateWorkspace = async () => {
    if (!currentWorkspace) return;
    setLoading(true);
    try {
      const res = await authenticatedFetch(`/api/workspaces/${currentWorkspace.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: currentWorkspace.name,
          description: currentWorkspace.description,
          query: query,
          servername: selectedServer,
          database_name: selectedDatabase
        })
      });
      if (res?.ok) {
        alert('Workspace updated successfully.');
        fetchWorkspaces();
      }
    } catch (e) {
      console.error("Update failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const getTechColor = (tech?: string) => {
    if (!tech) return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    switch (tech.toLowerCase()) {
      case 'mssql': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'postgres': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'oracle': return 'bg-red-500/20 text-red-400 border-red-500/30';
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-100px)] gap-4 animate-in slide-in-from-bottom-4 duration-500">
      {/* Header with Custom Dropdowns */}
      <div className="bg-gray-900 p-4 rounded-xl shadow-2xl border border-gray-800 flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap gap-2 flex-1">
          {/* Workspace Switcher */}
          <div className="relative">
            <label className="block text-[10px] text-gray-500 font-bold uppercase mb-1 ml-1">Workspace</label>
            <button
              onClick={() => setWsOpen(!wsOpen)}
              className="flex items-center justify-between bg-gray-850 border border-gray-700 hover:border-indigo-500 rounded-lg px-4 py-2 text-sm w-[220px] transition-all text-white shadow-inner"
            >
              <span className="truncate">{currentWorkspace?.name || 'New Workspace'}</span>
              <svg className={`w-4 h-4 transition-transform ${wsOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
            </button>
            {wsOpen && (
              <div className="absolute top-full left-0 mt-2 w-64 bg-gray-850 border border-gray-700 rounded-xl shadow-2xl z-[150] overflow-hidden py-1">
                <button onClick={() => { setCurrentWorkspace(null); setQuery(''); setWsOpen(false); navigate('/editor'); }} className="w-full text-left px-4 py-2 text-xs text-indigo-400 hover:bg-indigo-500/10 font-bold border-b border-gray-700">+ CREATE NEW</button>
                {workspaces.length === 0 ? (
                  <div className="px-4 py-3 text-xs text-gray-600">No workspaces found</div>
                ) : (
                  workspaces.map(w => (
                    <button key={w.id} onClick={() => { loadWorkspace(w.id); setWsOpen(false); navigate(`/editor/${w.id}`); }} className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-800 flex flex-col gap-0.5 ${currentWorkspace?.id === w.id ? 'bg-indigo-500/10 border-l-2 border-indigo-500' : ''}`}>
                      <span className="font-medium text-gray-100">{w.name}</span>
                      <span className="text-[10px] text-gray-500 italic truncate">{w.description}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Server Selector */}
          <div className="relative">
            <label className="block text-[10px] text-gray-500 font-bold uppercase mb-1 ml-1">Server</label>
            <button
              onClick={() => setSrvOpen(!srvOpen)}
              className="flex items-center justify-between bg-gray-850 border border-gray-700 hover:border-indigo-500 rounded-lg px-4 py-2 text-sm w-[240px] transition-all text-white shadow-inner"
            >
              <div className="flex items-center gap-2 truncate">
                <span className={`w-1.5 h-1.5 rounded-full ${selectedServer ? 'bg-indigo-500' : 'bg-gray-600'}`}></span>
                {selectedServer || 'Select Server'}
              </div>
              <svg className={`w-4 h-4 transition-transform ${srvOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
            </button>
            {srvOpen && (
              <div className="absolute top-full left-0 mt-2 w-[280px] bg-gray-850 border border-gray-700 rounded-xl shadow-2xl z-[150] overflow-hidden py-1">
                {Object.keys(servers).length === 0 ? (
                  <div className="px-4 py-3 text-xs text-gray-600">No servers available</div>
                ) : (
                  Object.keys(servers).map(s => (
                    <button key={s} onClick={() => { setSelectedServer(s); setSrvOpen(false); }} className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-800 flex items-center justify-between ${selectedServer === s ? 'bg-indigo-500/10 border-l-2 border-indigo-500' : ''}`}>
                      <span className="font-medium text-gray-100">{s}</span>
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${getTechColor(servers[s].technology)}`}>{servers[s].technology || 'Unknown'}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Database Selector */}
          <div className="relative">
            <label className="block text-[10px] text-gray-500 font-bold uppercase mb-1 ml-1">Database</label>
            <button
              onClick={() => setDbOpen(!dbOpen)}
              disabled={!selectedServer}
              className={`flex items-center justify-between bg-gray-850 border border-gray-700 hover:border-indigo-500 rounded-lg px-4 py-2 text-sm w-[200px] transition-all text-white shadow-inner ${!selectedServer ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <span className="truncate">{selectedDatabase || 'Select DB'}</span>
              <svg className={`w-4 h-4 transition-transform ${dbOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
            </button>
            {dbOpen && (
              <div className="absolute top-full left-0 mt-2 w-56 bg-gray-850 border border-gray-700 rounded-xl shadow-2xl z-[150] max-h-64 overflow-y-auto py-1">
                {selectedServer && servers[selectedServer]?.databases.length > 0 ? (
                  servers[selectedServer].databases.map(db => (
                    <button key={db} onClick={() => { setSelectedDatabase(db); setDbOpen(false); }} className={`w-full text-left px-4 py-2.5 text-sm hover:bg-gray-800 text-gray-300 ${selectedDatabase === db ? 'bg-indigo-500/10 text-white font-bold' : ''}`}>
                      {db}
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-xs text-gray-600">No databases found</div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => currentWorkspace ? handleUpdateWorkspace() : setShowSaveModal(true)}
            disabled={loading}
            className="bg-emerald-600/10 hover:bg-emerald-600 text-emerald-400 hover:text-white px-5 py-2 rounded-lg border border-emerald-600/30 transition shadow-lg text-sm font-bold disabled:opacity-50"
          >
            {loading ? '...' : (currentWorkspace ? 'UPDATE' : 'SAVE')}
          </button>
          <button onClick={executeQuery} disabled={loading} className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-2 rounded-lg text-sm font-black shadow-xl transition-all flex items-center gap-2 tracking-widest active:scale-95 disabled:opacity-50">
            {loading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> : 'RUN'}
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* Editor Area */}
        <div className="flex-1 bg-gray-900 rounded-xl border border-gray-800 p-2 flex flex-col shadow-2xl overflow-hidden">
          <div className="flex justify-between items-center mb-2 px-2">
            <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest flex items-center gap-2">
              <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse"></span> Query Studio
            </div>
            <button onClick={() => setQuery('')} className="text-[10px] text-red-500/50 hover:text-red-500 transition">CLEAR ALL</button>
          </div>
          <div className="flex-1 rounded-lg overflow-hidden bg-gray-950">
            <AceEditor value={query} onChange={setQuery} height="100%" />
          </div>
        </div>

        {/* Results Area */}
        <div className="flex-1 bg-gray-900 rounded-xl border border-gray-800 p-2 flex flex-col min-w-0 shadow-2xl overflow-hidden">
          <div className="flex justify-between items-center mb-2 px-2">
            <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Live Execution Result</div>
            {result?.data && result.data.length > 0 && (
              <button onClick={() => {
                const ws = XLSX.utils.json_to_sheet(result.data!);
                const wb = XLSX.utils.book_new();
                XLSX.utils.book_append_sheet(wb, ws, 'Results');
                XLSX.writeFile(wb, 'query_export.xlsx');
              }} className="text-[10px] text-emerald-400 hover:text-emerald-300 font-bold flex items-center gap-1">
                EXPORT EXCEL
              </button>
            )}
          </div>

          <div className="flex-1 bg-gray-950 rounded-lg border border-gray-800 overflow-auto relative custom-scrollbar">
            {loading && (
              <div className="absolute inset-0 bg-gray-950/80 backdrop-blur-sm flex items-center justify-center z-20">
                <div className="flex flex-col items-center gap-3">
                  <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-sm font-bold text-indigo-400 tracking-tighter uppercase">Remote Execution in Progress...</span>
                </div>
              </div>
            )}

            {result?.error && (
              <div className="p-4 bg-red-950/20 text-red-400 border border-red-500/20 m-4 rounded-lg font-mono text-xs shadow-lg">
                <div className="font-black mb-1 opacity-50 underline uppercase">Query Exception:</div>
                {result.error}
              </div>
            )}

            {result?.message && !result.error && (
              <div className="p-4 text-emerald-400 text-center font-bold text-sm bg-emerald-950/10 rounded m-4 border border-emerald-500/10">
                {result.message}
              </div>
            )}

            {result?.data && result.data.length > 0 ? (
              <table className="w-full text-left border-separate border-spacing-0 text-xs">
                <thead className="bg-gray-900 sticky top-0 z-10">
                  <tr>
                    {Object.keys(result.data[0]).map(k => (
                      <th key={k} className="p-3 border-b border-gray-800 font-black text-gray-500 uppercase tracking-tighter bg-gray-900">{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/30">
                  {result.data.map((row, i) => (
                    <tr key={i} className="hover:bg-indigo-500/5 group transition-colors">
                      {Object.values(row).map((v: any, j) => (
                        <td key={j} className="p-3 text-gray-400 group-hover:text-gray-100 whitespace-nowrap font-medium">
                          {v === null ? <span className="text-gray-700 italic opacity-50">NULL</span> : String(v)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : !loading && !result?.error && !result?.message && (
              <div className="h-full flex flex-col items-center justify-center text-gray-800 gap-4">
                <svg className="w-20 h-20 opacity-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path></svg>
                <p className="text-xs font-bold opacity-30 tracking-[0.2em] uppercase">Ready for Execution</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <Modal isOpen={showSaveModal} onClose={() => setShowSaveModal(false)} title="New Workspace Configuration">
        <div className="space-y-4">
          <div>
            <label className="block text-[10px] text-gray-500 font-black uppercase mb-1 ml-1 tracking-widest">Workspace Name</label>
            <input value={saveName} onChange={e => setSaveName(e.target.value)} placeholder="e.g. Sales Report Q1" className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-white outline-none focus:ring-1 focus:ring-indigo-500 text-sm font-medium" />
          </div>
          <div>
            <label className="block text-[10px] text-gray-500 font-black uppercase mb-1 ml-1 tracking-widest">Description</label>
            <textarea value={saveDesc} onChange={e => setSaveDesc(e.target.value)} placeholder="Briefly describe the purpose of this query." className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-white h-24 outline-none focus:ring-1 focus:ring-indigo-500 resize-none text-sm" />
          </div>
          <div className="bg-indigo-500/5 p-4 rounded-lg border border-indigo-500/20 text-xs text-indigo-300">
            New workspaces are saved and accessible from the explorer dashboard.
          </div>
          <button
            onClick={handleSaveWorkspace}
            disabled={!saveName || loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white p-3 rounded-lg font-black shadow-xl transition-all disabled:opacity-30 tracking-widest"
          >
            {loading ? 'SAVING...' : 'SAVE WORKSPACE'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default SqlEditor;
