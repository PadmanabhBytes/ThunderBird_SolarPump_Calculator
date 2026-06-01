from fpdf import FPDF
from datetime import date

def s(text):
    return (text.replace('—', '-').replace('–', '-').replace('’', "'")
                .replace('“', '"').replace('”', '"').replace('•', '*')
                .replace('✓', '[OK]').replace('\xd7', 'x').replace('≈', '~'))

class PDF(FPDF):
    def header(self):
        self.set_fill_color(20, 60, 100)
        self.rect(0, 0, 210, 18, 'F')
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(255, 255, 255)
        self.set_xy(0, 4)
        self.cell(0, 10, 'Thunderbird Solar Pumps - Open Questions for Jun 12 Meeting', align='C')
        self.set_text_color(0, 0, 0)
        self.ln(14)

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Prepared {date.today().strftime("%B %d, %Y")}  |  Page {self.page_no()}', align='C')

    def section_title(self, title, r, g, b):
        self.set_fill_color(r, g, b)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 7, f'  {title}', fill=True, new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def question_block(self, number, question, detail):
        y = self.get_y()
        self.set_fill_color(240, 245, 255)
        self.set_draw_color(180, 200, 230)
        self.set_font('Helvetica', 'B', 9)
        self.set_xy(12, y)
        self.cell(7, 7, str(number), border=1, align='C', fill=True)
        self.set_xy(22, y)
        self.set_text_color(20, 60, 100)
        self.multi_cell(175, 5, s(question), new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(80, 80, 80)
        self.set_font('Helvetica', '', 8.5)
        self.set_x(22)
        self.multi_cell(175, 5, s(detail), new_x='LMARGIN', new_y='NEXT')
        self.ln(2)

    def confirmed_item(self, text):
        self.set_font('Helvetica', '', 9)
        self.set_text_color(40, 120, 40)
        self.set_x(14)
        self.cell(8, 5, '[OK]')
        self.set_text_color(60, 60, 60)
        self.multi_cell(170, 5, s(text), new_x='LMARGIN', new_y='NEXT')


pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()
pdf.set_left_margin(10)
pdf.set_right_margin(10)

# Intro
pdf.set_font('Helvetica', '', 9)
pdf.set_text_color(80, 80, 80)
pdf.multi_cell(0, 5,
    s('The following questions cover open items identified during the Solar Pump Calculator build. '
      'All 5 reference scenarios currently pass our validation suite. These questions are needed '
      'to lock in specs, finalize equipment logic, and ensure the tool matches TBS quoting standards.'),
    align='J')
pdf.ln(4)

# ── SECTION 1: Must Confirm ───────────────────────────────────────────────────
pdf.section_title('SECTION 1  -  Must Confirm (Affects Calculation Correctness)', 180, 30, 30)

pdf.question_block(1,
    'Full Goulds Pump Sch 40 PVC friction table',
    'The friction value for 1.25" PVC at 14 GPM (2.56 ft/100ft) was reverse-engineered from\n'
    'your Scenario 3 reference output - it was not taken from the actual Goulds table.\n'
    'Can you share the complete official Goulds Sch 40 PVC friction loss table so we can verify\n'
    'every breakpoint is correct?')

pdf.question_block(2,
    'TBS 116-1038 panel exact Vmp and Voc (spec sheet values)',
    'Your Scenario 5 reference implies Vmp ~ 32.4V (7 panels x 32.4V = 227V system Vmp).\n'
    'Our tool currently defaults to Vmp = 40V and Voc = 48V for TBS stock panels.\n'
    'What are the actual spec-sheet values for the 116-1038? This directly affects wire AWG output.')

pdf.question_block(3,
    'Equipment-inclusion rules document',
    'Corey was going to send a document defining which SKUs appear in the equipment list\n'
    'under which input combination (pump, racking, accessories, controls).\n'
    'We are holding all accessories logic until this is received.')

pdf.question_block(4,
    'Minimum well casing diameter for 15TBS-4C-AC',
    'The pump catalog currently has no minimum casing set, so the pump shows for any casing size.\n'
    'What is the actual minimum inner diameter for this pump? (Submersibles are typically 4".)\n'
    'This affects whether we show a casing-incompatibility warning to the user.')

pdf.question_block(5,
    'GPD discrepancy - is ~3 gallons/day within acceptable tolerance?',
    'Our GPD formula: GPD = GPM x 6.5 hours x 60 min x 1.1 buffer.\n'
    'In some scenarios our output differs from the reference by ~3 gallons/day.\n'
    'Is this within your acceptable tolerance, or should the formula be adjusted?')

pdf.ln(2)

# ── SECTION 2: Equipment & Display ───────────────────────────────────────────
pdf.section_title('SECTION 2  -  Equipment & Display (Affects Quote Accuracy)', 180, 110, 20)

pdf.question_block(6,
    'Drop cable AWG cutoff - is 300 ft static water level the TBS rule?',
    'We switch from 12 AWG to 10 AWG drop cable when the static water level exceeds 300 ft.\n'
    'This threshold was derived from voltage-drop physics, not a TBS spec document.\n'
    'Is 300 ft TBS\'s actual published cutoff, or should it be different?')

pdf.question_block(7,
    'Racking for 8+ panels - how does the split work?',
    'For 7 panels we split into a 3+4 rack. What happens at 8, 9, 10+ panels?\n'
    'Does it go 4+4, 4+5, etc.? Do the rack SKUs (201-1003 through 206-1003) change\n'
    'above 7 panels, or do you use two separate rack assemblies?')

pdf.question_block(8,
    'Rack SKUs for 1-panel and 2-panel systems',
    'Our code generates SKU 201-1003 for 1-panel and 202-1003 for 2-panel racks.\n'
    'Do these SKUs actually exist in TBS inventory?')

pdf.question_block(9,
    'Mounting channel - always required or only with TBS racking?',
    'The TBS-4ACM monitor mounting channel currently only appears when TBS supplies the racking.\n'
    'Should it appear in the equipment list regardless of who supplies the solar racking?')

pdf.ln(2)

# ── SECTION 3: Edge Cases ────────────────────────────────────────────────────
pdf.section_title('SECTION 3  -  Edge Cases & Future-Proofing', 60, 60, 140)

pdf.question_block(10,
    'Solar window - 6.5 hours/day fixed or zone-dependent?',
    'We use 6.5 hours/day as a fixed solar window for all locations:\n'
    '   GPD = GPM x 6.5 x 60 x 1.1\n'
    'Should this vary by solar zone or geography, or is 6.5 hours a fixed TBS standard?')

pdf.question_block(11,
    'Deep-well generator backup - fallback panel sizing approach',
    'When a pump cannot reach nameplate flow at very high TDH (e.g. Scenario 5 at 480 ft),\n'
    'we size panels to deliver the customer\'s required GPM instead of the pump\'s rated GPM.\n'
    'Is this correct, or should the tool recommend a different pump in that scenario?')

pdf.question_block(12,
    'Voc / Vmp - STC only or NEC 690 temperature-derated?',
    'Voc and Vmp values in our output are currently at STC (25 deg C).\n'
    'Should they be derated for local minimum temperature per NEC 690.7?\n'
    'If yes, we would need to add a design minimum temperature input field to the form.')

pdf.ln(4)

# ── CONFIRMED ─────────────────────────────────────────────────────────────────
pdf.section_title('ALREADY CONFIRMED  -  No Action Needed', 40, 120, 40)
pdf.ln(1)

confirmed = [
    'TDH formula: Pumping Level + Elevation + Friction + Pressure Head x Safety Factor',
    '7.5% STC efficiency derating - applied consistently for all system types (confirmed May 29)',
    'Scenario 4 TDH = 125 ft - exact match confirmed by Corey (May 29)',
    'Voc/Vmp difference of 0.2V - accepted as close enough (May 29)',
    'Dry-run checkbox: only adds dry well sensor to parts list + flags low recovery warning; does NOT affect TDH',
    'Panel dimensions: only affect racking pipe length calculation, not hydraulic calculations',
    'Drop cable always appears in Customer Provided section regardless of racking/panel ownership',
]
for item in confirmed:
    pdf.confirmed_item(item)

out = '/Users/consultadd/Downloads/Thunderbird-SolarPumps/Client_Meeting_Questions.pdf'
pdf.output(out)
print(f'PDF saved: {out}')
