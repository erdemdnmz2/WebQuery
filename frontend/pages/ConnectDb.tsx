import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authenticatedFetch } from '../services/api';

const ConnectDb: React.FC = () => {
  const [dbName, setDbName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await authenticatedFetch('/api/mssql-connect', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ databaseName: dbName, username, password })
      });
      
      if (res?.ok) {
        alert('Connected successfully');
        navigate('/');
      } else {
        alert('Connection failed');
      }
    } catch (e) {
      alert('Network error');
    }
  };

  return (
    <div className="flex justify-center pt-10">
      <div className="w-full max-w-md bg-gray-800 p-8 rounded-xl border border-gray-700 shadow-xl">
         <h2 className="text-2xl font-bold text-white mb-6 text-center">Connect MSSQL</h2>
         <form onSubmit={handleSubmit} className="space-y-4">
            <div>
               <label className="block text-gray-400 text-sm mb-1">Database Name</label>
               <input value={dbName} onChange={e => setDbName(e.target.value)} className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white" required />
            </div>
            <div>
               <label className="block text-gray-400 text-sm mb-1">Username</label>
               <input value={username} onChange={e => setUsername(e.target.value)} className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white" required />
            </div>
            <div>
               <label className="block text-gray-400 text-sm mb-1">Password</label>
               <input type="password" value={password} onChange={e => setPassword(e.target.value)} className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white" required />
            </div>
            <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 rounded mt-2">Connect</button>
         </form>
      </div>
    </div>
  );
};

export default ConnectDb;
