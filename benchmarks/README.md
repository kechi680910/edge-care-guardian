# Performance validation

`stage2_metrics.csv` distinguishes targets from measured results. Populate the measured column only after running on the ASUS UGen300 hardware supplied for Stage II.

Required artifacts for the final repository:

- Model name, version, license, quantization, and compiler version.
- UGen300 interface (M.2 or USB), host specification, and software versions.
- Dataset/scenario description and subject-disjoint split.
- Recall, precision, F1, false alerts per room-day, latency percentiles, throughput, and sustained temperature.
- Packet-capture evidence for the privacy egress rule.
