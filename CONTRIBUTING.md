# Contributing

1. Create a focused branch.
2. Add tests for policy, privacy, detector, and pipeline changes.
3. Keep raw resident media and personally identifiable information out of the repository.
4. Distinguish benchmark targets from measured results.
5. Document third-party model and dataset licenses.
6. Run `python -m unittest discover -s tests -v` before opening a pull request.
7. When touching the Hailo seam, verify both `NullModel` (Stage I) and a
   `HailoModel` build (Stage II) pass the same detector tests.
