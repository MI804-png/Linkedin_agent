from docx import Document
from docx.oxml.ns import qn
import zipfile, os

# Extract images from template
with zipfile.ZipFile(r'd:\cv_portofolio\thesis\FinalThesis_Template.docx', 'r') as z:
    imgs = [n for n in z.namelist() if n.startswith('word/media/')]
    print('Images in template:', imgs)
    for img in imgs:
        out = r'd:\cv_portofolio\thesis\template_' + os.path.basename(img)
        with z.open(img) as src, open(out, 'wb') as dst:
            dst.write(src.read())
        print('Extracted:', out)

doc = Document(r'd:\cv_portofolio\thesis\FinalThesis_Template.docx')
for i, p in enumerate(doc.paragraphs[:40]):
    pics = p._element.findall('.//' + qn('a:blip'))
    pic_note = f' [HAS_IMAGE rId={[x.get(qn("r:embed")) for x in pics]}]' if pics else ''
    print(f'[{i}] style={p.style.name!r} text={p.text[:70]!r}{pic_note}')
