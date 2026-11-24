"""Prompt viết báo cáo. Trích nguyên văn từ p04_report.ipynb của kyc_v3."""

GROUP_PROMPT = """Below is a list of news articles about adverse events of the company {company}.
Group together articles that report the SAME event or the same chain of related developments
(for example: an executive being suspended, then dismissed, then prosecuted is one event).
Articles about different events must be in different groups.

Articles (id | date | event type | description):
{lines}

Reply ONLY with a JSON object: {{"groups": [[id, id, ...], [id, ...], ...]}}
Every id must appear in exactly one group."""


EVENT_PROMPT = """You are a KYC analyst writing one entry of a due diligence report on {company}.
Using ONLY the source articles below, write an English summary of this adverse event.

Rules:
- One paragraph of 80-150 words covering 5W1H: who, what, when, where, why, how. Only for "why" and "how", if the sources do not say, add one short sentence that it is not stated. Do not write such sentences for other points.
- Every sentence must end with a citation such as [1] or [1][2] pointing to the source numbers below. Do not use facts that are not in the sources.
- Vietnamese person names: family name in capitals, no diacritics, e.g. "NGUYEN Ba Duong". Use the full name at first mention and in the headline. After that, write "Mr." or "Ms." plus the family name, e.g. "Mr. NGUYEN". Never refer to a person by the given name alone.
- Focus on the adverse event itself. Leave out business or financial details that do not help explain the event.
- Companies: international name with ticker if listed, e.g. "Petrolimex (PLX)", "Vincom Retail (VRE)".
- Translate job titles into English (Chairman, CEO, Deputy CEO, Board member...). Amounts as "VND 662 billion".
- No Vietnamese words in the output.

Sources:
{sources}

Reply ONLY with a JSON object:
{{"headline": "short English headline in sentence case (only the first word and names capitalised) that states the adverse fact itself, e.g. the loss, the charge, the dismissal",
  "date": "date of the event, YYYY-MM-DD or YYYY-MM",
  "category": "one of: Regulatory/Legal, Litigation, Fraud/Crime, Financial distress, Leadership change, Incident, Reputation",
  "summary": "the paragraph"}}"""


OVERVIEW_PROMPT = """You are a KYC analyst. Below are the adverse events found in Vietnamese news about {company}.

{items}

Write ONLY a JSON object:
{{"company_name_en": "international name of the company",
  "overview": "3-5 English sentences: the main risk themes, the most serious and the most recent events, and whether problems are ongoing. No citations, no Vietnamese words.
   Judge how serious an event is by the harm it can do to the company. An outcome that is favorable to the company (for example a lawsuit it won) is never the most serious event."}}"""
