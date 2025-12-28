
import React, { useEffect, useState } from 'react';
import { authenticatedFetch } from '../services/api';
import { PendingQuery } from '../types';
import Modal from '../components/Modal';
import AceEditor from '../components/AceEditor';

const Admin: React.FC = () => {
  const [queries, setQueries] = useState<PendingQuery[]>([]);
  const [selectedQuery, setSelectedQuery] = useState<PendingQuery | null>(null);
  const [previewData, setPreviewData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fixed: Casting window to any to access globally loaded ace library to avoid TS error
    const ace = (window as any).ace;
    if (ace) {
      ace.config.set('basePath', 'https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.12/');
    }
    fetchPending();
  }, []);

  const fetchPending = async () => {
    const res = await authenticatedFetch('/api/admin/queries_to_approve');
    if (res?.ok) {
      const data = await res.json();
      setQueries(data.waiting_approvals || []);
    }
  };

  const runPreview = async () => {
    if (!selectedQuery) return;
    setLoading(true);
    try {
      const res = await authenticatedFetch(`/api/admin/execute_for_preview/${selectedQuery.workspace_id}`, { method: 'POST' });
      if (res?.ok) {
        const data = await res.json();
        setPreviewData(data.data || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (approved: boolean, executable: boolean = false) => {
    if (!selectedQuery) return;
    const url = approved 
      ? `/api/admin/approve_query/${selectedQuery.workspace_id}`
      : `/api/admin/reject_query/${selectedQuery.workspace_id}`;
    
    const body = approved ? JSON.stringify({ show_results: executable }) : undefined;
    
    const res = await authenticatedFetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body
    });

    if (res?.ok) {
      setSelectedQuery(null);
      setPreviewData([]);
      fetchPending();
    }
  };

  return (
    <div className="max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-white border-b border-gray-700 pb-4">Admin Approval Panel</h1>
      
      {queries.length === 0 ? (
         <div className="bg-gray-800 p-8 rounded-xl text-center text-gray-400">No pending queries found.</div>
      ) : (
        <div className="grid gap-4">
          {queries.map(q => (
            <div key={q.workspace_id} className="bg-gray-800 border border-gray-700 rounded-xl p-4 flex justify-between items-start">
               <div>
                  <div className="flex items-center gap-3 mb-2">
                     <span className="font-bold text-white text-lg">{q.username}</span>
                     <span className="text-xs bg-yellow-900/50 text-yellow-200 border border-yellow-700 px-2 py-0.5 rounded">{q.status}</span>
                     {q.risk_type && <span className="text-xs bg-red-900/50 text-red-200 border border-red-700 px-2 py-0.5 rounded">{q.risk_type}</span>}
                  </div>
                  <div className="text-sm text-gray-400 mb-2">
                    {q.servername} &bull; {q.database}
                  </div>
                  <div className="bg-gray-900 p-3 rounded font-mono text-sm text-gray-300 max-w-3xl overflow-hidden text-ellipsis whitespace-nowrap">
                    {q.query}
                  </div>
               </div>
               <button 
                 onClick={() => setSelectedQuery(q)}
                 className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded text-sm font-medium transition"
               >
                 Review
               </button>
            </div>
          ))}
        </div>
      )}

      {selectedQuery && (
        <Modal isOpen={true} onClose={() => setSelectedQuery(null)} title="Review Query" size="xl">
          <div className="flex flex-col gap-4">
             <div className="grid grid-cols-2 gap-4 text-sm text-gray-300 bg-gray-900 p-3 rounded">
                <div>User: <span className="text-white">{selectedQuery.username}</span></div>
                <div>Server: <span className="text-white">{selectedQuery.servername}</span></div>
                <div>Database: <span className="text-white">{selectedQuery.database}</span></div>
                <div>Risk: <span className="text-red-300">{selectedQuery.risk_type || 'None'}</span></div>
             </div>

             <div>
               <label className="text-xs text-gray-400 font-bold uppercase mb-1 block">Full Query</label>
               <AceEditor value={selectedQuery.query} readOnly={true} height="200px" />
             </div>

             <div className="border-t border-gray-700 pt-4">
                <div className="flex justify-between items-center mb-2">
                   <h4 className="text-sm font-bold uppercase text-gray-400">Result Preview</h4>
                   <button onClick={runPreview} disabled={loading} className="text-xs bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded">
                     {loading ? 'Running...' : 'Run Preview'}
                   </button>
                </div>
                <div className="bg-gray-900 rounded border border-gray-700 h-48 overflow-auto">
                   {previewData.length > 0 ? (
                     <table className="w-full text-xs text-left">
                       <thead className="bg-gray-800 text-gray-300 sticky top-0">
                         <tr>{Object.keys(previewData[0]).map(k => <th key={k} className="p-2">{k}</th>)}</tr>
                       </thead>
                       <tbody>
                         {previewData.map((r, i) => (
                           <tr key={i} className="border-b border-gray-800 text-gray-400">
                              {Object.values(r).map((v:any, j) => <td key={j} className="p-2 whitespace-nowrap">{String(v)}</td>)}
                           </tr>
                         ))}
                       </tbody>
                     </table>
                   ) : (
                     <div className="h-full flex items-center justify-center text-gray-500 text-sm">Click 'Run Preview' to see results</div>
                   )}
                </div>
             </div>

             <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => handleDecision(false)} className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded shadow">Reject</button>
                <button onClick={() => handleDecision(true, false)} className="bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-2 rounded shadow">Approve (No Exec)</button>
                <button onClick={() => handleDecision(true, true)} className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded shadow">Approve & Executable</button>
             </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

export default Admin;
