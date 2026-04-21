import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Players from './pages/Players';
import Matches from './pages/Matches';
import SquadDepth from './pages/SquadDepth';

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg)' }}>
        <Sidebar />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Routes>
            <Route path="/"        element={<Dashboard />} />
            <Route path="/players" element={<Players />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/depth"   element={<SquadDepth />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
