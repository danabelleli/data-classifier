import { useRef, useState } from 'react'
import { downloadResults } from './exportResults.js'
import { ClassTag, MAX_UPLOAD_BYTES, PageHeader, focusRing, primaryButton, secondaryButton } from './ui.jsx'

function Header({ result, loading, onUploadClick }) {
  const sensitive = result ? result.columns.filter((c) => c.data_class).length : 0
  return (
    <PageHeader page="classifier">
      {result && (
        <span className="rounded-lg bg-[#F1F3F6] px-3.5 py-2.5 text-sm wrap-anywhere">
          {result.file_name} · {sensitive} sensitive of {result.column_count} columns
        </span>
      )}
      <button type="button" onClick={onUploadClick} disabled={loading} className={`${primaryButton} disabled:cursor-wait`}>
        {loading ? 'Classifying…' : 'Upload CSV'}
      </button>
      <button type="button" onClick={() => downloadResults(result)} disabled={!result} className={secondaryButton}>
        Export results
      </button>
    </PageHeader>
  )
}

function ColumnList({ columns, selected, onSelect }) {
  return (
    <nav aria-label="Columns"
      className="flex max-h-80 w-full flex-col gap-0.5 overflow-y-auto rounded-xl border border-[#E3E6EB] bg-white p-2 md:sticky md:top-4 md:max-h-[calc(100vh-2rem)] md:w-80 md:shrink-0 md:overflow-y-auto">
      <h2 className="px-3 pt-2.5 pb-1.5 text-xs font-semibold tracking-wide text-[#4A5160] uppercase">Columns</h2>
      {columns.map((column, index) => {
        const isSelected = index === selected
        return (
          <button key={index} type="button" onClick={() => onSelect(index)} aria-current={isSelected ? 'true' : undefined}
            className={`flex min-h-11 cursor-pointer items-center justify-between gap-2.5 rounded-lg border-[1.5px] px-3 py-2 text-left ${focusRing} ${
              isSelected ? 'border-[#2F5BD3] bg-[#F1F4FB]' : 'border-transparent hover:bg-[#F7F8FA]'}`}>
            <span className={`min-w-0 font-mono text-[13px] break-all ${isSelected ? 'font-semibold' : ''}`}>{column.name}</span>
            <ClassTag dataClass={column.data_class} />
          </button>
        )
      })}
    </nav>
  )
}

function ColumnDetail({ column, rowCount }) {
  const hasPercent = column.match_percent !== null
  return (
    <section aria-label={`Details for column ${column.name}`} className="flex min-w-0 flex-1 flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-[#E3E6EB] bg-white p-6">
        <div className="flex min-w-0 flex-col gap-2">
          <span className="text-[13px] text-[#5B6270]">Column</span>
          <h1 className="font-mono text-2xl font-semibold break-all">{column.name}</h1>
          <ClassTag dataClass={column.data_class} large />
        </div>
        <div className="text-right">
          <div className="text-4xl font-bold tabular-nums">{hasPercent ? `${column.match_percent}%` : '—'}</div>
          <div className="text-[13px] text-[#5B6270]">
            {hasPercent ? 'of non-empty values match' : 'no class matched enough values'}
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-[#E3E6EB] bg-white">
        <h2 className="border-b border-[#E3E6EB] px-5 py-4 text-base font-semibold">Why</h2>
        <p className="px-5 py-4 text-sm leading-relaxed text-[#3A404C]">{column.reason}</p>
        <dl>
          {column.evidence.map((row) => (
            <div key={row.label}
              className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 border-t border-[#EEF0F3] px-5 py-3.5 text-sm sm:grid-cols-[130px_90px_minmax(0,1fr)]">
              <dt className="font-semibold text-[#4A5160]">{row.label}</dt>
              <dd className={`font-semibold ${row.status === 'Yes' ? 'text-[#1F3F9E]' : 'text-[#4A5160]'}`}>{row.status}</dd>
              <dd className="col-span-2 leading-normal text-[#3A404C] sm:col-span-1">{row.text || '—'}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="overflow-hidden rounded-xl border border-[#E3E6EB] bg-white">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[#E3E6EB] px-5 py-4">
          <h2 className="text-base font-semibold">Values</h2>
          <span className="text-[13px] text-[#5B6270]">
            {column.checked_class && !column.data_class ? `Checked against ${column.checked_class} · ` : ''}
            {column.values.length < rowCount
              ? `First ${column.values.length} of ${rowCount.toLocaleString()} rows`
              : `${rowCount} rows`}
          </span>
        </div>
        <ul>
          {column.values.map((item, index) => (
            <li key={index} className="flex flex-wrap justify-between gap-3 border-t border-[#EEF0F3] px-5 py-3 text-sm first:border-t-0">
              <span className={`min-w-0 font-mono text-[13px] break-all ${item.result === 'Empty' ? 'text-[#5B6270]' : ''}`}>{item.value}</span>
              <span className="text-[#4A5160]">{item.result}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

function EmptyState({ onUploadClick, loading }) {
  return (
    <div className="mx-auto mt-8 flex max-w-xl flex-col items-center gap-4 rounded-xl border border-[#E3E6EB] bg-white p-8 text-center">
      <h1 className="text-xl font-semibold">Find sensitive data in a CSV file</h1>
      <p className="text-sm leading-relaxed text-[#4A5160]">
        Each column is checked for six kinds of data: National ID (SSN), City, Person Name, Phone Number,
        Email Address and Date of Birth. Every decision comes with a plain-English reason.
      </p>
      <button type="button" onClick={onUploadClick} disabled={loading}
        className={`${primaryButton} px-5 disabled:cursor-wait`}>
        {loading ? 'Classifying…' : 'Upload CSV'}
      </button>
      <p className="text-xs text-[#5B6270]">Up to about 4.5 MB. The first 10,000 rows are analyzed.</p>
    </div>
  )
}

// onClassified(file) tells App which file was classified, so the Test results tab can reuse it.
export default function ClassifierPage({ onClassified }) {
  const fileInput = useRef(null)
  const [result, setResult] = useState(null)
  const [selected, setSelected] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleFile(event) {
    const file = event.target.files[0]
    event.target.value = '' // allow choosing the same file again
    if (!file) return
    if (file.size > MAX_UPLOAD_BYTES) {
      setError('This file is larger than about 4.5 MB, the upload limit. Try a smaller file.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const response = await fetch('/api/classify', { method: 'POST', body: form })
      const data = await response.json().catch(() => ({ error: `The server answered with status ${response.status}.` }))
      if (!response.ok) throw new Error(data.error || 'Something went wrong.')
      setResult(data)
      onClassified(file)
      setSelected(0)
    } catch (err) {
      setError(err.message || 'Could not reach the classifier.')
    } finally {
      setLoading(false)
    }
  }

  const openPicker = () => fileInput.current.click()

  return (
    <>
      <Header result={result} loading={loading} onUploadClick={openPicker} />
      <input ref={fileInput} type="file" accept=".csv,text/csv" onChange={handleFile} className="sr-only" tabIndex={-1} aria-hidden="true" />

      <main className="mx-auto max-w-[1200px] px-4 py-6 sm:px-8 sm:py-8">
        {error && (
          <p role="alert" className="mb-4 rounded-lg border border-[#F1C6C6] bg-[#FDF2F2] px-4 py-3 text-sm text-[#8A1C1C]">
            {error}
          </p>
        )}
        {!result && <EmptyState onUploadClick={openPicker} loading={loading} />}
        {result && result.columns.length > 0 && (
          <div className="flex flex-col items-start gap-6 md:flex-row">
            <ColumnList columns={result.columns} selected={selected} onSelect={setSelected} />
            <ColumnDetail column={result.columns[selected]} rowCount={result.row_count} />
          </div>
        )}
      </main>
    </>
  )
}
