import { useEffect, useRef, useState } from 'react'
import { MAX_UPLOAD_BYTES, PageHeader, Pagination, focusRing, primaryButton, secondaryButton } from './ui.jsx'

const MISTAKES_PER_PAGE = 10

// Precision/recall come from the API as a number (66.7) or null when the
// denominator is 0, which the spec says to show as "—".
const percent = (value) => (value === null ? '—' : `${value}%`)

// A small label above a button. The button shows the chosen file's name.
function FilePicker({ id, label, file, onChange, disabled }) {
  const input = useRef(null)
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span id={`${id}-label`} className="text-xs font-semibold text-[#4A5160]">{label}</span>
      <button type="button" onClick={() => input.current.click()} disabled={disabled}
        aria-describedby={`${id}-label`} title={file ? file.name : undefined}
        className={`${secondaryButton} max-w-56 truncate ${file ? 'font-mono font-normal!' : ''}`}>
        {file ? file.name : 'Choose file'}
      </button>
      <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" tabIndex={-1} aria-hidden="true"
        onChange={(event) => {
          onChange(event.target.files[0] || null)
          event.target.value = '' // allow choosing the same file again
        }} />
    </div>
  )
}

function ByClassTable({ classes }) {
  const headers = ['Class', 'True positives (TP)', 'False positives (FP)', 'False negatives (FN)', 'Precision', 'Recall']
  return (
    <section className="overflow-hidden rounded-xl border border-[#E3E6EB] bg-white">
      <h2 className="border-b border-[#E3E6EB] px-5 py-4 text-base font-semibold">By class</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left text-sm tabular-nums">
          <thead className="bg-[#F7F8FA] text-xs font-semibold tracking-wide text-[#4A5160] uppercase">
            <tr>
              {headers.map((header) => (
                <th key={header} scope="col" className="px-5 py-3 font-semibold">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {classes.map((row) => (
              <tr key={row.data_class} className="border-t border-[#EEF0F3]">
                <th scope="row" className="px-5 py-3.5 font-normal">
                  <span className="inline-block rounded-full bg-[#E8EEFC] px-2.5 py-1 text-[13px] font-semibold whitespace-nowrap text-[#1F3F9E]">
                    {row.data_class}
                  </span>
                </th>
                <td className="px-5 py-3.5">{row.tp}</td>
                <td className="px-5 py-3.5">{row.fp}</td>
                <td className="px-5 py-3.5">{row.fn}</td>
                <td className="px-5 py-3.5 font-semibold">{percent(row.precision)}</td>
                <td className="px-5 py-3.5 font-semibold">{percent(row.recall)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-[#E3E6EB] px-5 py-3.5 text-[13px] leading-normal text-[#5B6270]">
        Precision = TP ÷ (TP + FP): of the columns the app labeled with this class, how many were right.
        Recall = TP ÷ (TP + FN): of the columns that really are this class, how many the app found.
      </p>
    </section>
  )
}

function MistakesList({ mistakes }) {
  const [page, setPage] = useState(0)
  const pageCount = Math.max(1, Math.ceil(mistakes.length / MISTAKES_PER_PAGE))
  const first = page * MISTAKES_PER_PAGE
  const shown = mistakes.slice(first, first + MISTAKES_PER_PAGE)
  const headers = ['File', 'Column', 'App said', 'Correct answer', 'Type', "App's reason"]

  return (
    <section className="overflow-hidden rounded-xl border border-[#E3E6EB] bg-white">
      <div className="flex flex-wrap items-baseline gap-3 border-b border-[#E3E6EB] px-5 py-4">
        <h2 className="text-base font-semibold">Mistakes</h2>
        <span className="text-sm text-[#5B6270]">
          {mistakes.length === 0
            ? 'none'
            : `${mistakes.length} column${mistakes.length === 1 ? '' : 's'} · showing ${first + 1}–${first + shown.length}`}
        </span>
      </div>
      {mistakes.length === 0 ? (
        <p className="px-5 py-4 text-sm text-[#3A404C]">
          Every column matches its correct answer: 0 false positives (FP) and 0 false negatives (FN).
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1040px] border-collapse text-left text-sm">
              <thead className="bg-[#F7F8FA] text-xs font-semibold tracking-wide text-[#4A5160] uppercase">
                <tr>
                  {headers.map((header) => (
                    <th key={header} scope="col" className="px-5 py-3 font-semibold">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="align-top">
                {shown.map((mistake) => (
                  <tr key={mistake.column} className="border-t border-[#EEF0F3]">
                    <td className="w-[200px] px-5 py-3.5 font-mono text-xs wrap-break-word">{mistake.file}</td>
                    <th scope="row" className="w-[140px] px-5 py-3.5 text-left font-mono text-[13px] font-normal wrap-break-word">{mistake.column}</th>
                    <td className="w-[140px] px-5 py-3.5">{mistake.app_said}</td>
                    <td className="w-[140px] px-5 py-3.5">{mistake.correct_class}</td>
                    <td className="px-5 py-3.5 font-semibold whitespace-nowrap">
                      {mistake.types.map((type) => <div key={type}>{type}</div>)}
                    </td>
                    <td className="px-5 py-3.5 leading-normal text-[#3A404C]">{mistake.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pageCount > 1 && <Pagination page={page} pageCount={pageCount} onChange={setPage} label="Mistakes pages" />}
        </>
      )}
    </section>
  )
}

// The test CSV is not uploaded here: it is the file last classified on the
// Classifier tab (testFile, passed in by App), so it never has to be chosen twice.
export default function TestResultsPage({ testFile }) {
  const [answersFile, setAnswersFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null) // { message, problems }
  const [result, setResult] = useState(null)

  // A new file on the Classifier tab makes the old results out of date, so they are cleared.
  useEffect(() => {
    setResult(null)
    setError(null)
  }, [testFile])

  // A new answers file makes the old results out of date too.
  function chooseAnswersFile(file) {
    setAnswersFile(file)
    setResult(null)
    setError(null)
  }

  async function runTests() {
    if (testFile.size + answersFile.size > MAX_UPLOAD_BYTES) {
      setError({ message: 'The two files together are larger than about 4.5 MB, the upload limit.', problems: [] })
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const form = new FormData()
      form.append('file', testFile)
      form.append('answers', answersFile)
      const response = await fetch('/api/evaluate', { method: 'POST', body: form })
      const data = await response.json().catch(() => ({ error: `The server answered with status ${response.status}.` }))
      if (!response.ok) {
        setError({ message: data.error || 'Something went wrong.', problems: data.problems || [] })
        return
      }
      // Only show results that have the expected shape. Anything else (for example an
      // outdated local server answering with Classifier results) becomes a readable error.
      if (!Array.isArray(data.classes) || !Array.isArray(data.mistakes)) {
        setError({
          message: 'The server sent an unexpected answer, so the test results cannot be shown.',
          problems: ['If you are running the app locally, stop the Python server and start it again with: python3 dev_server.py'],
        })
        return
      }
      setResult(data)
    } catch (err) {
      setError({ message: err.message || 'Could not reach the classifier.', problems: [] })
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader page="tests">
        <button type="button" onClick={runTests} disabled={!testFile || !answersFile || loading}
          className={primaryButton}>
          {loading ? 'Running tests…' : 'Run tests'}
        </button>
      </PageHeader>

      <main className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex min-w-0 flex-col gap-1.5">
            <h1 className="text-[22px] font-bold">Test results</h1>
            <p className="text-sm text-[#5B6270] wrap-anywhere">
              {result
                ? `${result.file_name} · ${result.column_count} columns tested · every column compared with its correct answer.`
                : 'Upload an answers CSV for the file on the Classifier tab, then click Run tests. Nothing is stored.'}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="flex min-w-0 flex-col gap-1">
              <span className="text-xs font-semibold text-[#4A5160]">Test CSV (from the Classifier tab)</span>
              {testFile ? (
                <span title={testFile.name}
                  className="flex min-h-11 max-w-56 items-center truncate font-mono text-sm">
                  {testFile.name}
                </span>
              ) : (
                <a href="#/" className={`flex min-h-11 items-center rounded text-sm font-semibold text-[#2F5BD3] underline hover:text-[#1F3F9E] ${focusRing}`}>
                  Upload a file on the Classifier tab first
                </a>
              )}
            </div>
            <FilePicker id="answers-file" label="Answers CSV" file={answersFile} onChange={chooseAnswersFile} disabled={loading} />
          </div>
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-[#F1C6C6] bg-[#FDF2F2] px-4 py-3 text-sm text-[#8A1C1C]">
            <p className="font-semibold">{error.message}</p>
            {error.problems.length > 0 && (
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {error.problems.map((problem) => <li key={problem}>{problem}</li>)}
              </ul>
            )}
          </div>
        )}

        {result && (
          <>
            <ByClassTable classes={result.classes} />
            <MistakesList key={result.file_name + result.mistakes.length} mistakes={result.mistakes} />
          </>
        )}
      </main>
    </>
  )
}
