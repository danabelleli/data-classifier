# Sensitive Data Classifier

A web app that reads a CSV file and decides, for each column, whether it contains one of six sensitive data classes, and explains why.

**Live app:** https://data-classifier-kappa.vercel.app

The six classes: **National ID (US SSN)** · **City** · **Person Name** · **Phone Number** · **Email Address** · **Date of Birth**. Any other column is **Not classified**.

Every decision is made by explainable rules: regular expressions, validation, and official reference lists. No machine learning and no LLM calls.

## How to use

**Classifier tab**
1. Click **Upload CSV** and choose a file.
2. The column list shows each column's class (blue tag) or "Not classified".
3. Click a column to see the match %, **why** (values, header, other columns), and the column's values with their results, 10 per page.
4. **Export results** downloads a CSV with each column's class, match % and reason.

**Test results tab** (measures quality)
1. Upload a test CSV in the Classifier tab.
2. In Test results, upload an answers CSV with the correct class for each column:
   `column,correct_class` (for example `full_name,Person Name` or `title,Not classified`)
3. Click **Run tests** to see true positives, false positives, false negatives, precision and recall per class, plus every mistake with the app's reason.

**Limits:** uploads up to about 4.5 MB (Vercel); the first 10,000 rows are analyzed. The value list shows up to 1,000 values per column (fewer for very wide files, to stay under Vercel's response limit); the label always shows how many are shown out of the total. Uploaded files are processed in memory and never saved. Files can be comma, semicolon, tab or pipe separated.

**Run locally (optional):** `npm install`, then `python3 dev_server.py` and `npm run dev` in two terminals, and open http://localhost:5173.

**Command line:** from the project folder, run `python3 classify.py <path to a CSV file>` (for example `python3 classify.py ~/Downloads/sample_employees.csv`). The path can point to any CSV on your computer. It prints each column's class and reason; add `--json` for JSON.

## Approach

- **Values are the main evidence.** Each non-empty value is checked against each class. A class needs **90%** of values to match (10+ values) or **80%** (1–9 values).
- **Supporting evidence lowers the bar to 50%, but never replaces values.** It always comes from the column itself: a header keyword, or a related column (email, city/state).
- **Ambiguous values need supporting evidence.** Raw digits, single words, city names and dates can look like many things, so they only count with a matching header or related column.
- **Every decision has a reason** with counts, a percentage, and the evidence used.

**Global rules**
- Placeholders (`N/A`, `NA`, `null`, `none`, `unknown`, `-`) and blanks are treated as empty.
- Headers are split into words (`employee_ssn`, `employeeSSN` → `employee`, `ssn`) before matching keywords.
- If two classes pass: the highest % wins; within 5 points, the one with a header match wins; then SSN > Phone > Email > Date of Birth > Person Name > City.

## The rules for each class

### Email Address
- The whole value must look like an email: `name@domain.tld`.
- Header keywords: `email`, `e-mail`, `mail`.

### National ID (US SSN)
- 9 digits in a 3-2-4 pattern: `123-45-6789`, `123 45 6789`, `123456789`.
- Must pass SSA rules: never starts with `000`, `666` or `900`–`999`; never `00` in the middle; never `0000` at the end.
- Formatted values (dashes or spaces) count on their own.
- Raw 9 digits count only with an SSN header.
- SSNs can start with 0 or 00, and spreadsheets drop those zeros when SSNs are stored as numbers (7 or 8 digits left). With an SSN header, if at least 50% of values are already valid 9-digit SSNs, the zeros are added back and the normal validation applies.
- Header keywords: `ssn`, `social`, `social_security`, `national_id`, `tax_id`.

### Phone Number
- **US:** any common format (`(212) 555-0101`, `212-555-0101`, `212.555.0101`, `+1 212 555 0101`, `2125550101`).
  - Area code and exchange can't start with 0 or 1.
  - The area code must be on the official NANPA list (toll-free included).
- **International:** starts with `+`, has a country code on the official ITU list, and 8–15 digits in total. `+1` numbers follow the US rules.
- Formatted values count on their own. Raw digits count only with a phone header.
- Header keywords: `phone`, `mobile`, `cell`, `tel`, `telephone`, `contact_number`.

### Date of Birth
- **Is it a date?** Fits one of 10 formats (`1990-03-14`, `03/14/1990`, `14/03/1990`, `03/14/90`, `March 14, 1990`, …), is a real calendar date, not in the future, and not more than 120 years ago. Two-digit years that would land in the future go to the 1900s (`45` → 1945).
- **Is it a birth date?** One of:
  - the header has a birth keyword (`dob`, `birth`, `birthday`, `birth_date`, `date_of_birth`, `bday`, `born`); any age 0–120, so children's data counts; or
  - the file is about people (it has a Person Name or SSN column), has 2+ date columns, and this column holds the earliest date in 90%+ of rows, because a person is born before anything else happens to them.

### City
- A column of US state names or abbreviations is treated as a state column first (Not classified) and used for city/state pairs.
- Values are cleaned first: lowercase, `St.` → Saint, `Ft.` → Fort, `Mt.` → Mount, `Austin, TX` → Austin.
- A value is a city if it's a US place with 10,000+ people (Census), or a real city/state pair with the state column (any size).
- **Needs supporting evidence:** a header keyword (`city`, `town`, `municipality`, `locality`) or 50%+ of rows forming real city/state pairs.

### Person Name
- Values are cleaned first: titles (`Dr.`, `Mr.`) and suffixes (`Jr.`) removed, `Carter, Emily` → `Emily Carter`. 1–4 words, letters, hyphens and apostrophes only.
- **Full names:** the first word is in the SSA first-name list, **and** at least 50% of last words in the column are on the Census surname list (surnames shared by 1,000+ people).
- **Single words** (a first name or surname alone) count only with a name header or the email match.
- **Person evidence is required**, at least one of:
  - the file has an SSN column, a birth-date column (by header), or a `gender`/`sex` column;
  - the email match: a name word appears before the `@` of the email in the same row, in 50%+ of rows;
  - a person-name header: `first_name`, `last_name`, `full_name`, `surname`, `given_name`, `fname`, `lname`.

## Options I considered

| Decision | Options | What I chose and why |
|---|---|---|
| Value threshold | 95% · 90% | **90%** (80% for small columns), plus cleaning placeholders, so real columns with a few messy values still pass. |
| Role of the header | Block a class (e.g. `employee_id` blocks SSN) · Support only | **Support only.** Headers can be missing or misleading; values stay the main evidence. |
| Person Name method | Name shape first · First-name list first | **First-name list.** A shape rule calls job titles like "Data Analyst" names. |
| Area code check | Raw numbers only · Every value | **Every value.** Same validation for all formats, real area codes only. |
| Date of Birth | Age cutoff (e.g. 16–100) · Header + relations between columns | **Header + relations.** An age cutoff would miss children's birth dates (healthcare data). |
| Single-word names (`loyalty_tier`: Bronze, Silver, Gold) | Common names only · Count distinct values · Require support | **Require support** (name header or email match), the same rule as surnames. |
| City false positive (`collection` of product lines) | Bigger cities only · Count distinct values · Require support | **Require support.** The other two options wouldn't separate product lines from real cities. |
| Surname list size | 100+ · 1,000+ · 10,000+ people per surname | **1,000+:** 15% of the names but 77.3% of people. Drops word-like surnames (Table, Chair); 10,000+ would come too close to the 50% bar. |
| 3-value minimum per column | Keep · Strong formats only · Require support · Remove | **Remove.** Ambiguous cases already need support; the minimum only caused false negatives on small files. |
| Brand names in a name column (`merchant_name`: Kate Spade, Calvin Klein) | A hand-picked list of words before "name" · Person evidence | **Person evidence.** Brands and people can look identical inside the column; the difference is in the rest of the file. One-off cases are better handled with customer-specific tuning. |
| `national_id` as an SSN keyword | Remove · Keep | **Keep.** Removing it risks missing real SSNs under that header; the cost is labeling some non-US IDs as SSN. |

## What works well

Tested on 14 synthetic files (HR, e-commerce, travel, healthcare, data lake, contacts, transactions, product catalog, mortgage, global payroll, insurance claims, consumer app, bank), each with an answers file.

- Clear patterns are found even with meaningless headers (`col_1`, `col_7`).
- Mixed formats in one column (`(212) 555-0101` next to `+44 20 7946 0958`).
- Messy data: placeholders, ALL CAPS, extra spaces, a few typos.
- Traps handled: date-like codes (`2024-12-3100`), bank accounts with 9 digits, job titles, order IDs with a real area code, loyalty tiers, product lines named after cities, brand names, hire dates next to birth dates, tiny files.
- Every decision can be traced to specific values.

## Known limitations

| Class | Limitation |
|---|---|
| Email | Emails inside free text (a notes column) are not detected, by design. |
| SSN | Non-US 9-digit IDs (Israeli, Dutch) under a `national_id` header can be labeled SSN. Raw 9-digit SSNs without an SSN header are missed. SSNs that lost leading zeros are only recovered when the column has an SSN header and at least 50% of values are already valid 9-digit SSNs. |
| Phone | Raw digits without a phone header are missed. International numbers without `+` are missed. The area code and country code lists go out of date over time. Numbers with an extension (212-555-0101 x204, ext. 3) are not matched. |
| Date of Birth | A people file with `hire_date` and `termination_date` but no birth date: `hire_date` is the earliest, so it can be called Date of Birth. A single unlabeled birth-date column is missed. Dates with a time (`1990-03-14 00:00:00`) are missed. Dates with dots or no separators (14.03.1990, 19900314) are not recognized. |
| City | A city column with a vague header and no state column is missed. Non-US cities are not supported. Misspellings are missed. Nicknames and variants (NYC, New York City, SF) are not matched. |
| Person Name | Real names with a generic header (`customer_name`) and no person evidence are missed. In a file that has SSN, birth-date or gender columns, a name-shaped non-person column (brands) can still pass. Rare first names may be missing from the SSA list. Names longer than 4 words (Juan Carlos de la Cruz) are not matched. |
| State guard | A first-name column full of "Virginia" or "Georgia" would be treated as a state column. |
| Mixed columns | A column mixing two classes (emails and phones in one 'contact' column) usually reaches neither threshold and is Not classified. |

## Next steps with more time

- Separate classes for non-US national IDs, each with its own validation (for example the Israeli ID check digit).
- Credit card numbers (PCI), with the Luhn checksum.
- Matching misspelled cities.
- Test results across many labeled files at once, to measure precision and recall at scale.
- Customer-specific tuning: allowlists and custom keywords per customer, without changing the general rules.
