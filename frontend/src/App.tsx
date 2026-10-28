import { useEffect, useState } from 'react'
import { getHealth } from './api'

type BackendState = 'checking' | 'ok' | 'down'

function App() {
  const [backend, setBackend] = useState<BackendState>('checking')

  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal)
      .then((health) => setBackend(health.status === 'ok' ? 'ok' : 'down'))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error(error)
          setBackend('down')
        }
      })
    return () => controller.abort()
  }, [])

  return (
    <main className="page">
      <header>
        <h1>OAuth App Setup Guides</h1>
        <p className="lead">
          How hard is it to create and get approval for an OAuth app with a provider? Look up an
          app, see the time and effort including review waits, and know what to do next.
        </p>
      </header>
      <p role="status" className={`status status-${backend}`}>
        {backend === 'checking' && 'Checking the backend...'}
        {backend === 'ok' && 'Backend: ok'}
        {backend === 'down' && 'Backend: unreachable. Try again in a minute.'}
      </p>
    </main>
  )
}

export default App
