import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <section className="message">
      <h1>Page not found</h1>
      <p>
        <Link to="/">Back to the guide library</Link>
      </p>
    </section>
  )
}
