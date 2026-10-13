# Data profile: fibre availability and request status assistant

> Shape only. No real rows, addresses, identifiers, names or internal hostnames
> appear in this file. Every example value below is invented and follows the
> real pattern. Real system names are kept locally, not in this public repo.

**Source systems and owners:** six internal systems, read per lookup (not a batch feed)

| Source (generic name) | What it holds | Owner (role) |
| --- | --- | --- |
| Address register | Every building: building ID, settlement, street, house number, suffix | Data warehouse team |
| FTTH coverage forecast | Fibre status per building, project, technical acceptance date, network activation date, regulatory zone, acquisition status, number of apartments and customer units | Data warehouse team (dataset currently in a personal working schema) |
| Work-order system (regular requests) | Open customer requests: request ID, current task, task status, submit dates, location code, request type flag | Data warehouse team |
| Mini-project view | Open mini construction project requests, same shape as above | Data warehouse team |
| Field construction tracker | Progress of the cable to the building, technician notes, contractor, assigned PM / AM / programme manager / field lead; project status and notes | Field construction system owners |
| Responsibility matrix | Responsible person or team mailbox per location × process type × task column | FTTH operations |

Plus the **business rules**: a response template (task groups with expected
durations, regulatory stopwatch logic, responsibility rules, fallback contacts).
Owner: FTTH operations business owners.

**Classification and scope:** confidential. Work orders contain customer names,
request numbers and, in some records, national personal ID numbers. The field
tracker and the responsibility matrix contain employee names. Nothing is under
legal hold as far as known *(to confirm with the data owners)*.

**Arrives as:** SQL query results (one building per lookup) from a distributed
SQL engine over the data warehouse, plus a MySQL database for the field tracker.
Expected load: about 50 to 100 operator questions per working day (estimate).

## Schema (fields the product uses)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `building_id` (ADM ID) | integer | yes | Key across all sources; sometimes stored as string in one source, cast on join |
| `settlement`, `street`, `house_number` | string | yes | Street names in full official form, uppercase or mixed case |
| `suffix` | string | no | Letter or "/N" part of the house number; stored inconsistently (`/1`, `1`, `/01`, `B`) |
| `ftth_status` | enum | no | `HOMES CONNECTED`, `HOMES PASSED - STREET`, `HOMES PASSED - HOUSE`, `FTTA ROLLOUT`, or null; dash characters vary (en dash vs hyphen) |
| `connection_type` | enum | no | e.g. `SLOŽENO UKLJUČENJE` (complex connection) or empty |
| `project_name`, `project_code` | string | no | Project code may carry trailing spaces |
| `technical_acceptance_date` | date | no | Decides whether responsibility sits with the project team or the matrix |
| `network_activation_date` | date | no | Start of the 30-day regulatory stopwatch; can be in the future |
| `deregulated` | flag | no | Empty = regulated zone |
| `acquisition_status`, `acquisition_date`, `acquisition_channel`, `technology` | enum / date / string | no | Status values: approved, rejected, new, empty |
| `apartments` (KP), `customer_units` (KJ) | integer | no | 1–3 apartments = house, ≥4 = building |
| `request_id` (AAMS) | integer | no | Present only when an open request exists |
| `task_name`, `task_status` | string / enum | no | ~40 known task names in 13 groups; statuses such as New, Assigned, Parked; trailing spaces occur |
| `process_name` | string | no | Maps to process type: fibre or legacy (copper, relocation) |
| `task_created_date`, `request_submit_date` | timestamp | no | Base dates for deadline (SLA) calculation |
| `optics_interest` | flag | no | `YES` = interest registration, empty = regular request |
| `other_open_requests` | list | no | Up to a few other open request IDs on the same building |
| field-progress fields (drop installed, cabinet installed, connected, house wiring done) | string | no | Free-text-like values ("DA", "NE", "Storno", "realiziran") |
| `technician_note` | free text | no | Dated notes, sometimes contain a residents' representative phone number (PII) |
| `pm`, `am`, `programme_manager`, `field_lead`, `contractor` | string | no | Often empty at address level; project-level fallback exists |
| `condition_met_date` | timestamp | no | Only reliable signal that the drop cable is done |

## Identifier patterns

- `building_id` (ADM ID): `9999` to `99999999` (4–8 digits)
- `request_id` (AAMS): `69999999` (8 digits, usually starting with 4, 5 or 6)
- legacy request number shown to customers: `299999999` (9 digits), sometimes typed instead of the AAMS ID
- `project_name`: `FTTH_<CITY>_<AREA>` or `EUBB_<N>_<CITY>_DT_<N>_<AREA>`
- `location_code`: `999` (3 digits)
- house number with suffix: `15`, `15A`, `15/1`, `15 / 1`, `3/2A`

## What varies (the axes)

- **How the operator asks** (pilot sample, n=107): building ID ~40%, free-text address ~34%,
  follow-up without an identifier ~20%, request ID ~6%, bare number with no label ~1%.
- **How messy the input is:** typos ("dostupnosr", "osijk"), no diacritics, all caps, missing
  city, postal code and county pasted in, house number suffixes, Croatian grammatical cases of
  street names, colloquial words for a request (ticket, card, order).
- **Fibre status** (pilot answers that had one): homes passed street ~64%, homes connected ~28%,
  FTTA rollout ~5%, homes passed house ~3%.
- **The rare categories, and roughly how rare:** active regulatory stopwatch (~2%), missed task
  deadline (~6%), parked request, legacy copper/relocation request, two building records for one
  address, several open requests on one building, fibre-only address missing from the register,
  field data saying the drop is done while the status still says "street".
- **The case the system should decline or redirect:** ID or address not in the system (~6%),
  off-topic questions, requests for customer contact data, bulk lists of IDs (out of scope for v1),
  closed requests (not in the data).

## What "correct" looks like, and who judges it

FTTH operations business owners judge answers against the response template (task groups,
deadlines, stopwatch, responsibility rules). Already-judged examples exist as an internal
regression suite of ~90 scenarios built from real operator questions and operator-reported bugs.
These stay internal; only invented equivalents come to the course.

## Five golden examples

To be written from memory with every address, ID and name invented → `use_case/evals/golden.jsonl`
(TC1 Step 7). Planned coverage: address lookup (homes passed street), request with a missed
deadline and an escalation contact, active regulatory stopwatch, multi-turn clarification
(missing city, then a follow-up), and "not in the system".

## Non-text content

None. All inputs and sources are text or structured fields.

## What I am NOT allowed to do with this data

No export of real rows, no real data in this repo or in any demo, and no real data sent to a
model that is not approved for it. Inside the company, only the approved cloud model project may
see real data. For the course: share shape and numbers only, and generate synthetic data from
this profile.
