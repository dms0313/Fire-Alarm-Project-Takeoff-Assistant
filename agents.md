Please address the comments from this code review:

## Overall Comments
- Extract the huge inline JSON schema prompt in `_analyze_report_sections` into a dedicated constant or external template to declutter the method and simplify maintenance.
- Rather than hardcoding the 60000-character trimming logic, consider making the prompt length limit configurable or chunking the input to preserve important context.
- The roll-up logic in `_aggregate_totals` and `_build_takeoff_counts` is similar; refactor shared item-processing into a helper to avoid code duplication.

## Individual Comments

### Comment 1
<location> `modules/gemini_analyzer_unified.py:288-291` </location>
<code_context>
+"""
+
+        try:
+            response = self.model.generate_content(self._add_system_instruction(prompt))
+            return self._parse_json(getattr(response, "text", ""), {})
+        except Exception as e:
</code_context>

<issue_to_address>
**suggestion:** Check for empty or malformed model responses before parsing.

Add validation for the response before parsing, or update _parse_json to handle empty or malformed input robustly.

```suggestion
        try:
            response = self.model.generate_content(self._add_system_instruction(prompt))
            response_text = getattr(response, "text", "")
            if not response_text or not isinstance(response_text, str) or response_text.strip() == "":
                logger.error("Model response is empty or not a valid string.")
                return []
            return self._parse_json(response_text, {})
        except Exception as e:
```
</issue_to_address>

### Comment 2
<location> `modules/gemini_analyzer_unified.py:409` </location>
<code_context>
+        )
+
+        return {
+            "generated_at": datetime.now().isoformat(),
+            "total_pages": len(pages),
+            "fire_alarm_pages": fa_pages,
</code_context>

<issue_to_address>
**suggestion:** Consider using UTC for generated_at timestamp.

datetime.now() uses local time, which can lead to inconsistencies across time zones. Use datetime.utcnow().isoformat() for a consistent timestamp.

```suggestion
            "generated_at": datetime.utcnow().isoformat(),
```
</issue_to_address>

### Comment 3
<location> `modules/gemini_analyzer_unified.py:217-221` </location>
<code_context>
        relevant_pages = [
            p for p in pages if not fa_pages or p.get("page_number") in fa_pages
        ]
        if not relevant_pages:
            relevant_pages = pages

</code_context>

<issue_to_address>
**suggestion (code-quality):** Use `or` for providing a fallback value ([`use-or-for-fallback`](https://docs.sourcery.ai/Reference/Rules-and-In-Line-Suggestions/Python/Default-Rules/use-or-for-fallback))

```suggestion
        relevant_pages = [
                    p for p in pages if not fa_pages or p.get("page_number") in fa_pages
                ] or pages

```

<br/><details><summary>Explanation</summary>Thanks to the flexibility of Python's `or` operator, you can use a single
assignment statement, even if a variable can retrieve its value from various
sources. This is shorter and easier to read than using multiple assignments with
`if not` conditions.
</details>
</issue_to_address>