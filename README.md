# Sensitive Data Classifier

Upload a CSV file and see, for each column, whether it holds one of six kinds of sensitive data, with a plain-English reason for every decision.

The six classes are National ID (US Social Security Number), City, Person Name, Phone Number, Email Address and Date of Birth. A column that holds none of them is **Not classified**.

---

## 1. How to use it

**Live app:** https://data-classifier-kappa.vercel.app/

1. Click **Upload CSV** and choose a file.
2. The left list shows every column. Classified columns have a blue tag with their class.
3. Click a column to see the match percentage, **why** it was (or was not) classified, and its values with the result for each one.
4. Click **Export results** to download `<file name>_results.csv` (one row per column: `column`, `data_class`, `match_percent`, `reason`).

### Test results page (precision and recall)

The **Test results** tab measures how well the rules work on a file whose correct answers you know.

1. **Test CSV:** the file to test.
2. **Answers CSV:** the correct class for each column of the test CSV, written by a person:
   ```
   column,correct_class
   full_name,Person Name
   title,Not classified
   ```
   Class names must be exactly: National ID (SSN), City, Person Name, Phone Number, Email Address, Date of Birth, Not classified. Spaces around a name are ignored; capitalization must match.
3. Click **Run tests**. The test CSV is classified with exactly the same code as the Classifier page, then each column is compared with its correct answer. Nothing is stored.

If the files don't line up (a column with no answer, an answer for a column that isn't in the file, a column listed twice, or an unknown class name), the test does not run and every problem is listed, so the numbers are never based on a partial comparison.

For each of the 6 classes the page counts:
- **True positive (TP):** the app said this class and the correct answer is this class.
- **False positive (FP):** the app said this class, but the correct answer is something else.
- **False negative (FN):** the correct answer is this class, but the app said something else.
- **True negative (TN):** neither is this class.

A column given the wrong class (app says City, correct answer is Person Name) is an FP for City **and** an FN for Person Name.
**Precision = TP ÷ (TP + FP)**: of the columns the app labeled with this class, how many were right. **Recall = TP ÷ (TP + FN)**: of the columns that really are this class, how many the app found. When the denominator is 0, the page shows "—".
The **Mistakes** list shows every wrong column with the app's reason, 10 per page.

**Limits:** Vercel accepts uploads up to about **4.5 MB** per request. Only the first **10,000 rows** are analyzed. The UI lists the first 20 values of each column.

### Run it locally

You need Python 3.10+ and Node.js 18+.

```bash
npm install
python3 dev_server.py     # terminal 1: the Python API on http://localhost:8000
npm run dev               # terminal 2: the web app on http://localhost:5173
```

`dev_server.py` serves both API endpoints (`/api/classify` and `/api/evaluate`) and is only used locally. Vite forwards `/api` requests to it, so open http://localhost:5173 and upload a file. If you have the Vercel CLI, `vercel dev` runs both together the same way as in production.

### Deploy

Push the repo to GitHub and import it in Vercel (framework: Vite). The React app is served as static files from `dist/`. Each file in `api/` (`classify.py`, `evaluate.py`) becomes a Python serverless function. `vercel.json` makes sure the `classifier/` code and the `data/` reference lists are bundled with them. The Python code uses only the standard library, so there is no `requirements.txt`.

---

## 2. What the app does, and the approach

Every decision is made by rules that a person can read and check: regular expressions, validation rules and official reference lists. There is no machine learning and no AI model. The app works on any CSV without code changes, because it judges a column by its **contents**, not by its name.

- **Values are the main evidence.** Each non-empty value is tested against the rule for each class. A class must match a large share of values: **80%** for columns with 3–9 values, **90%** for 10 or more. Columns with fewer than 3 values are not classified (not enough data).
- **Supporting evidence lowers the bar to 50%, but never replaces values.** It comes from the column's **header** (for example `ssn`, `email`, `dob`) or from **related columns** in the same row: a city that forms a real city/state pair with a state column, or a name that appears inside the email address in that row.
- **Conflicts.** If more than one class passes, the highest percentage wins. If two are within 5 points, the one whose header matches wins. If still tied: SSN > Phone > Email > Date of Birth > Person Name > City. The reason names the runner-up.
- **Every result has a reason**, including Not classified columns. It gives the matched count, the non-empty count, the percentage, and which supporting evidence was used (or that none was).

Values are cleaned first: spaces are trimmed, and `N/A`, `NA`, `null`, `none`, `unknown`, `-` and blanks count as empty. Percentages use non-empty values only. Every value is read as text, so leading zeros (for example in SSNs) are kept.

Some classes depend on others, so the app runs two passes. **Pass 1** looks at each column alone: Email, SSN, Phone, state columns, and dates with a birth keyword in the header. **Pass 2** uses those results: City (paired with the state column), Person Name (compared with the email column), then birth dates found by position.

### Code layout

| Path | What it does |
|---|---|
| `api/classify.py` | Vercel function for the Classifier page: receives the upload, returns JSON |
| `api/evaluate.py` | Vercel function for the Test results page: receives the test CSV and answers CSV, returns the counts |
| `dev_server.py` | Local only: one server for both API endpoints |
| `classifier/cleaning.py` | Reads the CSV, trims values, handles placeholders like `N/A` |
| `classifier/headers.py` | Splits headers into words (`employeeSSN` → `employee`, `ssn`) and matches keywords |
| `classifier/rules_*.py` | One file per class with its value rule and header keywords |
| `classifier/decide.py` | Thresholds, the two passes, conflict resolution, reasons |
| `classifier/evaluate.py` | Test results: checks the answers CSV, compares, counts TP/FP/FN/TN, precision and recall |
| `classifier/upload.py` | Reads uploaded files from a request and sends JSON (shared by both endpoints) |
| `data/` | Official reference lists ([sources](data/README.md)) |
| `scripts/build_reference_data.py` | Rebuilds `data/` from the raw official downloads |
| `src/` | React + Vite + Tailwind web app |
| `tests/files/` | Test CSV files |

---

## 3. The rules for each class

### Email Address
The whole value must look like an email: `name@domain.tld` (letters, digits and `. _ % + -` before the `@`, a domain, and a 2+ letter ending).
Header keywords: `email`, `e-mail`, `mail`.

### National ID (US Social Security Number)
Nine digits in a 3-2-4 pattern, written with dashes, spaces or no separators (`123-45-6789`, `123 45 6789`, `123456789`). They must also pass the SSA's rules: never starting with `000`, `666` or `900`–`999`, never `00` in the middle, never `0000` at the end. The reason says how many values used each separator style.
Header keywords: `ssn`, `social`, `social_security`, `national_id`. A header like `employee_id` does **not** block SSN.

### Phone Number (US only)
A US phone number in any common format, such as `(212) 555-0101`, `212-555-0101`, `212.555.0101`, `2125550101`, `+1 212 555 0101`, `1-212-555-0101`. The area code and exchange cannot start with 0 or 1. The area code must be a real, in-service US area code from the NANPA list (toll-free codes included). The reason names the most common area code and its region ("212 = New York").
Header keywords: `phone`, `mobile`, `cell`, `tel`, `telephone`, `contact_number`.

### Date of Birth
**Step 1: is it a date?** A value is a valid date if it fits one of 10 formats (`1990-03-14`, `1990/03/14`, `03/14/1990`, `14/03/1990`, `03-14-1990`, `03/14/90`, `14/03/90`, `March 14, 1990`, `Mar 14, 1990`, `14-Mar-1990`), is a real calendar date (no Feb 30), is not in the future, and is not more than 120 years ago. Two-digit years that would land in the future go to the 1900s (`45` → 1945).

**Step 2: is it a birth date?** A date column is Date of Birth if either:
- its header has a birth keyword (`dob`, `birth`, `birthday`, `birth_date`, `date_of_birth`, `bday`, `born`); any age 0–120 is accepted; **or**
- the file is about people (it has a Person Name or SSN column), it has 2+ date columns, and this column holds the **earliest** date in at least 90% of rows, because a person is born before anything else happens to them.

Otherwise the column is Not classified, and the reason says the values are dates but nothing shows they are birth dates.

### City (US only)
First the app checks for a **state column**: if the values are US state names or abbreviations, the column is Not classified (State is not one of the six classes). It is remembered for the city check.

A value is a city if it is a US place with 10,000+ people in the Census list, **or** it forms a real (city, state) pair with the state column in the same row (any population, so small towns count). Names are normalized first: lowercase, `St.` → Saint, `Ft.` → Fort, `Mt.` → Mount, and a trailing `, TX` or `, Texas` is removed and used as the state.
Supporting evidence: header keywords `city`, `town`, `municipality`, `locality`; or 50%+ of rows forming real city/state pairs.

### Person Name
Names are normalized first: titles (`Mr`, `Mrs`, `Ms`, `Dr`, `Prof`) and suffixes (`Jr`, `Sr`, `II`, `III`, `IV`) are removed, and `Carter, Emily` becomes `Emily Carter`. A name has 1–4 words made of letters, hyphens and apostrophes (`O'Brien`, `Smith-Jones`), plus optional initials like `J.`. No digits.
- **Full name** (2–4 words): the first word must be in the SSA first-name list.
- **First name only**: the word is in the SSA first-name list.
- **Surname only**: the word is in the Census surname list. This only counts with support (a name header, names matching the email column, or another column with SSN, email, phone or date of birth), because the surname list contains ordinary words like Brown, White, Green and King.

Supporting evidence: header keywords `name`, `full_name`, `first_name`, `last_name`, `surname`, `given_name`, `fname`, `lname` and anything like `employee_name`; or a word of the name appearing before the `@` of the email in the same row in 50%+ of rows.

---

## 4. Other options considered

| Option | Why it was not chosen |
|---|---|
| Machine learning or named-entity recognition (spaCy, Microsoft Presidio) | Decisions cannot be explained as a simple rule, and results change between model versions. The brief requires every decision to be explainable. |
| An LLM call per column | Not explainable or repeatable, slow and costly, and it sends sensitive data to a third party. |
| Classifying by header only | Headers are often missing, abbreviated or misleading (`field_12`). Values are the real evidence; the header only helps. |
| pandas to read the file | It converts values to numbers (`012345678` loses its leading zero) and is a large dependency for a serverless function. Python's `csv` module keeps everything as text. |
| `dateutil` or other "smart" date parsers | Too forgiving: they accept almost any string with digits. A fixed list of formats makes it clear what counts as a date. |
| `phonenumbers` (libphonenumber) | Excellent for international numbers, but the scope is US only, and an official NANPA list is easier to explain and to check. |
| Searching inside free text (emails in a notes column) | The app classifies what a column **is**. Finding sensitive data hidden in free text is a different problem (see Next steps). |
| A newer Census Gazetteer (2020+) | Newer editions have no population column, which the 10,000-people rule needs. |

---

## 5. What works well and what does not

**Works well**
- Columns whose values clearly follow a pattern (email, SSN, US phone, dates), even with a meaningless header like `col_7`.
- Mixed formats in one column (`(212) 555-0101` next to `2125550101`; `123-45-6789` next to `123456789`).
- Traps such as a date with a 10-digit look (`2024-12-3100`), a bank account containing 9 digits in a row, a job title shaped like a name, or a city that is also a first name (Austin).
- Clear explanations: every value shows its own result, so a surprising decision can be traced to specific rows.

**Known limitations**

| Class | Limitation |
|---|---|
| Email | Emails inside free text are not detected (by design). |
| SSN | **False positives (accepted on purpose):** about 89% of random 9-digit numbers pass validation, so a 9-digit ID column without dashes can be classified as SSN. Missing a real SSN is worse than a false alarm. **False negatives:** SSNs saved as numbers that lost a leading zero (8 digits). |
| Phone | US only; international numbers are not supported. The area code list goes out of date as new codes are added. Made-up area codes in test data do not match (by design). |
| Date of Birth | **False positive:** a people file with `hire_date` and `termination_date` but no birth date column: `hire_date` is the earliest date, so it is called Date of Birth. **False negatives:** a single unlabeled birth date column with no other date to compare with; dates stored with a time (`1990-03-14 00:00:00`). Ambiguous dates like `03/04/1990` are read month-first when comparing columns. |
| City | US only. Misspellings are missed. Small towns (under 10,000 people) are only found when the file has a state column or the value includes the state. Places that grew past 10,000 after the 2010 Census need a state too. The Census name for some places differs from common use ("Boise City" for Boise). |
| State guard | A column that is mostly state names is treated as a state column first, so a first-name column full of "Virginia" and "Georgia" would be Not classified. |
| Person Name | Rare or international first names may be missing from the SSA list. The SSA list includes some ordinary words that were given as names, so a column of word pairs can occasionally pass. Names overlap with cities (handled by conflict resolution). |

---

## 6. Next steps with more time

- Automated tests in `tests/` for every rule and every trap, run on each change.
- A confidence level next to each result (for example, a 100% match with header and related-column support versus a 91% match with nothing else).
- Larger files: upload directly to storage instead of through the function, to go past 4.5 MB and 10,000 rows.
- More countries: international phone numbers, other national IDs (Canadian SIN, UK National Insurance number), and world cities.
- Recover SSNs that lost a leading zero when there is strong supporting evidence.
- Accept dates with a midnight time (`1990-03-14 00:00:00`).
- Use name frequency from the SSA data to give less weight to very rare names that are also ordinary words.
- Report sensitive data inside free-text columns as a separate warning, without changing the column's class.
- Let the user correct a decision in the UI and export the corrected result.
