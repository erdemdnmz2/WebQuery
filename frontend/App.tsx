
import React from 'react';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Home from './pages/Home';
import SqlEditor from './pages/SqlEditor';
import Admin from './pages/Admin';
import WorkspaceExecute from './pages/WorkspaceExecute';

const App: React.FC = () => {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<Home />} />
          <Route path="/editor" element={<SqlEditor />} />
          <Route path="/editor/:workspaceId" element={<SqlEditor />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/execute/:workspaceId" element={<WorkspaceExecute />} />
        </Routes>
      </Layout>
    </Router>
  );
};

export default App;
