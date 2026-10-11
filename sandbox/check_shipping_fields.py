import json
for n in ['C','F']:
    d = json.load(open(f'/Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/backend/fixtures/order_{n}.json'))
    pu = d['purchase_units'][0]
    print(n, 'shipping=', json.dumps(pu.get('shipping'), ensure_ascii=False)[:250])
    print(n, 'payer=', json.dumps(d.get('payer',{}).get('address',{}), ensure_ascii=False)[:150])
