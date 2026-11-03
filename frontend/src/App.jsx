import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Nav from './components/Nav'
import Home from './pages/Home'
import Players from './pages/Players'
import PlayerProfile from './pages/PlayerProfile'
import Scout from './pages/Scout'
import Compare from './pages/Compare'
import Rankings from './pages/Rankings'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import About from './pages/About'
import Eval from './pages/Eval'

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/"            element={<Home />} />
        <Route path="/players"     element={<Players />} />
        <Route path="/players/:pid" element={<PlayerProfile />} />
        <Route path="/scout"       element={<Scout />} />
        <Route path="/compare"     element={<Compare />} />
        <Route path="/rankings"    element={<Rankings />} />
        <Route path="/dashboard"   element={<Dashboard />} />
        <Route path="/explain"     element={<Navigate to="/dashboard" replace />} />
        <Route path="/chat"        element={<Chat />} />
        <Route path="/about"       element={<About />} />
        <Route path="/eval"        element={<Eval />} />
        <Route path="*"            element={<NotFound />} />
      </Routes>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'var(--c-card2)',
            color: 'var(--c-text)',
            border: '1px solid var(--c-border2)',
          },
        }}
      />
    </BrowserRouter>
  )
}

function NotFound() {
  return (
    <div style={{ textAlign: 'center', padding: '120px 24px' }}>
      <div style={{ fontSize: '4rem', marginBottom: 16 }}>⚽</div>
      <h2 style={{ marginBottom: 12 }}>Page not found</h2>
      <p style={{ color: 'var(--c-muted)', marginBottom: 24 }}>That page is offside.</p>
      <a href="/" className="btn btn-primary">← Back to Home</a>
    </div>
  )
}
