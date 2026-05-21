from zipfile import ZipFile

p = r"d:\cv_portofolio\thesis\Thesis_Mikhael_2026_v35_final.docx"
xml = ZipFile(p).read("word/document.xml").decode("utf-8", "ignore")
print("has_black:", "000000" in xml)
print("has_hyperlink_style:", "Hyperlink" in xml)
