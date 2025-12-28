
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authenticatedFetch } from '../services/api';

const Register: React.FC = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);

    try {
      const response = await authenticatedFetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password })
      });

      if (response && response.ok) {
        setMessage({ type: 'success', text: 'Registration successful! Redirecting...' });
        setTimeout(() => navigate('/login'), 2000);
      } else {
        const data = await response?.json();
        setMessage({ type: 'error', text: data?.error || 'Registration failed.' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'A network error occurred.' });
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 p-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-full opacity-10 pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-600 rounded-full blur-[120px]"></div>
        <div className="absolute bottom-[-10%] left-[-10%] w-[40%] h-[40%] bg-emerald-600 rounded-full blur-[120px]"></div>
      </div>

      <div className="w-full max-w-md bg-gray-900/50 backdrop-blur-xl rounded-3xl shadow-2xl p-10 border border-gray-800 relative z-10">
        <div className="flex flex-col items-center mb-8">
          <h2 className="text-4xl font-black text-white tracking-tighter uppercase">Register</h2>
          <p className="text-gray-500 text-[10px] font-bold mt-1 tracking-[0.3em] uppercase">Initialize Profile</p>
        </div>
        
        {message && (
          <div className={`mb-4 p-3 border rounded text-[10px] font-bold uppercase text-center tracking-widest ${message.type === 'success' ? 'bg-green-900/20 border-green-700/50 text-green-400' : 'bg-red-900/20 border-red-900/50 text-red-400'}`}>
            {message.text}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Username</label>
            <input 
              type="text" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium" 
              value={username} 
              onChange={(e) => setUsername(e.target.value)} 
              placeholder="operator_01"
              required 
            />
          </div>
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Email</label>
            <input 
              type="email" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium" 
              value={email} 
              onChange={(e) => setEmail(e.target.value)} 
              placeholder="email@webquery.io"
              required 
            />
          </div>
          <div>
            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1.5 ml-1">Password</label>
            <input 
              type="password" 
              className="w-full bg-gray-950 border border-gray-800 text-white rounded-xl p-3.5 focus:ring-1 focus:ring-indigo-500 outline-none transition-all placeholder:text-gray-700 font-medium" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              placeholder="••••••••"
              required 
            />
          </div>
          
          <div className="pt-4 flex flex-col gap-3">
            <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-black py-4 px-4 rounded-xl transition-all shadow-xl shadow-indigo-600/20 active:scale-95 uppercase tracking-widest text-xs">
              Create Account
            </button>
            <Link to="/login" className="w-full bg-gray-800/50 hover:bg-gray-800 text-gray-400 hover:text-white font-black py-4 px-4 rounded-xl transition-all border border-gray-800 text-center uppercase tracking-widest text-xs">
              Back to Connection
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Register;
