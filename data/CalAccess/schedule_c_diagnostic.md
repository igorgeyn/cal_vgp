# Schedule C (in-kind) attribution diagnostic

Run 2026-05-13 from current v3 dump. Filters applied:
- FORM_TYPE = 'C' (Schedule C non-monetary)
- Latest AMEND_ID per FILING_ID
- MEMO_CODE blank
- AMOUNT parseable + > 0
- RCPT_DATE parseable

## Bucket totals

| Bucket | Rows | Dollar amount |
|---|---|---|
| `accepted` | 14,452 | $242,550,215.67 |
| `no_cover_sheet` | 122,904 | $434,698,810.36 |
| `no_campaign_match` | 120 | $8,184,607.87 |
| `bad_prop_or_year` | 13,526 | $208,496,605.11 |
| `unknown_stance` | 14 | $642,708.72 |

## Top 25 filers in `accepted`

| Filer | Dollar amount |
|---|---|
| Californians for Affordable Prescriptions - Yes on Proposition 78 sponsored by P | $27,498,345.56 |
| Prop38yes.com, School Vouchers 2000 | $20,470,829.63 |
| Small Business Action Committee PAC, No on 30/Yes on 32, citizens for reforming  | $20,074,765.00 |
| No on 75, educators, firefighters, school employees, health care givers and labo | $10,998,658.64 |
| YES ON 22 - SAVE APP-BASED JOBS & SERVICES: A COALITION OF ON-DEMAND DRIVERS AND | $9,826,018.46 |
| No on 76, educators, firefighters, school employees, health care givers and labo | $9,454,970.69 |
| YES ON 20, NO ON 27 - HOLD POLITICIANS ACCOUNTABLE | $8,611,031.83 |
| No on 32, Stop corporate special exemptions from campaign finance rules, sponsor | $8,170,790.95 |
| Yes on 71: Coalition for Stem Cell Research and Cures | $8,101,837.99 |
| No on 30 | $7,268,960.40 |
| No on Prop. 48 - Keep Vegas-Style Casinos Out of Neighborhoods, a project of Sta | $6,440,672.53 |
| YES ON 14: CALIFORNIANS FOR STEM CELL RESEARCH, TREATMENTS AND CURES | $6,048,084.83 |
| Yes on 50, The Election Rigging Response Act, Governor Newsom?s Ballot Measure C | $4,909,912.74 |
| No on 38 A Coalition of Parents Educators Business Labor and Public Safety | $4,463,139.86 |
| YES ON 1A CALIFORNIANS FOR INDIAN SELF-RELIANCE SPONSORED BY CALIFORNIA INDIAN T | $4,166,718.77 |
| NO ON 86 - STOP THE $2 BILLION TAX HIKE, A COALITION OF BUSINESS, LAW ENFORCEMEN | $4,015,854.58 |
| Yes on Prop. 30--to Protect our Schools and Public Safety, a broad coalition of  | $3,649,050.16 |
| YES ON 54 - VOTERS FIRST, NOT SPECIAL INTERESTS - SPONSORED BY HOLD POLITICIANS  | $3,646,880.20 |
| Yes on Prop. 30--to Protect our Schools and Public Safety, a broad coalition of  | $3,467,367.00 |
| Yes on 52. Californians for Election Day Voter Registration | $2,849,080.27 |
| No on Prop.35-A Coalition of engineers peace officers firefighters taxpayers pub | $2,837,759.41 |
| No on 74, Teachers and School Board Members for Quality Education | $2,317,427.30 |
| LETS FIX OUR SCHOOLS/YES ON 26 A COALITION OF PARENTS TEACHERS BUSINESS AND LABO | $1,979,709.88 |
| NO ON 29 - CALIFORNIANS AGAINST OUT-OF-CONTROL TAXES AND SPENDING. MAJOR FUNDING | $1,886,482.30 |
| NO ON 56 - STOP THE SPECIAL INTEREST TAX GRAB. MAJOR FUNDING BY PHILIP MORRIS US | $1,595,006.99 |

## Top 25 filers in `no_cover_sheet`

| Filer | Dollar amount |
|---|---|
| (no cover sheet) | $434,698,810.36 |

## Top 25 filers in `no_campaign_match`

| Filer | Dollar amount |
|---|---|
| PROTECT PROP. 13, A PROJECT OF THE HOWARD JARVIS TAXPAYERS ASSOCIATION | $7,841,181.77 |
| Life on the Ballot | $107,981.88 |
| COMMITTEE FOR CLEAN WATER NATURAL RESOURCES AND PARKS, YES ON PROPOSITION 68 | $83,774.29 |
| Yes on Proposition 68 - Californians for Clean Water and Safe Parks, Sponsored b | $79,692.48 |
| CALIFORNIANS FOR PARENTAL RIGHTS FUND | $23,254.92 |
| COMMITTEE FOR CLEAN WATER NATURAL RESOURCES AND PARKS | $20,594.19 |
| Coalition to Protect Local Transportation Improvements, Yes on Prop. 69, sponsor | $15,000.00 |
| Protect Climate Funds and Stop Prop 70, CEJA Action Committee, a project of Tide | $6,791.09 |
| California Faculty Association Political Issues Committee | $5,537.25 |
| VETO GUNMAGEDDON | $800.00 |

## Top 25 filers in `bad_prop_or_year`

| Filer | Dollar amount |
|---|---|
| YES ON 14: CALIFORNIANS FOR STEM CELL RESEARCH, TREATMENTS AND CURES | $14,871,714.24 |
| Californians for Financial Education | $7,628,781.67 |
| TAXPAYERS FOR ACCOUNTABILITY & BETTER SCHOOLS(TABS) YES ON PROP. 39A COALTN. OF  | $7,595,719.39 |
| Californians for Affordable Prescriptions - Yes on Proposition 78 sponsored by P | $7,265,968.35 |
| HOLD POLITICIANS ACCOUNTABLE | $6,610,625.00 |
| LETS FIX OUR SCHOOLS/YES ON 26 A COALITION OF PARENTS TEACHERS BUSINESS AND LABO | $6,032,184.07 |
| No on 75, educators, firefighters, school employees, health care givers and labo | $5,385,424.76 |
| PROTECT PROP. 13, A PROJECT OF THE HOWARD JARVIS TAXPAYERS ASSOCIATION | $4,863,210.09 |
| YES ON 70, MAJOR FUNDING BY AGUA CALIENTE BAND OF CAHUILLA INDIANS, SAN MANUEL B | $4,570,895.41 |
| Yes on 24, Californians for Consumer Privacy | $4,454,482.76 |
| TAXPAYERS FOR ACCOUNTABILITY & BETTER SCHOOLS(TABS), YES ON PROP. 39,A COALTN. O | $4,220,295.17 |
| Stop the Republican Recall of Governor Newsom | $4,010,038.67 |
| No on 74, Teachers and School Board Members for Quality Education | $4,009,413.55 |
| No on 68 & 70 - Governor Schwarzenegger's Committee For Fair Share Gaming Agreem | $3,271,201.68 |
| Citizens for Paycheck Protection, sponsored by Pharmaceutical Research and Manuf | $3,203,575.09 |
| No on 32, Stop corporate special exemptions from campaign finance rules, sponsor | $3,117,442.16 |
| VOTERS FIRST ACT FOR CONGRESS | $3,100,241.99 |
| Californians for Voter ID | $3,051,645.82 |
| Small Business Action Committee PAC, No on 30/Yes on 32, citizens for reforming  | $3,000,235.00 |
| YES ON 88: TAXPAYERS FOR BETTER SCHOOLS AND SMALLER CLASSES, SPONSORED BY EDVOIC | $2,960,000.00 |
| California Patriot Coalition - Recall Governor Gavin Newsom | $2,698,740.02 |
| No on 42. A coalition of teachers and service employees who oppose diverting fun | $2,652,000.00 |
| YES ON 22 - SAVE APP-BASED JOBS & SERVICES: A COALITION OF ON-DEMAND DRIVERS AND | $2,519,087.08 |
| CALIFORNIANS AGAINST THE WRONG PRESCRIPTION - NO ON PROPOSITION 79 SPONSORED BY  | $2,442,701.53 |
| No on 76, educators, firefighters, school employees, health care givers and labo | $2,290,865.78 |

## Top 25 filers in `unknown_stance`

| Filer | Dollar amount |
|---|---|
| Californians to Mend, Not End, The Death Penalty. No on Prop 62, Yes on Prop 66. | $642,708.72 |

## Top 20 unmatched (prop_num, election_year) by dollar volume
(Rows where prop_num + year extract but no v2 crosswalk entry)

| prop_num | year | dollars |
|---|---|---|
| 13 | 2026 | $7,841,181.77 |
| 68 | 2018 | $184,060.96 |
| 127 | 2006 | $57,621.88 |
| 127 | 2005 | $50,360.00 |
| 40 | 2016 | $23,254.92 |
| 69 | 2018 | $15,000.00 |
| 70 | 2018 | $6,791.09 |
| 1A | 2012 | $5,537.25 |
| 4 | 2016 | $800.00 |
