import { Link, NavLink, Route, Routes } from 'react-router-dom'
import GeneratePage from './pages/GeneratePage'
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
            <span className="brand-mark" aria-hidden="true" />
            <span>
              OAuth<span className="hide-small"> App Setup</span> Guides
            </span>
          </Link>
          <nav className="site-nav" aria-label="Main">
            <NavLink to="/" end>
              Library
            </NavLink>
            <NavLink to="/generate">
              Investigate<span className="hide-small"> an app</span>
            </NavLink>
          </nav>
        </div>
      </header>
      <main id="main" className="container">
        <Routes>
          <Route path="/" element={<LibraryPage />} />
          <Route path="/guides/:slug" element={<GuidePage />} />
          <Route path="/generate" element={<GeneratePage />} />
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
