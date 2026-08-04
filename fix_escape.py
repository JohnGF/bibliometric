with open("src/core/exporters/cocitation_exporter.py", "r") as f:
    content = f.read()

# Let's fix the invalid escape sequences
content = content.replace('\\href', '\\\\href')
with open("src/core/exporters/cocitation_exporter.py", "w") as f:
    f.write(content)
