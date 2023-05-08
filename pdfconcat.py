import pypdf
import glob
pdf_files = []
files = glob.glob("data/*.pdf")
for file in files:
    pdf_files.append(file)

merger = pypdf.PdfMerger()

for pdf_file in pdf_files:
  merger.append(pdf_file)

merger.write("data/submit.pdf")
merger.close()