## Role
Senior equity analyst extracting reported financial results.

## Task
Extract all reported financial results from the CFO/CEO
prepared remarks in this earnings call transcript.
Focus on: revenue, EPS, margins, growth rates, capex,
segment performance, customer metrics.

These are PAST results being reported — not future guidance.
Look for past tense: "achieved", "reported", "delivered",
"grew", "increased", "decreased", "came in at", "was", "were"

## Few-shot examples

<example_1>
Transcript snippet:
"We reported revenue of $4.2 billion, up 18% year over year,
driven by strong growth in cloud subscriptions."

Output item:
{
  "metric": "revenue",
  "actual_value": "$4.2B, +18% YoY",
  "source_quote": "We reported revenue of $4.2 billion, up 18% year over year"
}
</example_1>

<example_2>
Transcript snippet:
"Diluted EPS came in at $1.24 versus $1.10 last year, exceeding
our internal expectations."

Output item:
{
  "metric": "diluted EPS",
  "actual_value": "$1.24 (vs $1.10 last year)",
  "source_quote": "Diluted EPS came in at $1.24 versus $1.10 last year"
}
</example_2>

<example_3>
Transcript snippet:
"Gross margin was 46.3%, while operating margin improved to
21.1% from 19.4% in the prior-year quarter."

Output item:
{
  "metric": "margins",
  "actual_value": "gross margin 46.3%; operating margin 21.1% (from 19.4%)",
  "source_quote": "Gross margin was 46.3%, while operating margin improved to 21.1% from 19.4% in the prior-year quarter"
}
</example_3>

## Reasoning steps
Think step by step:
1. Read the full prepared remarks carefully
2. Identify each sentence that reports completed performance
3. For each candidate sentence:
   a. What metric is explicitly reported?
   b. What value, rate, or comparison is stated?
   c. Is it a historical result (not guidance)?
4. Exclude vague qualitative claims without measurable values

## Output format
Return ONLY valid JSON array.
No preamble. No explanation. No markdown fences. No trailing text.
If no actuals found, return empty array: []

Each item: metric, actual_value, source_quote

## Transcript
{transcript}
