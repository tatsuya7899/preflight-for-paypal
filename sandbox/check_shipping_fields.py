import json
import os
FIXTURES = os.path.join(os.path.dirname(__file__), "..", "backend", "fixtures")
for n in ['C','F']:
    d = json.load(open(os.path.join(FIXTURES, f'order_{n}.json')))
    pu = d['purchase_units'][0]
    print(n, 'shipping=', json.dumps(pu.get('shipping'), ensure_ascii=False)[:250])
    print(n, 'payer=', json.dumps(d.get('payer',{}).get('address',{}), ensure_ascii=False)[:150])
