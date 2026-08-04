with open("src/core/exporters/cocitation_exporter.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '{cnt:,}' in line:
        # replace the single trailing backslash with double backslash
        lines[i] = line.replace('{cnt:,} \\"', '{cnt:,} \\\\\\\\"')

with open("src/core/exporters/cocitation_exporter.py", "w") as f:
    f.writelines(lines)
