import re
with open("src/core/exporters/cocitation_exporter.py", "r") as f:
    content = f.read()

# Replace any number of backslashes before href with just \\href
content = re.sub(r'\\+href', r'\\href', content)

# But wait, in a f-string that is NOT raw, it should be "\\\\href" to yield "\\href" in string.
content = content.replace('\\href', '\\\\href')
with open("src/core/exporters/cocitation_exporter.py", "w") as f:
    f.write(content)
