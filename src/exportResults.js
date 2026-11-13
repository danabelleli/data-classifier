// Builds and downloads <original name>_results.csv with one row per column.

// Quote a value for CSV: wrap it in double quotes and double any quotes inside.
// Values starting with = + - @ get a leading apostrophe so spreadsheet apps
// show them as text instead of running them as formulas (column names come
// from the uploaded file, so they are untrusted).
function csvCell(value) {
  let text = value === null || value === undefined ? '' : String(value)
  if (/^[=+\-@]/.test(text)) text = `'${text}`
  return `"${text.replace(/"/g, '""')}"`
}

export function resultsFileName(fileName) {
  return `${fileName.replace(/\.csv$/i, '')}_results.csv`
}

export function downloadResults(result) {
  const header = ['column', 'data_class', 'match_percent', 'reason']
  const rows = result.columns.map((column) => [
    column.name,
    column.data_class ?? 'Not classified',
    column.match_percent ?? '',
    column.reason,
  ])
  const csv = [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n')

  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = resultsFileName(result.file_name)
  link.click()
  URL.revokeObjectURL(url)
}
