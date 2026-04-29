import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import Products from './pages/Products'
import Optimizer from './pages/Optimizer'
import History from './pages/History'

export default function App() {
  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/products" element={<Products />} />
          <Route path="/optimizer" element={<Optimizer />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </main>
    </div>
  )
}
