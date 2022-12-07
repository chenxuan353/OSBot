import re
import codecs

string = input()
print("[Origin]", string)

with codecs.open("./tools/all-codes-oneline.txt", 'r', encoding='utf8') as f:
    pat = f.readline()
    string = re.sub(pattern=pat, repl="", string=string, flags=re.UNICODE)

print("[Filtered]",string)
