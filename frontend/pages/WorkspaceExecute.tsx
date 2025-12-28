
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { authenticatedFetch } from '../services/api';
import AceEditor from '../components/AceEditor';
import * as XLSX from 'xlsx';

const WorkspaceExecute: React.FC = () => {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Fixed: Casting window to any to access globally loaded ace library to avoid TS error
    const ace = (window as any).ace;
    if (ace) {
      ace.config.set('basePath', 'https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.12/');
    }
    const fetchWS = async () => {
       try {
         const res = await authenticatedFetch(`/api/get_workspace_by_id/${workspaceId}`);
         if (res?.ok) {
           setData(await res.json());
         } else {
           setError("Workspace could not be loaded.");
         }
       } catch (error) {
         setError("Connection error: " + (error as Error).message);
       } finally {
         setLoading(false);
       }
    };
    fetchWS();
  }, [workspaceId]);

  const execute = async () => {
    setExecuting(true);
    setError(null);
    setResults([]);
    try {
      const res = await authenticatedFetch(`/api/execute_workspace/${workspaceId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
      });
      const json = await res.json();
      if (res?.ok) {
        setResults(json.data || []);
      } else {
        setError(json.error || json.detail || "Execution failed");
      }
    } catch (e) {
      setError("Execution error: " + (e as Error).message);
    } finally {
      setExecuting(false);
    }
  };

  const downloadCSV = () => {
    if (!results || !results.length) return;
    const cols = Object.keys(results[0]);
    const lines = [cols.join(',')];
    results.forEach(r => {
      const vals = cols.map(c => {
        const v = r[c];
        if (v === null || v === undefined) return '';
        const s = String(v).replace(/"/g, '""');
        return '"' + s + '"';
      });
      lines.push(vals.join(','));
    });
    
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `workspace_${workspaceId}_results.csv`;
    link.click();
  };

  const downloadXLSX = () => {
    if (!results || !results.length) return;
    const ws = XLSX.utils.json_to_sheet(results);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Results');
    XLSX.writeFile(wb, `workspace_${workspaceId}_results.xlsx`);
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950 text-gray-400">
        <div className="flex flex-col items-center gap-4">
           <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
           <p className="animate-pulse">Loading Workspace...</p>
        </div>
      </div>
    );
  }

  if (!data && error) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950 text-red-400">
        <div className="text-center p-8 bg-gray-900 rounded-xl border border-red-900/30">
          <h2 className="text-2xl font-bold mb-2">Error</h2>
          <p>{error}</p>
          <button onClick={() => navigate('/')} className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm">Return Home</button>
        </div>
      </div>
    );
  }

  const hasResults = results.length > 0;

  return (
    <div className="flex flex-col h-[calc(100vh-80px)] overflow-hidden">
      <div className="bg-gray-850 p-4 border-b border-gray-700 flex justify-between items-center shadow-lg mb-6 rounded-xl">
         <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <span className="w-2 h-2 bg-indigo-500 rounded-full"></span>
              {data.name}
            </h1>
            <div className="flex items-center gap-2 mt-1">
               <span className="text-xs font-mono text-gray-400 bg-gray-900 px-2 py-0.5 rounded border border-gray-800">{data.servername}</span>
               <span className="text-xs text-gray-500">/</span>
               <span className="text-xs font-mono text-gray-400 bg-gray-900 px-2 py-0.5 rounded border border-gray-800">{data.database_name}</span>
            </div>
         </div>
         <div className="flex gap-2">
           <button 
             onClick={execute} 
             disabled={executing}
             className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-lg font-semibold shadow-lg disabled:opacity-50 transition-all flex items-center gap-2"
           >
             {executing ? (
               <>
                 <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                 Running...
               </>
             ) : 'Execute Query'}
           </button>
           
           <div className="flex bg-gray-800 rounded-lg p-1 border border-gray-700">
             <button 
               onClick={downloadCSV}
               disabled={!hasResults}
               title="Download CSV"
               className="p-2 text-gray-400 hover:text-white disabled:opacity-30 transition"
             >
               <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
             </button>
             <button 
               onClick={downloadXLSX}
               disabled={!hasResults}
               title="Download Excel"
               className="p-2 text-emerald-500 hover:text-emerald-400 disabled:opacity-30 transition"
             >
               <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
             </button>
           </div>
         </div>
      </div>

      <div className="flex-1 flex gap-6 min-h-0">
         <div className="w-2/5 bg-gray-850 rounded-xl border border-gray-700 p-2 flex flex-col shadow-2xl">
            <div className="flex justify-between items-center mb-2 px-2">
               <span className="text-xs text-gray-500 font-bold uppercase tracking-widest">Query Preview</span>
               <span className="text-[10px] text-indigo-400/50 uppercase">Read-Only</span>
            </div>
            <div className="flex-1 relative rounded-lg overflow-hidden border border-gray-800">
               <AceEditor value={data.query || ''} readOnly={true} height="100%" />
            </div>
         </div>
         
         <div className="flex-1 bg-gray-850 rounded-xl border border-gray-700 p-2 flex flex-col min-w-0 shadow-2xl">
            <div className="flex justify-between items-center mb-2 px-2">
               <span className="text-xs text-gray-500 font-bold uppercase tracking-widest">Execution Results</span>
               {hasResults && <span className="text-xs text-indigo-400 font-medium">{results.length} rows returned</span>}
            </div>
            <div className="flex-1 bg-gray-950 rounded-lg border border-gray-800 overflow-auto relative">
               {error && (
                 <div className="m-4 p-4 bg-red-900/20 border border-red-900/50 rounded-lg text-red-200 text-sm font-mono whitespace-pre-wrap">
                   <strong className="uppercase">Error:</strong> {error}
                 </div>
               )}

               {hasResults ? (
                 <table className="w-full text-left text-sm border-separate border-spacing-0">
                    <thead className="bg-gray-900 text-gray-300 sticky top-0 z-10 shadow-sm">
                      <tr>
                        {Object.keys(results[0]).map((k, i) => (
                          <th key={k} className={`p-3 border-b border-gray-800 font-semibold whitespace-nowrap bg-gray-900 ${i === 0 ? 'rounded-tl-lg' : ''}`}>
                            {k}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {results.map((r, i) => (
                        <tr key={i} className="hover:bg-gray-800/40 transition-colors group">
                          {Object.values(r).map((v:any, j) => (
                            <td key={j} className="p-3 border-b border-gray-900/50 text-gray-400 group-hover:text-gray-200 whitespace-nowrap">
                              {v === null ? <span className="text-gray-700 italic">NULL</span> : String(v)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                 </table>
               ) : (
                 <div className="flex flex-col items-center justify-center h-full text-gray-600 gap-4">
                   {executing ? (
                     <div className="flex flex-col items-center gap-2">
                        <div className="w-10 h-10 border-4 border-gray-800 border-t-indigo-500 rounded-full animate-spin"></div>
                        <p className="text-sm uppercase tracking-tighter">Remote Processing...</p>
                     </div>
                   ) : (
                     <>
                        <svg className="w-16 h-16 opacity-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        <p className="text-sm uppercase tracking-widest font-bold opacity-30">Press Execute to see results</p>
                     </>
                   )}
                 </div>
               )}
            </div>
         </div>
      </div>
    </div>
  );
};

export default WorkspaceExecute;
