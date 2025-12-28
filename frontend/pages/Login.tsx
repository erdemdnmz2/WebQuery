
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authenticatedFetch } from '../services/api';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const response = await authenticatedFetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      if (response && response.ok) {
        navigate('/');
      } else {
        const data = await response?.json();
        setError(data?.error || "Connection refused. Ensure the backend is running.");
      }
    } catch (err) {
      setError("Network error occurred while attempting to establish connection.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 p-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-full opacity-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-indigo-600 rounded-full blur-[120px]"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-emerald-600 rounded-full blur-[120px]"></div>
      </div>

      <div className="w-full max-w-md bg-gray-900/50 backdrop-blur-xl rounded-3xl shadow-2xl p-10 border border-gray-800 relative z-10">
        <div className="flex flex-col items-center mb-8">
          <h2 className="text-4xl font-black text-white tracking-tighter uppercase">WebQuery</h2>
          <p className="text-gray-500 text-[10px] font-bold mt-1 tracking-[0.3em] uppercase">Data Infrastructure</p>
        </div>
        
        {error && (
          <div className="mb-4 p-3 bg-red-900/20 border border-red-900/50 text-red-400 text-[10px] font-bold uppercase rounded-lg text-center tracking-widest">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Identity (Email)</label>
            <input 
              type="email" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@webquery.io"
              required
            />
          </div>
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Secure Code (Password)</label>
            <input 
              type="password" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>
          
          <div className="pt-4 flex flex-col gap-4">
            <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-black py-4 px-4 rounded-xl transition-all shadow-xl shadow-indigo-600/20 active:scale-95 uppercase tracking-widest text-xs">
              Establish Connection
            </button>
            
            <div className="flex flex-col gap-2 items-center">
              <Link to="/register" className="text-[10px] text-gray-400 hover:text-indigo-400 font-black uppercase tracking-widest transition-colors">
                Create New Identity
              </Link>
              <div className="text-center text-[9px] text-gray-700 font-bold uppercase tracking-tighter mt-2">
                Authorized personnel only beyond this point.
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
