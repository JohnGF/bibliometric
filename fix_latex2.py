import re

with open("src/core/exporters/cocitation_exporter.py", "r") as f:
    content = f.read()

# Make sure we didn't miss fixing the backslashes at the end of the line.
# Looking for `{cnt:,} \` and making it `{cnt:,} \\`

lines = content.split('\n')
for i, line in enumerate(lines):
    if '{cnt:,}' in line and line.strip().endswith('\\"'):
        lines[i] = line[:-2] + '\\\\"'
    elif '{cnt:,}' in line and line.strip().endswith('\\\\"'):
        # It's already fine
        pass

content = '\n'.join(lines)

with open("src/core/exporters/cocitation_exporter.py", "w") as f:
    f.write(content)
