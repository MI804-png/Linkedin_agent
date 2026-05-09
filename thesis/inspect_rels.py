import zipfile, re

with zipfile.ZipFile(r'd:\cv_portofolio\thesis\FinalThesis_Template.docx', 'r') as z:
    files = z.namelist()
    rels_files = [f for f in files if '_rels' in f]
    print('Rels files:', rels_files)
    for rf in rels_files:
        print(f'\n--- {rf} ---')
        content = z.read(rf).decode('utf-8')
        for m in re.finditer(r'Id="([^"]+)"[^>]*Target="([^"]+)"', content):
            print(f'  {m.group(1)} -> {m.group(2)}')
