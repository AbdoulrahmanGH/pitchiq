import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import RequireAuth from './components/RequireAuth';
import { AuthProvider } from './services/AuthProvider';
import Dashboard from './pages/Dashboard';
import Players from './pages/Players';
import Matches from './pages/Matches';
import SquadDepth from './pages/SquadDepth';
import About from './pages/About';
import Login from './pages/Login';

// /login is a standalone page -- no sidebar/nav chrome. Everything else
// sits inside the app shell (sidebar + content column).
function AppShell({ children }) {
  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {children}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<AppShell><RequireAuth><Dashboard /></RequireAuth></AppShell>} />
          <Route path="/players" element={<AppShell><RequireAuth><Players /></RequireAuth></AppShell>} />
          <Route path="/matches" element={<AppShell><RequireAuth><Matches /></RequireAuth></AppShell>} />
          <Route path="/depth" element={<AppShell><RequireAuth><SquadDepth /></RequireAuth></AppShell>} />
          <Route path="/about" element={<AppShell><RequireAuth><About /></RequireAuth></AppShell>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
