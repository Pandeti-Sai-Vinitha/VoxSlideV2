from pptx import Presentation

for tmpl in ["template5.potx"]:
    print(f"--- {tmpl} ---")
    prs = Presentation(f"backend/sample_ppt/{tmpl}")
    for i, layout in enumerate(prs.slide_layouts):
        print(f"Layout {i}: {layout.name}")
        for ph in layout.placeholders:
            ph_type = getattr(ph.placeholder_format, "type", None)
            print(f"  - {ph.name} ({ph_type})")
