import React, { useEffect, useState } from 'react';
import { authenticatedFetch } from '../services/api';
import { PendingQuery } from '../types';
import Modal from '../components/Modal';
import AceEditor from '../components/AceEditor';

interface Database {
  id: number;
  servername: string;
  database_name: string;
  technology: string;
  db_username?: string;
}

interface MaskingRule {
  table_name: string;
  column_name: string;
  masking_type: string;
  is_active: boolean;
}

const Admin: React.FC = () => {
  // Navigation & Tab state
  const [activeTab, setActiveTab] = useState<'approvals' | 'masking'>('approvals');

  // --- Query Approvals State ---
  const [queries, setQueries] = useState<PendingQuery[]>([]);
  const [selectedQuery, setSelectedQuery] = useState<PendingQuery | null>(null);
  const [previewData, setPreviewData] = useState<any[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // --- Databases & Masking State ---
  const [databases, setDatabases] = useState<Database[]>([]);
  const [selectedDb, setSelectedDb] = useState<Database | null>(null);
  const [loadingDbs, setLoadingDbs] = useState(false);
  const [savingRules, setSavingRules] = useState(false);
  const [loadingSchema, setLoadingSchema] = useState(false);

  // Add Database Form State
  const [dbForm, setDbForm] = useState({
    servername: '',
    database_name: '',
    technology: 'mssql'
  });
  const [addingDb, setAddingDb] = useState(false);
  const [generatedCreds, setGeneratedCreds] = useState<{ username: string; password: string } | null>(null);

  // Schema Discovery & Masking Rules State
  const [schema, setSchema] = useState<Record<string, string[]>>({});
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
  const [maskedColumns, setMaskedColumns] = useState<Set<string>>(new Set()); // Formatted as "table_name.column_name"

  useEffect(() => {
    // Initialize AceEditor config
    const ace = (window as any).ace;
    if (ace) {
      ace.config.set('basePath', 'https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.12/');
    }
    fetchPending();
    fetchDatabases();
  }, []);

  // Fetch pending queries for approvals
  const fetchPending = async () => {
    const res = await authenticatedFetch('/api/admin/queries_to_approve');
    if (res?.ok) {
      const data = await res.json();
      setQueries(data.waiting_approvals || []);
    }
  };

  // Fetch registered databases
  const fetchDatabases = async () => {
    setLoadingDbs(true);
    const res = await authenticatedFetch('/api/admin/databases');
    if (res?.ok) {
      const data = await res.json();
      setDatabases(data.databases || []);
    }
    setLoadingDbs(false);
  };

  // Run preview execution for a selected query
  const runPreview = async () => {
    if (!selectedQuery) return;
    setLoadingPreview(true);
    try {
      const res = await authenticatedFetch(`/api/admin/execute_for_preview/${selectedQuery.workspace_id}`, { method: 'POST' });
      if (res?.ok) {
        const data = await res.json();
        setPreviewData(data.data || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingPreview(false);
    }
  };

  // Handle query approval or rejection
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

  // Add a new database to the system and generate secure access credentials
  const handleAddDatabase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dbForm.servername || !dbForm.database_name) return;
    setAddingDb(true);
    try {
      const res = await authenticatedFetch('/api/admin/add_database', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          servername: dbForm.servername,
          database_name: dbForm.database_name,
          tech_name: dbForm.technology
        })
      });
      if (res?.ok) {
        const data = await res.json();
        // Set the generated credentials to show in the success modal
        setGeneratedCreds({
          username: data.db_username,
          password: data.db_password
        });
        setDbForm({ servername: '', database_name: '', technology: 'mssql' });
        fetchDatabases();
      } else {
        const errData = await res?.json();
        alert(errData?.detail || "Failed to add database.");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setAddingDb(false);
    }
  };

  // Select a database to load its schema and masking rules
  const handleSelectDatabase = async (db: Database) => {
    setSelectedDb(db);
    setSchema({});
    setMaskedColumns(new Set());
    setExpandedTables({});
    
    // Load schema & masking rules in parallel
    await Promise.all([
      discoverSchema(db.id),
      loadMaskingRules(db.id)
    ]);
  };

  // Discover tables & columns for a database
  const discoverSchema = async (dbId: number) => {
    setLoadingSchema(true);
    try {
      const res = await authenticatedFetch(`/api/admin/databases/${dbId}/discover_schema`);
      if (res?.ok) {
        const data = await res.json();
        setSchema(data || {});
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSchema(false);
    }
  };

  // Load persistent masking rules for a database
  const loadMaskingRules = async (dbId: number) => {
    try {
      const res = await authenticatedFetch(`/api/admin/databases/${dbId}/masking_rules`);
      if (res?.ok) {
        const rules: MaskingRule[] = await res.json();
        const masked = new Set<string>();
        rules.forEach(r => {
          if (r.is_active) {
            masked.add(`${r.table_name.toLowerCase()}.${r.column_name.toLowerCase()}`);
          }
        });
        setMaskedColumns(masked);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Toggle active masking rule on a specific table/column
  const handleToggleMasking = (tableName: string, columnName: string) => {
    const key = `${tableName.toLowerCase()}.` + `${columnName.toLowerCase()}`;
    const newMasked = new Set(maskedColumns);
    if (newMasked.has(key)) {
      newMasked.delete(key);
    } else {
      newMasked.add(key);
    }
    setMaskedColumns(newMasked);
  };

  // Save masking rules to backend
  const handleSaveMaskingRules = async () => {
    if (!selectedDb) return;
    setSavingRules(true);
    
    const rulesList: MaskingRule[] = [];
    Object.keys(schema).forEach(tableName => {
      schema[tableName].forEach(columnName => {
        const key = `${tableName.toLowerCase()}.${columnName.toLowerCase()}`;
        if (maskedColumns.has(key)) {
          rulesList.push({
            table_name: tableName,
            column_name: columnName,
            masking_type: 'default',
            is_active: true
          });
        }
      });
    });

    try {
      const res = await authenticatedFetch(`/api/admin/databases/${selectedDb.id}/masking_rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules: rulesList })
      });
      if (res?.ok) {
        alert("Masking rules updated successfully.");
      } else {
        alert("Failed to save masking rules.");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSavingRules(false);
    }
  };

  const toggleTableExpand = (tableName: string) => {
    setExpandedTables(prev => ({
      ...prev,
      [tableName]: !prev[tableName]
    }));
  };

  // Custom helper to safety lowercase
  const safetyLower = (val: string) => val ? val.toLowerCase() : '';

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Premium Dashboard Header with Sub-header Navigation */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-800 pb-5 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Yönetim Paneli</h1>
          <p className="text-sm text-gray-400 mt-1">Sorgu onayları, veritabanı bağlantıları ve veri maskeleme konfigürasyonları.</p>
        </div>
        
        {/* Modern Switcher Tabs */}
        <div className="flex bg-gray-900/80 border border-gray-800 p-1 rounded-xl mt-4 md:mt-0 shadow-inner">
          <button 
            onClick={() => setActiveTab('approvals')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
              activeTab === 'approvals' 
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Sorgu Onayları
            {queries.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs font-bold bg-red-500 text-white rounded-full leading-none animate-pulse">
                {queries.length}
              </span>
            )}
          </button>
          <button 
            onClick={() => setActiveTab('masking')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
              activeTab === 'masking' 
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            Veritabanı & Maskeleme
          </button>
        </div>
      </div>

      {/* ==================== TAB: QUERY APPROVALS ==================== */}
      {activeTab === 'approvals' && (
        <div>
          {queries.length === 0 ? (
            <div className="bg-gray-850 border border-gray-800 p-16 rounded-2xl text-center shadow-xl">
              <div className="inline-flex p-4 rounded-full bg-gray-800 text-indigo-400 mb-4">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white">Bekleyen Sorgu Bulunmuyor</h3>
              <p className="text-gray-400 text-sm mt-1 max-w-sm mx-auto">Tüm riskli sorgu analiz talepleri karara bağlanmış durumda.</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {queries.map(q => (
                <div key={q.workspace_id} className="bg-gray-850 border border-gray-800 hover:border-gray-700 rounded-xl p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 transition duration-200 shadow-md">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2.5">
                      <span className="font-semibold text-white text-lg">{q.username}</span>
                      <span className="text-xs font-medium bg-amber-900/40 text-amber-300 border border-amber-800/60 px-2.5 py-0.5 rounded-full">
                        {q.status === 'waiting_for_approval' ? 'Onay Bekliyor' : q.status}
                      </span>
                      {q.risk_type && (
                        <span className="text-xs font-medium bg-red-950/55 text-red-300 border border-red-850 px-2.5 py-0.5 rounded-full">
                          {q.risk_type} Riski
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-400 flex items-center gap-2 mb-3">
                      <span className="font-medium text-gray-300">{q.servername}</span>
                      <span className="text-gray-600">&bull;</span>
                      <span className="font-medium text-gray-300">{q.database}</span>
                    </div>
                    <div className="bg-gray-900/90 border border-gray-800/80 p-3.5 rounded-lg font-mono text-xs text-gray-300 max-w-4xl overflow-hidden text-ellipsis whitespace-nowrap">
                      {q.query}
                    </div>
                  </div>
                  <button 
                    onClick={() => {
                      setSelectedQuery(q);
                      setPreviewData([]);
                    }}
                    className="w-full md:w-auto bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-indigo-600/10 flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                    İncele
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ==================== TAB: DATABASE & MASKING ==================== */}
      {activeTab === 'masking' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column: DB Registration & DB List */}
          <div className="lg:col-span-5 flex flex-col gap-6">
            
            {/* Database Registration Form */}
            <div className="bg-gray-850 border border-gray-800 rounded-2xl p-6 shadow-md">
              <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-4 border-b border-gray-800 pb-3">
                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Yeni Veritabanı Ekle
              </h2>
              
              <form onSubmit={handleAddDatabase} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Sunucu Adresi (Host)</label>
                  <input 
                    type="text"
                    required
                    placeholder="örn. localhost veya 10.0.0.5"
                    value={dbForm.servername}
                    onChange={e => setDbForm({ ...dbForm, servername: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-800 hover:border-gray-700 focus:border-indigo-600 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Veritabanı Adı</label>
                    <input 
                      type="text"
                      required
                      placeholder="örn. Northwind"
                      value={dbForm.database_name}
                      onChange={e => setDbForm({ ...dbForm, database_name: e.target.value })}
                      className="w-full bg-gray-900 border border-gray-800 hover:border-gray-700 focus:border-indigo-600 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Teknoloji</label>
                    <select
                      value={dbForm.technology}
                      onChange={e => setDbForm({ ...dbForm, technology: e.target.value })}
                      className="w-full bg-gray-900 border border-gray-800 hover:border-gray-700 focus:border-indigo-600 rounded-lg px-3 py-2.5 text-sm text-white outline-none transition"
                    >
                      <option value="mssql">MS SQL Server</option>
                      <option value="postgresql">PostgreSQL</option>
                      <option value="mysql">MySQL</option>
                    </select>
                  </div>
                </div>

                <button 
                  type="submit"
                  disabled={addingDb}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-800 text-white font-semibold py-2.5 rounded-lg text-sm transition shadow-md shadow-indigo-600/10 mt-2"
                >
                  {addingDb ? 'Veritabanı Ekleniyor...' : 'Ekle & Güvenli Kullanıcı Üret'}
                </button>
              </form>
            </div>

            {/* Database List */}
            <div className="bg-gray-850 border border-gray-800 rounded-2xl p-6 shadow-md flex-1">
              <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-4 border-b border-gray-800 pb-3">
                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.58 4 8 4s8-1.79 8-4M4 7c0-2.21 3.58-4 8-4s8 1.79 8 4m0 5c0 2.21-3.58 4-8 4s-8-1.79-8-4" />
                </svg>
                Kayıtlı Veritabanları
              </h2>

              {loadingDbs ? (
                <div className="text-center py-8 text-gray-500 text-sm">Veritabanları yükleniyor...</div>
              ) : databases.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-sm">Henüz kayıtlı veritabanı bulunmuyor.</div>
              ) : (
                <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
                  {databases.map(db => (
                    <button
                      key={db.id}
                      onClick={() => handleSelectDatabase(db)}
                      className={`w-full text-left p-3 rounded-xl border transition duration-150 flex justify-between items-center ${
                        selectedDb?.id === db.id 
                          ? 'bg-indigo-900/30 border-indigo-700 text-white' 
                          : 'bg-gray-900/60 border-gray-800 hover:border-gray-700 text-gray-300 hover:text-white'
                      }`}
                    >
                      <div>
                        <div className="font-semibold text-sm">{db.database_name}</div>
                        <div className="text-xs text-gray-400 mt-0.5">{db.servername} &bull; {db.technology.toUpperCase()}</div>
                      </div>
                      <svg className={`w-4.5 h-4.5 transition-transform duration-200 ${selectedDb?.id === db.id ? 'text-indigo-400 transform translate-x-0.5' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                  ))}
                </div>
              )}
            </div>

          </div>

          {/* Right Column: Schema TreeView & Masking Rules */}
          <div className="lg:col-span-7">
            {selectedDb ? (
              <div className="bg-gray-850 border border-gray-800 rounded-2xl p-6 shadow-md h-full flex flex-col">
                
                {/* Panel Header */}
                <div className="flex flex-wrap justify-between items-center border-b border-gray-800 pb-4 mb-4 gap-4">
                  <div>
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                      <span className="text-indigo-400">#</span>
                      {selectedDb.database_name} Maskeleme Kuralları
                    </h2>
                    <p className="text-xs text-gray-400 mt-0.5">{selectedDb.servername} sunucusundaki aktif şema kolonları.</p>
                  </div>
                  
                  <button 
                    onClick={() => discoverSchema(selectedDb.id)}
                    disabled={loadingSchema}
                    className="bg-gray-800 hover:bg-gray-700 disabled:bg-gray-850 text-xs font-semibold text-gray-300 hover:text-white px-3 py-2 rounded-lg border border-gray-700 transition flex items-center gap-1.5"
                  >
                    <svg className={`w-3.5 h-3.5 ${loadingSchema ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
                    </svg>
                    Şemayı Yenile
                  </button>
                </div>

                {/* Schema TreeView Container */}
                <div className="flex-1 min-h-[380px] max-h-[480px] overflow-y-auto bg-gray-900/65 border border-gray-800/80 rounded-xl p-4">
                  {loadingSchema ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-2">
                      <svg className="w-8 h-8 text-indigo-500 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span className="text-sm font-medium">Veritabanı şeması taranıyor...</span>
                    </div>
                  ) : Object.keys(schema).length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-500 text-sm text-center px-6">
                      <svg className="w-10 h-10 text-gray-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      Bu veritabanına ait tablo bilgisi bulunamadı veya bağlantı kurulamadı. Lütfen sunucu ayarlarını ve ağ erişimini kontrol edin.
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {Object.keys(schema).map(tableName => {
                        const isExpanded = !!expandedTables[tableName];
                        const columns = schema[tableName];
                        return (
                          <div key={tableName} className="border border-gray-800/60 rounded-lg overflow-hidden bg-gray-950/40">
                            {/* Table Node */}
                            <button
                              onClick={() => toggleTableExpand(tableName)}
                              className="w-full flex items-center justify-between p-3 hover:bg-gray-800/25 transition text-left"
                            >
                              <div className="flex items-center gap-2">
                                <svg className={`w-4 h-4 text-gray-400 transition-transform duration-150 ${isExpanded ? 'transform rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                                </svg>
                                <svg className="w-4 h-4 text-indigo-400/80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                                <span className="font-semibold text-sm text-gray-200">{tableName}</span>
                              </div>
                              <span className="text-xs text-indigo-400/85 font-semibold bg-indigo-950/40 px-2 py-0.5 rounded-full">
                                {columns.length} Kolon
                              </span>
                            </button>

                            {/* Column Leaf Nodes (Expanded) */}
                            {isExpanded && (
                              <div className="border-t border-gray-900 bg-gray-950/80 px-4 py-2 space-y-1.5 pl-9">
                                {columns.map(col => {
                                  const isMasked = maskedColumns.has(`${tableName.toLowerCase()}.${col.toLowerCase()}`);
                                  return (
                                    <div 
                                      key={col} 
                                      onClick={() => handleToggleMasking(tableName, col)}
                                      className="flex items-center justify-between py-1.5 hover:bg-gray-900/40 rounded px-2 cursor-pointer select-none"
                                    >
                                      <span className="text-xs text-gray-300 font-mono">{col}</span>
                                      <div className="flex items-center gap-2">
                                        {isMasked && (
                                          <span className="text-[10px] uppercase font-bold bg-amber-950/50 text-amber-400 border border-amber-800/40 px-1.5 py-0.2 rounded">
                                            Maskeli
                                          </span>
                                        )}
                                        <input 
                                          type="checkbox" 
                                          checked={isMasked}
                                          onChange={() => {}} // Handled by div onClick
                                          className="w-4 h-4 rounded text-indigo-600 bg-gray-900 border-gray-700 focus:ring-indigo-600 focus:ring-offset-gray-900"
                                        />
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Save Rules Button */}
                <div className="mt-5 border-t border-gray-800 pt-4 flex justify-between items-center">
                  <span className="text-xs text-gray-400 font-medium">
                    Toplam <span className="text-amber-400 font-bold">{maskedColumns.size}</span> kolon maskelenmek üzere seçildi.
                  </span>
                  <button 
                    onClick={handleSaveMaskingRules}
                    disabled={savingRules || loadingSchema}
                    className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-800 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition shadow-md shadow-indigo-600/10 flex items-center gap-2"
                  >
                    {savingRules ? (
                      <>
                        <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
                        </svg>
                        Kaydediliyor...
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                        </svg>
                        Kuralları Kaydet
                      </>
                    )}
                  </button>
                </div>

              </div>
            ) : (
              <div className="bg-gray-850 border border-gray-800 p-16 rounded-2xl text-center shadow-xl h-full flex flex-col items-center justify-center">
                <div className="p-4 rounded-full bg-gray-800 text-indigo-400 mb-4">
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold text-white">Maskeleme Yönetimi</h3>
                <p className="text-gray-400 text-sm mt-1 max-w-xs mx-auto">Sol paneldeki kayıtlı veritabanlarından birini seçerek aktif şema kolonları üzerinde maskeleme kuralları tanımlayabilirsiniz.</p>
              </div>
            )}
          </div>

        </div>
      )}

      {/* ==================== MODAL: GENERATED CREDENTIALS ==================== */}
      {generatedCreds && (
        <Modal 
          isOpen={true} 
          onClose={() => setGeneratedCreds(null)} 
          title="Veritabanı Erişim Bilgileri" 
          size="md"
        >
          <div className="space-y-4">
            <div className="bg-amber-950/40 border border-amber-900/50 p-4 rounded-xl flex gap-3">
              <svg className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <h4 className="text-xs font-bold text-amber-300 uppercase">Önemli Güvenlik Uyarısı</h4>
                <p className="text-xs text-amber-400/90 mt-1 leading-relaxed">
                  WebQuery, bu veritabanına erişmek için aşağıdaki benzersiz servis hesabı kimlik bilgilerini üretmiştir. Şifre sadece <strong>bir kez</strong> gösterilecektir. Lütfen bilgileri güvenli bir yere kaydedin.
                </p>
              </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3 font-mono text-xs">
              <div className="flex justify-between items-center">
                <span className="text-gray-400 uppercase font-bold text-[10px]">Üretilen Kullanıcı Adı:</span>
                <span className="text-indigo-300 font-semibold select-all">{generatedCreds.username}</span>
              </div>
              <div className="border-t border-gray-800/50 pt-2.5 flex justify-between items-center">
                <span className="text-gray-400 uppercase font-bold text-[10px]">Üretilen Şifre:</span>
                <span className="text-indigo-300 font-semibold select-all">{generatedCreds.password}</span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button 
                onClick={() => {
                  navigator.clipboard.writeText(`Username: ${generatedCreds.username}\nPassword: ${generatedCreds.password}`);
                  alert("Credentials copied to clipboard.");
                  setGeneratedCreds(null);
                }}
                className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition flex items-center gap-1.5"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                </svg>
                Kopyala & Kapat
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ==================== MODAL: REVIEW QUERY ==================== */}
      {selectedQuery && (
        <Modal 
          isOpen={true} 
          onClose={() => setSelectedQuery(null)} 
          title="Sorgu Talebi İncelemesi" 
          size="xl"
        >
          <div className="flex flex-col gap-5">
            
            {/* Metadata Summary Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-gray-900 border border-gray-800 p-4 rounded-xl text-xs font-medium">
              <div>
                <span className="text-gray-400 block mb-0.5">Kullanıcı:</span>
                <span className="text-white text-sm font-bold">{selectedQuery.username}</span>
              </div>
              <div>
                <span className="text-gray-400 block mb-0.5">Sunucu:</span>
                <span className="text-white text-sm font-semibold">{selectedQuery.servername}</span>
              </div>
              <div>
                <span className="text-gray-400 block mb-0.5">Veritabanı:</span>
                <span className="text-white text-sm font-semibold">{selectedQuery.database}</span>
              </div>
              <div>
                <span className="text-gray-400 block mb-0.5">Risk Seviyesi:</span>
                <span className={`text-sm font-bold ${selectedQuery.risk_type ? 'text-red-400' : 'text-emerald-400'}`}>
                  {selectedQuery.risk_type || 'Yok'}
                </span>
              </div>
            </div>

            {/* SQL Query Editor Preview */}
            <div>
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5 block">SQL Sorgusu</label>
              <div className="border border-gray-800 rounded-xl overflow-hidden">
                <AceEditor value={selectedQuery.query} readOnly={true} height="220px" />
              </div>
            </div>

            {/* Result Preview Panel */}
            <div className="border-t border-gray-800 pt-5">
              <div className="flex justify-between items-center mb-3">
                <h4 className="text-xs font-bold uppercase text-gray-400 tracking-wider">Sonuç Önizleme</h4>
                <button 
                  onClick={runPreview} 
                  disabled={loadingPreview} 
                  className="bg-gray-850 hover:bg-gray-800 border border-gray-700 disabled:bg-gray-900 text-xs font-semibold text-white px-3.5 py-1.5 rounded-lg transition flex items-center gap-1"
                >
                  {loadingPreview ? (
                    <>
                      <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
                      </svg>
                      Çalıştırılıyor...
                    </>
                  ) : (
                    <>
                      <svg className="w-3 h-3 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Önizleme Çalıştır
                    </>
                  )}
                </button>
              </div>

              <div className="bg-gray-900 border border-gray-800 rounded-xl h-48 overflow-auto">
                {previewData.length > 0 ? (
                  <table className="w-full text-xs text-left border-collapse">
                    <thead className="bg-gray-850 text-gray-300 border-b border-gray-800 sticky top-0">
                      <tr>
                        {Object.keys(previewData[0]).map(k => (
                          <th key={k} className="p-3 font-semibold border-r border-gray-800 last:border-0">{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800/60">
                      {previewData.map((r, i) => (
                        <tr key={i} className="hover:bg-gray-850/30 text-gray-300 transition duration-100">
                          {Object.values(r).map((v: any, j) => (
                            <td key={j} className="p-3 border-r border-gray-800/40 last:border-0 font-mono whitespace-nowrap overflow-hidden text-ellipsis max-w-[200px]">
                              {String(v)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-500 text-xs">
                    Önizleme verilerini görüntülemek için yukarıdaki 'Önizleme Çalıştır' butonuna basın.
                  </div>
                )}
              </div>
            </div>

            {/* Action Decision Buttons */}
            <div className="flex flex-wrap justify-end gap-3 pt-3 border-t border-gray-800 mt-2">
              <button 
                onClick={() => handleDecision(false)} 
                className="bg-red-650 hover:bg-red-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-red-900/10"
              >
                Reddet
              </button>
              <button 
                onClick={() => handleDecision(true, false)} 
                className="bg-amber-600 hover:bg-amber-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-amber-700/10"
              >
                Onayla (Gözlem Modu)
              </button>
              <button 
                onClick={() => handleDecision(true, true)} 
                className="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition shadow-md shadow-emerald-700/10"
              >
                Onayla & Çalıştırılabilir Yap
              </button>
            </div>

          </div>
        </Modal>
      )}

    </div>
  );
};

export default Admin;
