import re

with open("src/core/exporters/cocitation_exporter.py", "r") as f:
    content = f.read()

# Make sure openalex ID filtering works for "openalex:" filter format in API.
# Basically when we ask openalex `filter=openalex:W123|W456`, it must be valid.

# If there is no result from OpenAlex due to "Bad Request" it might be because
# our fake ID like "https://openalex.org/W1" produces "W1", which is not a valid OpenAlex ID length/format
# Let's verify that the logic only takes OpenAlex IDs that start with W and ignores others.
pass
