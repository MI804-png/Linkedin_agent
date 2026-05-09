import os, glob

keep = 'AutoApply_Thesis_v13.docx'
folder = r'd:\cv_portofolio\thesis'

for f in glob.glob(os.path.join(folder, 'AutoApply_Thesis_v*.docx')):
    if os.path.basename(f) != keep:
        try:
            os.remove(f)
            print(f'Deleted: {f}')
        except PermissionError:
            print(f'Skipped (file open): {f}')

print('Remaining:')
for f in glob.glob(os.path.join(folder, 'AutoApply_Thesis_v*.docx')):
    print(f'  {os.path.basename(f)}')
