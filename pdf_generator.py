from fpdf import FPDF
from datetime import datetime
import spacy

class ForensicDossierPDF(FPDF):
    def header(self):
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 26, "F")
        self.set_text_color(56, 189, 248)
        self.set_font("Helvetica", "B", 13)
        self.set_xy(12, 6)
        self.cell(0, 7, "CENTRAL FORENSIC LINGUISTICS DIVISION", align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(148, 163, 184)
        self.set_x(12)
        self.cell(0, 4, "LOCAL DISK VAULT // INVESTIGATION DOSSIER", align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(56, 189, 248)
        self.set_line_width(0.8)
        self.line(0, 26, 210, 26)
        self.ln(10)

    def footer(self):
        self.set_y(-16)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.3)
        self.line(12, 281, 198, 281)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184)
        self.set_x(12)
        self.cell(90, 8, "RESTRICTED AGENCY VAULT FILE", align="L")
        self.cell(96, 8, f"Dossier Page {self.page_no()}/{{nb}}", align="R")

def generate_pdf_report(case_id: str, title: str, entries: list[dict], processed_entities: list[dict], triplets: list[dict], operative: str, agency: str) -> bytes:
    pdf = ForensicDossierPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Metadata Header Box
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.rect(12, 32, 186, 24, "DF")
    
    pdf.set_xy(16, 35)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(45, 5, "CASE FILE:")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(50, 5, f"{case_id} - {title[:28]}")
    
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(40, 5, "LOCAL LOGS:")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(50, 5, f"{len(entries)} Entries Stored", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(16)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(45, 5, "AGENT CLEARANCE:")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(50, 5, operative)

    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(40, 5, "AGENCY VAULT:")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(50, 5, agency[:30], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(12)

    # Section 1: Chronological Evidence Log
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "1. CHRONOLOGICAL EVIDENCE LOGS", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    for i, entry in enumerate(entries, 1):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(2, 132, 199)
        pdf.cell(0, 5, f"LOG #{i} // TIMESTAMP: {entry['timestamp']} // AGENT: {entry['author']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(51, 65, 85)
        clean_text = entry["text"].encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(186, 5, clean_text)
        pdf.ln(3)
    pdf.ln(4)

    # Section 2: Named Entities
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "2. IDENTIFIED NAMED ENTITIES (NER)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(75, 7, "  Entity Mention", fill=True)
    pdf.cell(45, 7, "  Classification", fill=True)
    pdf.cell(66, 7, "  Context Role", fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 8.5)
    fill = False
    for ent in processed_entities:
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(30, 41, 59)
        safe_ent = ent["text"].encode("latin-1", "replace").decode("latin-1")
        pdf.cell(75, 6, f"  {safe_ent[:35]}", border=1, fill=True)
        pdf.cell(45, 6, f"  {ent['label']}", border=1, fill=True)
        pdf.cell(66, 6, f"  {spacy.explain(ent['label'])[:35]}", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
        fill = not fill
    pdf.ln(6)

    # Section 3: SVO Linkages
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "3. CUMULATIVE RELATIONAL LINKAGES (S-V-O)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(65, 7, "  Source Entity (Subject)", fill=True)
    pdf.cell(45, 7, "  Action / Predicate", fill=True)
    pdf.cell(76, 7, "  Target / Object Destination", fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 8.5)
    if triplets:
        fill = False
        for t in triplets:
            pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(30, 41, 59)
            s = t['Subject'].encode("latin-1", "replace").decode("latin-1")
            r = t['Relation'].encode("latin-1", "replace").decode("latin-1")
            o = t['Object'].encode("latin-1", "replace").decode("latin-1")
            pdf.cell(65, 6, f"  {s[:35]}", border=1, fill=True)
            pdf.cell(45, 6, f"  {r[:22]}", border=1, fill=True)
            pdf.cell(76, 6, f"  {o[:45]}", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
            fill = not fill
    else:
        pdf.cell(186, 6, "  No direct SVO relationship triples parsed in this evidence segment.", border=1, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())