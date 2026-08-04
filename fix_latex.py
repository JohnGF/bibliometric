import re

with open("src/core/exporters/cocitation_exporter.py", "r") as f:
    content = f.read()

# Fix 1: Make fetch_and_cache_missing_openalex_titles work for full URLs by checking the split result.
# Right now it checks w.startswith("W"), we should also check w.split("/")[-1].startswith("W").
content = re.sub(
    r'missing = list\(set\(\[w\.strip\(\)\.lower\(\) for w in w_ids if w\.strip\(\)\.lower\(\) not in lookup and \(w\.startswith\("W"\) or w\.startswith\("w"\)\)\]\)\)',
    r'missing = list(set([w.strip().lower().split("/")[-1] for w in w_ids if w.strip().lower() not in lookup and w.strip().split("/")[-1].lower().startswith("w")]))',
    content
)

# Fix 2: the latex row ends should be \\
content = re.sub(r'\{cnt:,\} \\"', r'{cnt:,} \\\\"', content)

with open("src/core/exporters/cocitation_exporter.py", "w") as f:
    f.write(content)
