# -*- coding: utf-8 -*-
"""lookup_template.html 의 __DATA_PLACEHOLDER__ 를 실제 JSON으로 치환해 lookup.html 생성"""
with open("data/webdata.json", encoding="utf-8") as f:
    data_json = f.read()

with open("lookup_template.html", encoding="utf-8") as f:
    template = f.read()

out = template.replace("__DATA_PLACEHOLDER__", data_json)

with open("lookup.html", "w", encoding="utf-8") as f:
    f.write(out)

print(f"생성 완료: lookup.html ({len(out.encode('utf-8'))/1024:.1f} KB)")
