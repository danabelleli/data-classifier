// Small pieces shared by both pages: the header with tabs, the class tag, button styles.

export const focusRing =
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2F5BD3]'

export const primaryButton =
  `min-h-11 cursor-pointer rounded-lg bg-[#2F5BD3] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#244AB0] disabled:cursor-not-allowed disabled:bg-[#9AA6C4] ${focusRing}`

export const secondaryButton =
  `min-h-11 cursor-pointer rounded-lg border border-[#C9CED6] bg-white px-4 py-2.5 text-sm font-semibold text-[#16181D] hover:bg-[#F1F3F6] disabled:cursor-not-allowed disabled:text-[#6B7280] disabled:hover:bg-white ${focusRing}`

export const MAX_UPLOAD_BYTES = 4.5 * 1024 * 1024 // Vercel's request size limit

function ShieldIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2F5BD3" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6l8-3z" />
    </svg>
  )
}

export const PAGES = [
  { id: 'classifier', label: 'Classifier', href: '#/' },
  { id: 'tests', label: 'Test results', href: '#/tests' },
]

// The header bar: app name, the two page tabs, and the current page's buttons (children).
export function PageHeader({ page, children }) {
  return (
    <header className="border-b border-[#E3E6EB] bg-white">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-8">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <div className="flex items-center gap-2.5">
            <ShieldIcon />
            <span className="text-[17px] font-semibold">Sensitive Data Classifier</span>
          </div>
          <nav aria-label="Pages" className="flex gap-1">
            {PAGES.map((item) => (
              <a key={item.id} href={item.href} aria-current={item.id === page ? 'page' : undefined}
                className={`rounded-lg px-3.5 py-3 text-sm no-underline ${focusRing} ${
                  item.id === page ? 'bg-[#E8EEFC] font-semibold text-[#1F3F9E]' : 'text-[#4A5160] hover:bg-[#F1F3F6]'}`}>
                {item.label}
              </a>
            ))}
          </nav>
        </div>
        <div className="flex flex-wrap items-center gap-3">{children}</div>
      </div>
    </header>
  )
}

// The light-blue class tag, or gray "Not classified".
export function ClassTag({ dataClass, large = false }) {
  const size = large ? 'text-sm px-3 py-1' : 'text-xs px-2.5 py-0.5'
  if (!dataClass) {
    return large ? (
      <span className={`${size} self-start rounded-full bg-[#EEF0F3] text-[#4A5160]`}>Not classified</span>
    ) : (
      <span className="whitespace-nowrap text-xs text-[#5B6270]">Not classified</span>
    )
  }
  return (
    <span className={`${size} self-start whitespace-nowrap rounded-full bg-[#E1E8FB] font-semibold text-[#1F3F9E]`}>
      {dataClass}
    </span>
  )
}
