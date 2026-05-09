try:
    import pypdf
    reader = pypdf.PdfReader(r'd:\cv_portofolio\thesis\Thesis_HR_Decision_Support_System_50pages_ACADEMIC_FINAL_v3.pdf')
    print('Pages:', len(reader.pages))
    # First page text
    text = reader.pages[0].extract_text()
    print('=== COVER PAGE ===')
    print(text[:1500])
except ImportError:
    try:
        import pdfplumber
        with pdfplumber.open(r'd:\cv_portofolio\thesis\Thesis_HR_Decision_Support_System_50pages_ACADEMIC_FINAL_v3.pdf') as pdf:
            print(pdf.pages[0].extract_text()[:1500])
    except ImportError:
        print('Neither pypdf nor pdfplumber available')
