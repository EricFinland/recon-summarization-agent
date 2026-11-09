"""Summarize parsed scan data into a ReconSummary.

Rule: only report what is present in the scan input. Do not add hosts,
ports, services, or findings that the input does not support.

TODO: implement summarization (and the LLM call, if used).
"""
