
import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { authenticatedFetch } from '../services/api';
import { User } from '../types';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const response = await authenticatedFetch('/api/me');
        if (response && response.ok) {
          const data = await response.json();
          setUser(data);
        } else {
          if (!['/login', '/register'].includes(location.pathname)) {
            navigate('/login');
          }
        }
      } catch (e) {
        if (!['/login', '/register'].includes(location.pathname)) {
          navigate('/login');
        }
      }
    };
    fetchUser();
  }, [navigate, location.pathname]);

  const handleLogout = async () => {
    try { await authenticatedFetch('/api/logout', { method: 'POST' }); } catch(e) {}
    setUser(null);
    navigate('/login');
  };

  if (['/login', '/register'].includes(location.pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans selection:bg-indigo-500/30">
      <nav className="fixed top-0 left-0 right-0 z-[100] bg-gray-900/80 backdrop-blur-md border-b border-gray-800 h-16 flex items-center justify-between px-6">
        <div className="flex items-center gap-10">
          <Link to="/" className="flex items-center gap-3 group">
            <span className="text-lg font-black tracking-tighter text-white group-hover:text-indigo-400 transition-colors uppercase">WEBQuery</span>
          </Link>
          <div className="hidden md:flex gap-1 bg-gray-950 p-1 rounded-lg border border-gray-800">
            {[
              { to: "/", label: "Explorer" },
              { to: "/editor", label: "SQL Studio" },
            ].map(link => (
              <Link 
                key={link.to} 
                to={link.to} 
                className={`px-4 py-2 rounded-md text-[13px] font-bold transition-all ${
                  location.pathname === link.to ? 'bg-gray-800 text-indigo-400 shadow-sm' : 'text-gray-500 hover:text-white hover:bg-gray-800/50'
                }`}
              >
                {link.label}
              </Link>
            ))}
            {user?.is_admin && (
              <Link to="/admin" className="px-4 py-2 rounded-md text-[13px] font-bold text-emerald-500/80 hover:text-emerald-400 hover:bg-emerald-400/10 transition-colors">ADMIN PANEL</Link>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex flex-col items-end">
             <span className="text-xs font-bold text-indigo-400">
               {user?.username || 'Guest'}
             </span>
          </div>
          <button 
            onClick={handleLogout}
            className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-900 border border-gray-800 hover:border-red-900/50 hover:bg-red-900/10 text-gray-500 hover:text-red-500 transition-all"
            title="Sign Out"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
          </button>
        </div>
      </nav>

      <main className="pt-24 px-6 md:px-10 pb-10 h-full">
        {children}
      </main>
    </div>
  );
};

export default Layout;
