import { useState, useEffect } from 'react'
import nexusLogo from '/logo-128.png'
import './App.css'

function App() {
  const [count, setCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [showContent, setShowContent] = useState(false)

  // Simulate loading on first open
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsLoading(false)
      setTimeout(() => setShowContent(true), 300)
    }, 2200)
    return () => clearTimeout(timer)
  }, [])

  const tableData = [
    { id: 1, name: "Project Alpha", status: "Active", date: "2026-01-15" },
    { id: 2, name: "Research Beta", status: "Pending", date: "2026-02-20" },
    { id: 3, name: "Extension Gamma", status: "Completed", date: "2026-03-10" },
  ]

  if (isLoading) {
    return (
      <div className="loading-screen">
        <div className="logo-container">
          <img 
            src={nexusLogo} 
            className="logo logo-animate" 
            alt="NExUS Logo" 
          />
          <div className="logo-glow"></div>
        </div>
        <h2 className="loading-text">NExUS</h2>
        <p className="loading-subtitle">Networked Extension Unified System</p>
        <div className="loading-bar">
          <div className="loading-progress"></div>
        </div>
      </div>
    )
  }

  return (
    <div className={`app ${showContent ? 'fade-in' : ''}`}>
      <div className="header">
        <div className="logo-header">
          <img src={nexusLogo} className="logo-small" alt="NExUS" />
          <div>
            <h1>NExUS</h1>
            <p className="subtitle">Networked Extension Unified System</p>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Demo Dashboard</h2>
        <div className="stats">
          <div className="stat-card">
            <span className="stat-number">124</span>
            <span className="stat-label">Projects</span>
          </div>
          <div className="stat-card">
            <span className="stat-number">87</span>
            <span className="stat-label">Active Users</span>
          </div>
        </div>

        <div className="demo-table">
          <h3>Recent Activities</h3>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Status</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tableData.map(item => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.name}</td>
                  <td>
                    <span className={`status ${item.status.toLowerCase()}`}>
                      {item.status}
                    </span>
                  </td>
                  <td>{item.date}</td>
                  <td className="actions">
                    <button 
                      className="icon-btn view" 
                      title="View"
                      onClick={() => alert(`Viewing ${item.name}`)}
                    >
                      👁️
                    </button>
                    <button 
                      className="icon-btn edit" 
                      title="Edit"
                      onClick={() => alert(`Editing ${item.name}`)}
                    >
                      ✏️
                    </button>
                    <button 
                      className="icon-btn delete" 
                      title="Delete"
                      onClick={() => alert(`Deleting ${item.name}`)}
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <button onClick={() => setCount((count) => count + 1)}>
            <span className="btn-icon">🔢</span> count is {count}
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
