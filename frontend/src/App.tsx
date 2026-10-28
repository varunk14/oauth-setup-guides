import { Link, Route, Routes } from 'react-router-dom'
import GuidePage from './pages/GuidePage'
import LibraryPage from './pages/LibraryPage'
import NotFoundPage from './pages/NotFoundPage'

function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="container">
          <Link to="/" className="brand">
            OAuth App Setup Guides
          </Link>
        </div>
      </header>
      <main id="main" className="container">
        <Routes>
          <Route path="/" element={<LibraryPage />} />
          <Route path="/guides/:slug" element={<GuidePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <footer className="site-footer container">
        Every claim is labelled TESTED, SOURCED, INFERRED or UNVERIFIED. Provider rules change;
        check the linked sources before you rely on a detail.
      </footer>
    </>
  )
}

export default App
