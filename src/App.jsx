import { useEffect, useState } from 'react'
import ClassifierPage from './ClassifierPage.jsx'
import TestResultsPage from './TestResultsPage.jsx'

// Which page the URL points to: "#/tests" is Test results, anything else is the Classifier.
// Using the URL hash means the tabs are real links and a page refresh stays on the same tab.
function pageFromHash() {
  return window.location.hash === '#/tests' ? 'tests' : 'classifier'
}

export default function App() {
  const [page, setPage] = useState(pageFromHash)
  // The file last classified on the Classifier tab; the Test results tab tests this same file.
  const [classifiedFile, setClassifiedFile] = useState(null)

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  // Both pages stay mounted and the other one is hidden, so switching tabs
  // keeps each page's uploaded file and results.
  return (
    <div className="min-h-screen bg-[#F7F8FA] font-['Inter',system-ui,sans-serif] text-[#16181D]">
      <div hidden={page !== 'classifier'}><ClassifierPage onClassified={setClassifiedFile} /></div>
      <div hidden={page !== 'tests'}><TestResultsPage testFile={classifiedFile} /></div>
    </div>
  )
}
