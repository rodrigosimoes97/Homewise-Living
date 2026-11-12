import re
import pathlib

html = pathlib.Path("docs/index.html").read_text(encoding="utf-8")
classes_in_html = set(re.findall(r'class=[\'"]([^\'"]+)[\'"]', html))
all_classes = set()
for c in classes_in_html:
    for single in c.split():
        all_classes.add(single)

css = pathlib.Path("docs/assets/style.css").read_text(encoding="utf-8")

missing = []
present = []
for cl in sorted(all_classes):
    pattern = r"\." + re.escape(cl) + r"[\s,\.\:\{]"
    if not re.search(pattern, css):
        missing.append(cl)
    else:
        present.append(cl)

print(f"Total classes in index.html: {len(all_classes)}")
print(f"Present classes: {len(present)}")
print(f"Missing classes in style.css: {len(missing)}")
if missing:
    print("Missing list:")
    for m in missing:
        print(f"  - {m}")
