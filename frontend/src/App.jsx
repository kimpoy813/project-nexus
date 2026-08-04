import { useState } from 'react'
import nexusLogo from '/logo-128.png'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <div>
        <img src={nexusLogo} className="logo" alt="ISPSC-RDEI Extension Office logo" />
      </div>
      <h1>NExUS</h1>
      <p className="read-the-docs">Networked Extension Unified System</p>
      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          count is {count}
        </button>
      </div>
    </>
  )
}

export default App
