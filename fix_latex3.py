with open("src/core/exporters/cocitation_exporter.py", "r") as f:
    content = f.read()

content = content.replace('{cnt:,} \\"', '{cnt:,} \\\\\\\\"')

with open("src/core/exporters/cocitation_exporter.py", "w") as f:
    f.write(content)
