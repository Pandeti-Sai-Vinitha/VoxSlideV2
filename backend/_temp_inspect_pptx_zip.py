import zipfile
from pathlib import Path
path = Path('temp_test_output.pptx')
with zipfile.ZipFile(path, 'r') as z:
    media = [n for n in z.namelist() if n.startswith('ppt/media/')]
    print('media files:', media)
    for name in media:
        print('  ', name, z.getinfo(name).file_size)
    rels = [n for n in z.namelist() if n.startswith('ppt/slides/_rels/')]
    print('slide rels:', rels)
    for rel in rels:
        print('REL', rel)
        print(z.read(rel).decode('utf-8'))
