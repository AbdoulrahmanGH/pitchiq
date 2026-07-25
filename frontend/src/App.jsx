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

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg)' }}>
          <Sidebar />
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <Routes>
              <Route path="/"        element={<RequireAuth><Dashboard /></RequireAuth>} />
              <Route path="/players" element={<RequireAuth><Players /></RequireAuth>} />
              <Route path="/matches" element={<RequireAuth><Matches /></RequireAuth>} />
              <Route path="/depth"   element={<RequireAuth><SquadDepth /></RequireAuth>} />
              <Route path="/about"   element={<RequireAuth><About /></RequireAuth>} />
              <Route path="/login"   element={<Login />} />
            </Routes>
          </div>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}
