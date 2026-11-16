"""Kafe Kamera'nın AugeLab Studio'ya kaydettiği özel bloklar.

Studio her bloğun dosyasını bu tanımlardan kendisi üretir (node.custom.create). Bloklar incedir: asıl iş, Studio'nun özel
blok klasörünün yanına konan "kafe_engine" klasöründeki kafe_motor paketindedir (model ve ek kütüphaneler de orada).
Studio'nun kendi ortamına hiçbir paket kurulmaz; motorun ek kütüphaneleri sys.path'in SONUNA eklenir.

Sahne:  Kafe Kamera İşi (metin girişi) → Kafe Kaynak → Kafe Algılama
Hiçbir blok görüntü çıkışı vermez: yüzleri açık kare Studio'da başka bir yere gitmez.
"""
from __future__ import annotations

MOTOR_KLASORU = "kafe_engine"  # Studio'nun custom_blocks klasörünün kardeşi
KAYNAK_OP = "KafeKaynak"
KAYNAK_BASLIK = "Kafe Kaynak"
ALGILA_OP = "KafeAlgila"
ALGILA_BASLIK = "Kafe Algılama"

# İki blokta da aynı: motoru bul, sürümü değiştiyse yeniden yükle.
_YUKLE = """\
klasor = state.get('klasor')
if klasor is None:
    here = globals().get('__file__')
    if here:
        klasor = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(here))), 'kafe_engine')
    else:
        klasor = os.path.join(os.environ.get('APPDATA', ''), 'AugeLab Studio', 'marketplace', 'kafe_engine')
    if not os.path.isdir(os.path.join(klasor, 'kafe_motor')):
        outputs['Durum'] = 'hata: motor bulunamadi (Kafe Kamera programini bir kez acin)'
        return
    for p in (klasor, os.path.join(klasor, 'deps')):
        if os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)
    state['klasor'] = klasor
try:
    damga = os.path.getmtime(os.path.join(klasor, 'surum.txt'))
except OSError:
    damga = 0
if state.get('blok') is None or state.get('damga') != damga:
    imza = ''
    try:
        with open(os.path.join(klasor, 'surum.txt'), encoding='ascii') as f:
            imza = f.read()
    except OSError:
        pass
    eski = sys.modules.get('kafe_motor')
    if eski is not None and getattr(eski, '_imza', None) != imza:
        for ad in [m for m in sys.modules if m == 'kafe_motor' or m.startswith('kafe_motor.')]:
            del sys.modules[ad]
    try:
        state['blok'] = importlib.import_module('kafe_motor.blok')
        sys.modules['kafe_motor']._imza = imza
    except Exception as exc:
        state['blok'] = None
        outputs['Durum'] = 'hata: motor yuklenemedi: %s: %s' % (type(exc).__name__, exc)
        return
    state['damga'] = damga
    state['durum'] = {}
blok = state['blok']
"""

KAYNAK_KODU = """\
outputs['Image'] = None
outputs['Sira'] = -1
outputs['Zaman'] = 0
outputs['Bitti'] = False
outputs['Durum'] = ''
""" + _YUKLE + """\
try:
    goruntu, sira, zaman, bitti, durum = blok.kaynak(state['durum'], inputs['Is'] or '')
except Exception as exc:
    outputs['Durum'] = 'hata: %s: %s' % (type(exc).__name__, exc)
    outputs['Bitti'] = True
    return
outputs['Image'] = goruntu
outputs['Sira'] = sira
outputs['Zaman'] = zaman
outputs['Bitti'] = bitti
outputs['Durum'] = durum
"""

ALGILA_KODU = """\
outputs['Durum'] = ''
""" + _YUKLE + """\
try:
    outputs['Durum'] = blok.algila(state['durum'], inputs['Image'], inputs['Is'] or '', inputs['Sira'], inputs['Zaman'],
                                   bool(inputs['Bitti']), inputs['Kaynak'] or '')
except Exception as exc:
    outputs['Durum'] = 'hata: %s: %s' % (type(exc).__name__, exc)
"""

KAYNAK = {
    "resolverKey": "kafe_kaynak",
    "name": KAYNAK_OP,
    "opCode": KAYNAK_OP,
    "title": KAYNAK_BASLIK,
    "kind": "computation",
    "description": (
        "Kafe Kamera işinin kaynağı: video dosyasını kare kare, tek kareyi bir kez ya da (arayüzsüz koşuda) canlı kameranın "
        "akışını okur. İş, Kafe Kamera'nın başlattığı sürecin ortamından gelir. Çıkışlar: görüntü, kare sırası, zaman (sn), "
        "akış bittiğinde bir kez True olan Bitti ve durum."
    ),
    "imports": ["sys", "os", "importlib"],
    "inputs": [{"name": "Is", "type": "String"}],
    "outputs": [{"name": "Image", "type": "ImageAny"}, {"name": "Sira", "type": "Number"}, {"name": "Zaman", "type": "Number"},
                {"name": "Bitti", "type": "Boolean"}, {"name": "Durum", "type": "String"}],
    "parameters": [],
    "processCode": KAYNAK_KODU,
}

ALGILA = {
    "resolverKey": "kafe_algila",
    "name": ALGILA_OP,
    "opCode": ALGILA_OP,
    "title": ALGILA_BASLIK,
    "kind": "computation",
    "description": (
        "Kişi algılama, takip (ByteTrack) ve iskelet noktaları (YOLO11s-pose). Sonucu Kafe Kamera'nın verdiği dosyaya "
        "yazar; görüntü çıkışı yoktur (yüzleri Kafe Kamera gizler). Çıkış: durum."
    ),
    "imports": ["sys", "os", "importlib"],
    "inputs": [{"name": "Image", "type": "ImageAny"}, {"name": "Is", "type": "String"}, {"name": "Sira", "type": "Number"},
               {"name": "Zaman", "type": "Number"}, {"name": "Bitti", "type": "Boolean"}, {"name": "Kaynak", "type": "String"}],
    "outputs": [{"name": "Durum", "type": "String"}],
    "parameters": [],
    "processCode": ALGILA_KODU,
}

TANIMLAR = [KAYNAK, ALGILA]


def imza() -> str:
    """Blok tanımlarının özeti: giriş ya da çıkışlar değiştiyse hazır sahnenin yeniden üretilmesi gerekir."""
    import hashlib
    import json

    return hashlib.sha1(json.dumps(TANIMLAR, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def dosya_metni(t: dict) -> str:
    """Bloğun Studio'nun özel blok klasörüne konacak dosyası: Studio'nun node.custom.create ile tanımdan ürettiği dosyanın
    aynısı (Raf Kamera'da bayt bayt denetlendi). Arayüzsüz çalışmada (studio run) Studio açık olmadığından dosyayı panel
    kendisi yazar."""
    op = t["opCode"]
    girisler = ",\n".join(f"        SocketTypes.{g['type']}({g['name']!r}, multiple=False)" for g in t["inputs"])
    cikislar = ",\n".join(f"        SocketTypes.{c['type']}({c['name']!r}, multiple=False)" for c in t["outputs"])
    adlar = ", ".join(repr(c["name"]) for c in t["outputs"])
    if len(t["outputs"]) == 1:
        adlar += ","
    islem = "".join(("        " + s if s.strip() else "") + "\n" for s in t["processCode"].rstrip("\n").split("\n"))
    girdi = ",\n".join(f"            {g['name']!r}: self.input[{g['name']!r}].data" for g in t["inputs"])
    cikti = ",\n".join(f"            {c['name']!r}: None" for c in t["outputs"])
    ithal = "".join(f"import {m}\n" for m in t.get("imports") or [])
    return (
        "from studio.custom_block import (\n"
        "    Block, CheckBox, DropDown, Label, SocketTypes, TextInput, add_block,\n"
        ")\n\n"
        f"{ithal}\n"
        f"class {op}(Block):\n"
        f"    op_code = {op!r}\n"
        f"    input_sockets = [\n{girisler}\n    ]\n"
        f"    output_sockets = [\n{cikislar}\n    ]\n"
        "    _augelab_generated_spec_version = 1\n"
        f"    _augelab_output_names = ({adlar})\n\n"
        "    def init(self):\n"
        f"        self.op_title = {t['title']!r}\n"
        "        self.width = 280\n"
        "        self.height = 150\n"
        f"        self.tooltip = {t['description']!r}\n"
        "        pass\n"
        "        self._augelab_generated_state = {}\n\n"
        "    @staticmethod\n"
        "    def _process(inputs, parameters, state, outputs):\n"
        f"{islem}\n"
        "    def run(self):\n"
        f"        inputs = {{\n{girdi}\n        }}\n"
        "        parameters = {\n            \n        }\n"
        "        state = self._augelab_generated_state\n"
        f"        outputs = {{\n{cikti}\n        }}\n"
        "        self._process(inputs, parameters, state, outputs)\n"
        "        unknown = set(outputs).difference(self._augelab_output_names)\n"
        "        if unknown:\n"
        "            raise ValueError(f\"Undeclared generated outputs: {sorted(unknown)}\")\n"
        "        for output_name in self._augelab_output_names:\n"
        "            self.output[output_name].data = outputs[output_name]\n\n\n"
        f"add_block({op}.op_code, {op})\n"
    )
